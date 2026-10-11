"""Uses repository rollback/backend with temporary paths and synthetic requests."""
import contextlib
import http.client
import io
import json
import os
import ssl
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.database import Database
from backend.map_preview import MapObservations, make_application
from backend.mystic_login_port import LoginPortApplication
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.probe_files import prepare, restore
from tools.map_preview_support import install_config, ENGINE_INI
from tools import ramsgate_map_preview as preview


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config'
        self.config.mkdir()
        (self.config/'Engine.ini').write_bytes(b'original settings')
        self.hosts, self.ca = self.root/'hosts', self.root/'cacert.pem'
        self.hosts.write_bytes(b'127.0.0.1 localhost\n')
        self.ca.write_bytes(b'original CA')
        self.journal = prepare(self.root/'state', self.ca, self.hosts, self.config,
                              b'-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----',
                              ['auth-prod.steelyard.ca'])
    def test_config_roundtrip(self):
        install_config(self.config, self.journal)
        self.assertEqual((self.config/'Engine.ini').read_text(), ENGINE_INI)
        restore(self.journal)
        self.assertEqual((self.config/'Engine.ini').read_bytes(), b'original settings')
        self.assertEqual(self.ca.read_bytes(), b'original CA')
        self.assertEqual(self.hosts.read_bytes(), b'127.0.0.1 localhost\n')
        saved = Path(json.loads(self.journal.read_text())['config_after'])
        self.assertEqual((saved/'Engine.ini').read_text(), ENGINE_INI)
    def test_normal_login_preserves_cooked_default_map(self):
        install_config(self.config, self.journal, normal_login=True)
        self.assertEqual((self.config/'Engine.ini').read_bytes(), b'')
        restore(self.journal)
        self.assertEqual((self.config/'Engine.ini').read_bytes(), b'original settings')
        self.assertEqual(self.ca.read_bytes(), b'original CA')
        self.assertEqual(self.hosts.read_bytes(), b'127.0.0.1 localhost\n')

    def test_wrong_marker_refused(self):
        (self.config/'.reawakened-probe').write_text('wrong')
        with self.assertRaises(ValueError):
            install_config(self.config, self.journal)
        self.assertFalse((self.config/'Engine.ini').exists())
    def test_existing_config_file_not_overwritten(self):
        (self.config/'Engine.ini').write_text('keep')
        with self.assertRaises(FileExistsError):
            install_config(self.config, self.journal)
        self.assertEqual((self.config/'Engine.ini').read_text(), 'keep')
    def test_restored_journal_refused(self):
        restore(self.journal)
        with self.assertRaises(ValueError):
            install_config(self.config, self.journal)
        self.assertEqual((self.config/'Engine.ini').read_bytes(), b'original settings')
    def test_wrong_directory_refused(self):
        with self.assertRaises(ValueError):
            install_config(self.root/'other', self.journal)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.addCleanup(self.db.close)
        self.obs = MapObservations()
        self.app = make_application(self.db, self.obs)
    def test_observation_preserves_404(self):
        args = ('POST', 'tracking-prod.steelyard.ca', '/heartbeat', {}, b'{"map":"ramsgate_01_persistent"}')
        baseline = LoginPortApplication(self.db).handle(*args, secure=True)
        reply = self.app.handle(*args, secure=True)
        self.assertEqual((reply.status, reply.body()), (baseline.status, baseline.body()))
        self.assertTrue(self.obs.report()['ramsgate_self_report_seen'])
    def test_http_not_observed(self):
        self.app.handle('POST', 'tracking-prod.steelyard.ca','/heartbeat',{}, b'{"map":"ramsgate_01_persistent"}')
        self.assertFalse(self.obs.report()['ramsgate_self_report_seen'])
    def test_origin_rejected_and_not_observed(self):
        reply = self.app.handle('POST', 'tracking-prod.steelyard.ca','/heartbeat',{'Origin':'null'},
                                b'{"map":"ramsgate_01_persistent"}', secure=True)
        self.assertEqual(reply.status,403)
        self.assertFalse(self.obs.report()['ramsgate_self_report_seen'])
    def test_no_identity_shortcut(self):
        reply = self.app.handle('GET','dauntless-prod.steelyard.ca','/character',{},secure=True)
        self.assertEqual(reply.status,401)
        self.assertFalse(self.app.handle('GET','localhost','/health',{}).payload['game_compatible'])
    def test_authenticated_city_join_waits_for_real_host(self):
        self.app.lab_key = 'map-test-key'
        issued = self.app.handle('POST', 'localhost', '/__lab/session',
                                 {'X-Reawakened-Lab-Key': 'map-test-key'},
                                 b'{"subject":"map-test"}', secure=True)
        self.assertEqual(issued.status, 200)
        token = issued.payload['payload']['sessiontoken']
        session = self.app.sessions.resolve(token)
        self.db.create(session.account_id, 'MapSlayer', '{}')
        headers = {'Authorization': 'Bearer ' + token}
        self.assertEqual(self.app.handle('GET', 'dauntless-prod.steelyard.ca',
                         '/character', headers, secure=True).status, 200)
        body = json.dumps({'playerId': session.account_id, 'gameMode': 'CITY',
                           'buildId': '682875_2.1.1_shipping'}).encode()
        reply = self.app.handle('POST', 'mm2-prod.steelyard.ca', '/candidate/join',
                                headers, body, secure=True)
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.payload['status'], 'MATCHING')
        self.assertNotIn('serverInfo', reply.payload)
        self.assertFalse(self.obs.report()['game_server_started'])
        self.assertEqual(self.app.handle('GET', 'dauntless-prod.steelyard.ca',
                         '/character', {}, secure=True).status, 401)

    def test_isolated_normal_login_database_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'normal-login.sqlite3'
            db1 = Database(path)
            try:
                account = db1.account('eos-research:synthetic-subject')['accountId']
                created = db1.create(account, 'PersistentSlayer', '{}')
            finally:
                db1.close()
            db2 = Database(path)
            try:
                same = db2.account('eos-research:synthetic-subject')['accountId']
                self.assertEqual(same, account)
                self.assertEqual(db2.get(same)[0]['id'], created['id'])
                self.assertEqual(db2.get(db2.account('lab:other')['accountId']), [])
            finally:
                db2.close()

    def test_offline_identity_smoke_without_epic_or_game(self):
        result = preview.offline_identity_self_test()
        self.assertEqual(result['offline_identity'], 'passed')
        self.assertEqual(result['local_character'], 'passed')
        self.assertEqual(result['city_request'], 'matching_no_host')
        self.assertEqual(result['epic_authentication'], 'not_tested')
        self.assertEqual(result['game_client'], 'not_launched')
        self.assertEqual(result['game_server'], 'not_started')

    def test_persistent_local_account_character_and_city_after_backend_restart(self):
        # A fresh server process must find the same character, but must not
        # reuse the previous process's session token or invent a game host.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'normal-login.sqlite3'
            db1 = Database(path)
            try:
                app1 = make_application(db1, MapObservations())
                app1.lab_key = 'restart-test-only'
                issued = app1.handle('POST', 'localhost', '/__lab/session',
                                     {'X-Reawakened-Lab-Key': 'restart-test-only'},
                                     b'{"subject":"persistent-local-slayer"}', secure=True)
                self.assertEqual(issued.status, 200)
                token1 = issued.payload['payload']['sessiontoken']
                session1 = app1.sessions.resolve(token1)
                created = db1.create(session1.account_id, 'RamsgateSlayer', '{}')
            finally:
                db1.close()
            db2 = Database(path)
            try:
                app2 = make_application(db2, MapObservations())
                old_headers = {'Authorization': 'Bearer ' + token1}
                self.assertEqual(app2.handle('GET', 'dauntless-prod.steelyard.ca',
                                             '/character', old_headers, secure=True).status, 401)
                app2.lab_key = 'restart-test-only'
                issued2 = app2.handle('POST', 'localhost', '/__lab/session',
                                      {'X-Reawakened-Lab-Key': 'restart-test-only'},
                                      b'{"subject":"persistent-local-slayer"}', secure=True)
                self.assertEqual(issued2.status, 200)
                token2 = issued2.payload['payload']['sessiontoken']
                self.assertNotEqual(token1, token2)
                headers = {'Authorization': 'Bearer ' + token2}
                characters = app2.handle('GET', 'dauntless-prod.steelyard.ca',
                                          '/character', headers, secure=True)
                self.assertEqual(characters.status, 200)
                self.assertEqual([c['id'] for c in characters.payload], [created['id']])
                session2 = app2.sessions.resolve(token2)
                body = json.dumps({'playerId': session2.account_id, 'gameMode': 'CITY',
                                   'buildId': '682875_2.1.1_shipping'}).encode()
                city = app2.handle('POST', 'mm2-prod.steelyard.ca', '/candidate/join',
                                   headers, body, secure=True)
                self.assertEqual(city.status, 200)
                self.assertEqual(city.payload['status'], 'MATCHING')
                self.assertNotIn('serverInfo', city.payload)
            finally:
                db2.close()

    def test_wrong_service_not_observed(self):
        self.app.handle('POST','auth-prod.steelyard.ca','/heartbeat',{},b'{"map":"ramsgate_01_persistent"}',secure=True)
        self.assertFalse(self.obs.report()['ramsgate_self_report_seen'])
    def test_real_tls_map_self_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tls = generate(Path(tmp)/'tls')
            server = make_server(self.app, '127.0.0.1', 0, tls_context(tls/'server.pem',tls/'server-key.pem'))
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            thread.start()
            connection = http.client.HTTPSConnection('127.0.0.1', server.server_port, timeout=5,
                        context=ssl.create_default_context(cafile=str(tls/'ca.pem')))
            try:
                connection.request('POST','/heartbeat',body=b'{"map":"ramsgate_01_persistent","token":"PRIVATE"}',
                                   headers={'Host':'tracking-prod.steelyard.ca'})
                reply = connection.getresponse()
                self.assertEqual(reply.status,404)
                self.assertEqual(reply.read(),b'')
                report = self.obs.report()
                self.assertTrue(report['ramsgate_self_report_seen'])
                self.assertFalse(report['client_join_verified'])
                self.assertNotIn('PRIVATE', json.dumps(report))
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(6)


class ExternalServerModeTests(unittest.TestCase):
    def test_external_mode_requires_normal_login_before_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'game'
            home = Path(tmp) / 'state'
            with self.assertRaisesRegex(ValueError, 'requires normal login'):
                preview.run_preview(root, home, 120, external_server=True)
            self.assertFalse(root.exists())
            self.assertFalse(home.exists())


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.user, self.system, self.game = root/'user', root/'system', root/'game'
        self.config = self.user/'Archon/Saved/Config/WindowsClient'
        self.config.mkdir(parents=True)
        (self.config/'Engine.ini').write_text('original')
        self.hosts = self.system/'System32/drivers/etc/hosts'
        self.hosts.parent.mkdir(parents=True)
        self.hosts.write_text('127.0.0.1 localhost\n')
        self.game.mkdir()
        self.home = self.user/'DauntlessReawakenedMapTest'
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {'LOCALAPPDATA':str(self.user),'SystemRoot':str(self.system)}))
        self.stack.enter_context(patch.object(preview,'check',return_value={'exe':str(self.game/'game.exe')}))
        self.stack.enter_context(patch.object(preview,'windows_ready'))
        self.stack.enter_context(patch.object(preview,'flush_dns'))
        self.stack.enter_context(patch.object(preview.socket,'getaddrinfo',return_value=[(None,None,None,None,('127.0.0.1',443))]))
        self.servers = self.stack.enter_context(patch.object(preview,'make_server',side_effect=lambda *a:Mock()))
        self.connection = self.stack.enter_context(patch.object(preview.http.client,'HTTPSConnection'))
        self.connection.return_value.getresponse.return_value.status=200
        self.connection.return_value.getresponse.return_value.read.return_value=b'{"experimental_login_port":true}'
        self.proc=Mock()
        self.proc.poll.return_value=0
        self.launch=self.stack.enter_context(patch.object(preview.subprocess,'Popen',return_value=self.proc))
        self.stack.enter_context(patch('builtins.input',return_value='MAP'))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
    def run_preview(self):
        preview.run_preview(self.game,self.home,30)
    def report(self):
        return json.loads((self.home/'active/map-preview-result.json').read_text())
    def test_complete_simulated_launch_restores(self):
        self.run_preview()
        self.assertEqual((self.config/'Engine.ini').read_text(),'original')
        self.assertTrue(self.report()['restored'])
        self.assertFalse(self.report()['game_server_started'])
        self.assertFalse((self.home/'research.sqlite3').exists())
        self.launch.assert_called_once()
    def test_config_failure_restores_before_any_launch(self):
        with patch.object(preview,'install_config',side_effect=ValueError('config rejected')):
            with self.assertRaises(ValueError): self.run_preview()
        self.assertEqual((self.config/'Engine.ini').read_text(),'original')
        self.assertTrue(self.report()['restored'])
        self.launch.assert_not_called()
    def test_launch_failure_restores(self):
        self.launch.side_effect=OSError('launch refused')
        with self.assertRaises(OSError): self.run_preview()
        self.assertTrue(self.report()['restored'])
    def test_failed_stop_withholds_restore(self):
        self.proc.poll.return_value=None
        with patch.object(preview,'watch',return_value={'termination':'time_limit'}), \
             patch.object(preview,'stop_owned',side_effect=OSError('still running')):
            with self.assertRaises(OSError): self.run_preview()
        self.assertFalse(self.report()['restored'])
        self.assertIn('GameDefaultMap=',(self.config/'Engine.ini').read_text())
    def test_legacy_pending_blocks_new_changes(self):
        old=self.user/'DauntlessReawakenedProbe/active/journal.json'
        old.parent.mkdir(parents=True)
        old.write_text('{"restored":false}')
        with self.assertRaises(ValueError): self.run_preview()
        self.assertFalse(self.home.exists())
        self.launch.assert_not_called()
    def test_decline_makes_no_state(self):
        with patch('builtins.input',return_value=''):
            self.run_preview()
        self.assertFalse(self.home.exists())
        self.launch.assert_not_called()
    def test_busy_port_makes_no_config_changes(self):
        self.servers.side_effect=OSError('port busy')
        with self.assertRaises(OSError): self.run_preview()
        self.assertEqual((self.config/'Engine.ini').read_text(),'original')
        self.assertFalse((self.home/'active').exists())
        self.launch.assert_not_called()
    def test_duration_rejected_before_changes(self):
        with self.assertRaises(ValueError): preview.run_preview(self.game,self.home,600)
        self.assertFalse(self.home.exists())


if __name__ == '__main__':
    unittest.main()
