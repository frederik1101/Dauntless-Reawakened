"""Inventory gate tests use local/synthetic sessions, never the proprietary game."""
import base64
import http.client
import json
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from backend.application import Application
from backend.database import Database
from backend.mystic_login_port import LoginPortApplication
from backend.server import make_server, tls_context
from tools.local_tls import generate


class MigrationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.addCleanup(self.db.close)
        self.app = LoginPortApplication(self.db, lab_key='only-a-test-key')
        result = self.app.handle('POST', 'localhost', '/__lab/session',
                                {'X-Reawakened-Lab-Key': 'only-a-test-key'}, b'{"subject":"one"}')
        self.token = result.payload['payload']['sessiontoken']
        self.headers = {'Authorization': 'Bearer ' + self.token}
        self.account = self.app.sessions.resolve(self.token).account_id
        result = self.app.handle('PUT', 'dauntless-prod.steelyard.ca', '/character',
                                self.headers, b'{"name":"Synthetic"}', secure=True)
        self.character = result.payload['id']
        self.path = '/inventory/' + self.character + '/dauntlessrel-2.1.1:682875'

    def post(self, path=None, body=b'', *, secure=True, headers=None):
        return self.app.handle('POST', 'dauntless-prod.steelyard.ca', path or self.path,
                               self.headers if headers is None else headers, body, secure=secure)

    def test_no_migration_response_has_correct_shape(self):
        result = self.post()
        self.assertEqual(result.status, 200)
        self.assertEqual(result.payload, {'code': 'NONE', 'message': ''})
        self.assertEqual(result.route, 'ported-inventory-migration-none')

    def test_exact_retries_have_no_database_writes(self):
        before = self.db._db.total_changes
        original = self.db.get(self.account)
        for _ in range(4):
            self.assertEqual(self.post().status, 200)
        self.assertEqual(self.db._db.total_changes, before)
        self.assertEqual(self.db.get(self.account), original)

    def test_nonempty_character_must_be_owned(self):
        other = self.db.account('other')
        character = self.db.create(other['accountId'], 'Other', '{}')['id']
        result = self.post('/inventory/' + character + '/682875')
        self.assertEqual(result.status, 404)
        self.assertEqual(result.body(), b'')

    def test_unknown_character_fails(self):
        self.assertEqual(self.post('/inventory/unknown/682875').status, 404)

    def test_empty_character_single_profile_no_writes(self):
        before = self.db._db.total_changes
        self.assertEqual(self.post('/inventory//682875').status, 200)
        self.assertEqual(self.db._db.total_changes, before)

    def test_empty_character_no_profile_does_not_create_one(self):
        session = self.app.sessions.create(self.db.account('empty')['accountId'])
        result = self.post('/inventory//682875', headers={'Authorization': 'Bearer ' + session.session_token})
        self.assertEqual(result.status, 200)
        self.assertEqual(self.db.get(session.account_id), [])

    def test_empty_character_ambiguous_profile_fails(self):
        self.db.create(self.account, 'Second', '{}')
        self.assertEqual(self.post('/inventory//682875').status, 409)

    def test_authentication_is_required(self):
        for headers in ({}, {'Authorization': 'Bearer bad'}):
            self.assertEqual(self.post(headers=headers).status, 401)
        self.app.sessions.revoke(self.token)
        self.assertEqual(self.post().status, 401)

    def test_tls_is_required(self):
        self.assertEqual(self.post(secure=False).status, 503)

    def test_browser_origin_rejected(self):
        headers = {**self.headers, 'Origin': 'https://example.invalid'}
        self.assertEqual(self.post(headers=headers).status, 403)

    def test_unknown_body_and_transaction_intents_rejected(self):
        for body in (b'{"transactionId":"a"}', b'{"addInstancedItems":[]}',
                     b'{"metadata":"unknown"}', b'[]', b'null'):
            result = self.post(body=body)
            self.assertEqual(result.status, 422)
            self.assertEqual(result.route, 'inventory-migration-body-unsupported')
            self.assertEqual(result.body(), b'')

    def test_empty_object_accepted(self):
        self.assertEqual(self.post(body=b'{}').status, 200)

    def test_wrong_service_and_methods_do_not_match(self):
        for method, service in (('PUT', 'dauntless-prod'), ('DELETE', 'dauntless-prod'),
                                ('POST', 'gamesession-prod')):
            result = self.app.handle(method, service + '.steelyard.ca', self.path,
                                     self.headers, secure=True)
            self.assertEqual(result.status, 404)

    def test_baseline_remains_unimplemented(self):
        self.assertEqual(Application(self.db).handle('POST', 'dauntless-prod.steelyard.ca',
                         self.path, self.headers, secure=True).status, 404)

    def test_bare_transaction_route_not_faked(self):
        self.assertEqual(self.post('/inventory', body=b'{"transactionId":"a"}').status, 503)

    def test_get_inventory_retains_original_semantics(self):
        result = self.app.handle('GET', 'dauntless-prod.steelyard.ca',
                                '/inventory/' + self.account + '/' + self.character,
                                self.headers, secure=True)
        self.assertEqual(result.status, 200)
        self.assertIn('instancedItems', result.payload)
        self.assertNotIn('code', result.payload)

    def test_health_does_not_claim_game_server_or_login_completion(self):
        payload = self.app.handle('GET', 'localhost', '/health', {}).payload
        self.assertTrue(payload['inventory_migration_port_enabled'])
        self.assertFalse(payload['game_compatible'])


class MigrationTlsTests(unittest.TestCase):
    def test_synthetic_login_migration_inventory_restart_sequence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tls = generate(root / 'tls')
            db_path = root / 'test.sqlite3'
            db = Database(db_path)
            app = LoginPortApplication(db, allow_unverified_eos_sub=True)
            server = make_server(app, '127.0.0.1', 0,
                                 tls_context(tls / 'server.pem', tls / 'server-key.pem'))
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={'poll_interval': .01}, daemon=True)
            worker.start()
            context = ssl.create_default_context(cafile=str(tls / 'ca.pem'))

            def call(method, service, endpoint, token=None, data=None):
                connection = http.client.HTTPSConnection('127.0.0.1', server.server_port,
                                                         context=context, timeout=5)
                headers = {'Host': service + '.steelyard.ca'}
                if token:
                    headers['Authorization'] = 'Bearer ' + token
                try:
                    connection.request(method, endpoint,
                        body=None if data is None else json.dumps(data).encode(), headers=headers)
                    response = connection.getresponse()
                    data = response.read()
                    self.assertEqual(response.status, 200, (service, response.status))
                    return json.loads(data)
                finally:
                    connection.close()

            subject = 'synthetic-subject-not-real'
            payload = base64.urlsafe_b64encode(json.dumps({'sub': subject}).encode()).rstrip(b'=')
            fake = 'header.' + payload.decode() + '.signature'
            try:
                with self.assertLogs('reawakened.requests', 'INFO') as captured:
                    call('GET', 'gamesession-prod', '/account/link/epic/synthetic')
                    call('POST', 'login-queue-prod', '/login')
                    session = call('PUT', 'gamesession-prod', '/gamesession/epiceos', fake)
                    token = session['payload']['sessiontoken']
                    account = call('GET', 'auth-prod', '/accountinfo', token)['accountId']
                    created = call('PUT', 'dauntless-prod', '/character', token, {'name': 'Synthetic'})
                    path = '/inventory/' + created['id'] + '/dauntlessrel-2.1.1:682875'
                    self.assertEqual(call('POST', 'dauntless-prod', path, token),
                                     {'code': 'NONE', 'message': ''})
                    # A second migration acknowledgement grants nothing.
                    call('POST', 'dauntless-prod', path, token)
                    inventory = call('GET', 'dauntless-prod',
                                     '/inventory/' + account + '/' + created['id'], token)
                    self.assertEqual(len(inventory['instancedItems']), 2)
                log = '\n'.join(captured.output)
                self.assertIn('route=ported-inventory-migration-none', log)
                self.assertIn('endpoint=/inventory/{character}/{build}', log)
                self.assertIn('endpoint=/inventory/{account}/{character}', log)
                for private in (subject, fake, token, account, created['id'], 'dauntlessrel-2.1.1:682875'):
                    self.assertNotIn(private, log)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
                db.close()
            reopened = Database(db_path)
            try:
                self.assertEqual(reopened.get(account)[0]['id'], created['id'])
                self.assertEqual(reopened.bootstrap_inventory(account, created['id']), inventory)
            finally:
                reopened.close()


if __name__ == '__main__':
    unittest.main()
