"""Initial player-data reads: shape tests are not proof of working game systems."""
import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend.application import Application
from backend.database import Database
from backend.player_data import initial_loadouts, initial_progression, match_read, slot_counts
from backend.server import make_server


class PlayerDataHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.db = Database(self.path)
        self.app = Application(self.db, lab_key='fixture-key')
        self.http = make_server(self.app, port=0)
        self.worker = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': .01})
        self.worker.start()
        self.account = self.db.account('test-subject')['accountId']
        self.token = self.app.sessions.create(self.account).session_token
        self.character = self.db.create(self.account, 'Slayer', '{}')['id']

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join(timeout=5)
        self.db.close()
        self.tmp.cleanup()

    def request(self, service, path, method='GET', token=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request(method, path, headers={'Host': service + '.steelyard.ca',
                                               'Authorization': 'BEARER ' + (token or self.token)})
            response = conn.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
        finally:
            conn.close()

    def test_inventory_contains_only_documented_starter_catalogs(self):
        code, reply = self.request('dauntless-prod', f'/inventory/{self.account}/{self.character}')
        self.assertEqual(code, 200)
        self.assertEqual(set(reply), {'stackedItems', 'instancedItems'})
        self.assertEqual(reply['stackedItems'], [])
        self.assertEqual({x['catalogId'] for x in reply['instancedItems']}, {'WP_EB_TRAINING', 'LT_BASIC'})
        for item in reply['instancedItems']:
            self.assertEqual(set(item), {'catalogId', 'instanceId', 'quantity', 'updateVersion'})
            self.assertIs(type(item['quantity']), int)
            self.assertIs(type(item['updateVersion']), int)

    def test_inventory_bootstrap_is_once_and_persists(self):
        endpoint = f'/inventory/{self.account}/{self.character}'
        first = self.request('dauntless-prod', endpoint)[1]
        self.assertEqual(self.request('dauntless-prod', endpoint)[1], first)
        reopened = Database(self.path)
        try:
            self.assertEqual(reopened.bootstrap_inventory(self.account, self.character), first)
        finally:
            reopened.close()

    def test_inventory_rejects_wrong_account(self):
        other = self.db.account('other')['accountId']
        self.assertEqual(self.request('dauntless-prod', f'/inventory/{other}/{self.character}')[0], 401)

    def test_inventory_rejects_other_character(self):
        other = self.db.account('other')['accountId']
        character = self.db.create(other, 'Other', '{}')['id']
        self.assertEqual(self.request('dauntless-prod', f'/inventory/{self.account}/{character}')[0], 404)

    def test_inventory_rejects_invalid_session(self):
        self.assertEqual(self.request('dauntless-prod', f'/inventory/{self.account}/{self.character}', token='bad')[0], 401)

    def test_inventory_transaction_never_reports_fake_success(self):
        self.assertEqual(self.request('dauntless-prod', '/inventory', method='POST'), (503, None))

    def test_loadout_initial_values_are_safe_types(self):
        code, reply = self.request('loadout-prod', f'/loadout/{self.account}/{self.character}/all')
        self.assertEqual(code, 200)
        self.assertEqual(reply['code'], 'OK')
        payload = reply['payload']
        self.assertEqual(payload['active_index'], -1)
        self.assertEqual(payload['loadouts'], [])
        self.assertIs(payload['needs_migration'], False)
        self.assertGreater(payload['num_account_slots'] + payload['num_character_slots'], 0)
        for key in [*slot_counts(), 'active_index']:
            self.assertIs(type(payload[key]), int)
        self.assertIs(type(payload['persistent']['update_version']), int)

    def test_loadout_slot_counts_match(self):
        for path in [f'/loadout/{self.account}/slotcount',
                     f'/loadout/{self.account}/{self.character}/slotcount']:
            self.assertEqual(self.request('loadout-prod', path)[1]['payload'], slot_counts())

    def test_loadout_checks_character_ownership(self):
        self.assertEqual(self.request('loadout-prod', f'/loadout/{self.account}/unknown/all')[0], 404)

    def test_progression_tracks_and_objectives_have_numeric_code(self):
        for path in [f'/progression/{self.account}', f'/progression/objectives/{self.account}']:
            code, reply = self.request('progression-prod', path)
            self.assertEqual(code, 200)
            self.assertIs(type(reply['code']), int)
            self.assertEqual(reply['payload'], [])

    def test_config_paths_and_bounty_draft_types(self):
        reply = self.request('progression-prod', '/progression/config')[1]
        self.assertEqual(reply['payload'], {'paths': []})
        reply = self.request('progression-prod', f'/bounty/{self.account}')[1]
        self.assertNotIn('payload', reply)
        self.assertEqual(reply['bounties'], [])
        self.assertIs(type(reply['draft_data']['bronze_count']), int)

    def test_cooldowns_are_flat(self):
        self.assertEqual(self.request('progression-prod', f'/cooldown/{self.account}')[1], {'cooldowns': []})

    def test_each_documented_escalation_season_has_initial_state(self):
        for season in range(1, 7):
            code, reply = self.request('progression-prod', f'/escalation/ESC_SEASON_{season}/{self.account}')
            self.assertEqual(code, 200)
            self.assertEqual(reply['payload']['escalation_level'], 0)
            self.assertEqual(reply['payload']['talents_progress'], [])
        self.assertEqual(self.request('progression-prod', f'/escalation/ESC_SEASON_7/{self.account}')[0], 404)

    def test_data_reads_do_not_change_character_version(self):
        self.request('dauntless-prod', f'/inventory/{self.account}/{self.character}')
        self.request('loadout-prod', f'/loadout/{self.account}/{self.character}/all')
        self.assertEqual(self.db.get(self.account)[0]['updateVersion'], 0)

    def test_bootstrap_health_does_not_claim_progression_works(self):
        health = self.app.handle('GET', 'localhost', '/health', {}).payload
        self.assertFalse(health['game_compatible'])
        self.assertTrue(any('transactions' in reason for reason in health['blockers']))

    def test_unknown_progression_paths_and_saves_fail(self):
        for path, method in [(f'/pjm/{self.account}', 'GET'),
                             (f'/progression/{self.account}/UNKNOWN_TRACK', 'GET'),
                             (f'/escalation/ESC_SEASON_1/{self.account}', 'POST')]:
            self.assertEqual(self.request('progression-prod', path, method=method), (404, None))

    def test_session_account_binding_covers_every_read_family(self):
        other = self.db.account('other')['accountId']
        for service, path in [('progression-prod', f'/progression/{other}'),
                              ('progression-prod', f'/cooldown/{other}'),
                              ('progression-prod', f'/bounty/{other}'),
                              ('progression-prod', f'/escalation/ESC_SEASON_1/{other}'),
                              ('loadout-prod', f'/loadout/{other}/slotcount')]:
            self.assertEqual(self.request(service, path)[0], 401)


class PlayerDataUnitTests(unittest.TestCase):
    def test_bootstrap_is_safe_under_concurrent_reads(self):
        db = Database(':memory:')
        try:
            account = db.account('test')['accountId']
            character = db.create(account, 'Slayer', '{}')['id']
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                values = list(pool.map(lambda _: db.bootstrap_inventory(account, character), range(32)))
            self.assertTrue(all(value == values[0] for value in values))
            self.assertEqual(len(values[0]['instancedItems']), 2)
        finally:
            db.close()

    def test_loadout_responses_are_independent(self):
        result = initial_loadouts()
        result['payload']['persistent']['manual_emotes'].append('test')
        self.assertEqual(initial_loadouts()['payload']['persistent']['manual_emotes'], [])

    def test_routes_do_not_capture_other_services(self):
        self.assertIsNone(match_read('auth-prod', '/inventory/a/b'))
        self.assertIsNone(match_read('loadout-prod', '/loadout/a/b/all/extra'))
        self.assertIsNone(match_read('progression-prod', '/escalation/ESC_SEASON_99/a'))

    def test_unknown_bootstrap_shape_is_rejected(self):
        with self.assertRaises(ValueError):
            initial_progression('invented')

class PlayerDataTlsSequenceTests(unittest.TestCase):
    def test_tls_research_session_then_character_and_player_reads(self):
        # Tests the implemented subset only. Maintenance/tags/ban-check are NOT
        # part of this sequence; this does not establish full game login.
        import base64
        import ssl
        try:
            import cryptography
        except ImportError:
            self.skipTest('Install requirements-dev.txt for TLS tests')
        from tools.local_tls import generate
        from backend.server import tls_context
        with tempfile.TemporaryDirectory() as tmp:
            certs = generate(Path(tmp) / 'tls')
            db = Database(Path(tmp) / 'state.sqlite3')
            app = Application(db, allow_unverified_eos_sub=True)
            http_server = make_server(app, port=0, tls=tls_context(certs / 'server.pem', certs / 'server-key.pem'))
            worker = threading.Thread(target=http_server.serve_forever, kwargs={'poll_interval': .01})
            worker.start()
            context = ssl.create_default_context(cafile=str(certs / 'ca.pem'))
            def call(method, service, path, token, data=None):
                conn = http.client.HTTPSConnection('127.0.0.1', http_server.server_port,
                                                   context=context, timeout=3)
                try:
                    conn.request(method, path, body=json.dumps(data) if data is not None else None,
                                 headers={'Host': service + '.steelyard.ca',
                                          'Authorization': 'BEARER ' + token})
                    response = conn.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200)
                    return json.loads(body)
                finally:
                    conn.close()
            try:
                payload = base64.urlsafe_b64encode(b'{"sub":"tls-sequence-fixture"}').decode().rstrip('=')
                jwt = 'e30.' + payload + '.c2ln'
                reply = call('PUT', 'gamesession-prod', '/gamesession/epiceos', jwt)
                token = reply['payload']['sessiontoken']
                self.assertNotEqual(token, jwt)
                account = call('GET', 'auth-prod', '/accountinfo', token)['accountId']
                character = call('PUT', 'dauntless-prod', '/character', token, {'name': 'Slayer'})['id']
                inventory = call('GET', 'dauntless-prod', f'/inventory/{account}/{character}', token)
                self.assertEqual(len(inventory['instancedItems']), 2)
                loadouts = call('GET', 'loadout-prod', f'/loadout/{account}/{character}/all', token)
                self.assertEqual(loadouts['payload']['active_index'], -1)
                data = json.dumps({'PlayerAccountProgressStep': 'EnteredRamsgate'})
                call('POST', 'dauntless-prod', '/character', token,
                     {'characterId': character, 'data': data, 'updateVersion': 1})
                self.assertEqual(call('GET', 'dauntless-prod', '/character', token)[0]['updateVersion'], 1)
            finally:
                http_server.shutdown()
                http_server.server_close()
                worker.join(timeout=5)
                db.close()


if __name__ == '__main__':
    unittest.main()
