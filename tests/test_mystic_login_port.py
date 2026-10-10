"""Port tests use synthetic identities. Passing them is NOT an Epic/client login."""
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
from backend.mystic_login_port import LoginPortApplication, SOURCE_URL
from backend.server import make_server, tls_context
from tools.local_tls import generate


def fake_jwt(sub, nonce='one'):
    payload = base64.urlsafe_b64encode(json.dumps({'sub': sub, 'nonce': nonce}).encode()).rstrip(b'=')
    return 'header.' + payload.decode() + '.fakeSignature'


class PortTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.app = LoginPortApplication(self.db, lab_key='test-only')
        self.addCleanup(self.db.close)
        response = self.app.handle('POST', 'localhost', '/__lab/session',
                                   {'X-Reawakened-Lab-Key': 'test-only'}, b'{"subject":"one"}')
        self.token = response.payload['payload']['sessiontoken']
        self.headers = {'Authorization': 'BEARER ' + self.token}
        self.account = self.app.sessions.resolve(self.token).account_id

    def request(self, method, service, path, data=None, **kwargs):
        body = b'' if data is None else json.dumps(data).encode()
        return self.app.handle(method, service + '.steelyard.ca', path, self.headers, body,
                               secure=kwargs.get('secure', True))

    def test_base_still_rejects_unverified_routes(self):
        response = Application(self.db).handle('GET', 'auth-prod.steelyard.ca', '/tags', {})
        self.assertEqual(response.status, 404)
        self.assertEqual(response.body(), b'')

    def test_tags_uses_session_account(self):
        self.assertEqual(self.request('GET', 'auth-prod', '/tags').payload,
                         {'accountId': self.account, 'tags': []})

    def test_ban_check_is_typed(self):
        payload = self.request('GET', 'auth-prod', '/isbanned').payload
        self.assertIs(payload['isBanned'], False)

    def test_port_requires_tls(self):
        self.assertEqual(self.request('GET', 'auth-prod', '/tags', secure=False).status, 503)

    def test_port_requires_session(self):
        reply = self.app.handle('GET', 'auth-prod.steelyard.ca', '/tags', {}, secure=True)
        self.assertEqual(reply.status, 401)

    def test_unknown_token_rejected(self):
        self.headers['Authorization'] = 'Bearer unknown'
        self.assertEqual(self.request('GET', 'auth-prod', '/isbanned').status, 401)

    def test_revoked_token_rejected(self):
        self.app.sessions.revoke(self.token)
        self.assertEqual(self.request('GET', 'auth-prod', '/tags').status, 401)

    def test_public_account_is_self_only(self):
        result = self.request('POST', 'auth-prod', '/accountinfo/public', {'accountId': self.account})
        self.assertEqual(result.payload['accountId'], self.account)
        self.assertEqual(result.payload['linkedAccounts'][0]['accountType'], 'epic')

    def test_public_account_does_not_substitute_self_for_other(self):
        reply = self.request('POST', 'auth-prod', '/accountinfo/public', {'accountId': 'someone-else'})
        self.assertEqual(reply.status, 401)
        self.assertEqual(reply.body(), b'')

    def test_public_account_invalid_body(self):
        self.assertEqual(self.request('POST', 'auth-prod', '/accountinfo/public', {}).status, 400)

    def test_migration_status_is_211_flat_not_upstream_wrapped(self):
        payload = self.request('GET', 'migration-prod', '/migration/status').payload
        self.assertEqual(payload, {'migration_finished': True, 'migration_failed': False})
        self.assertNotIn('payload', payload)

    def test_migration_trigger_has_no_external_migration(self):
        before = self.db.get(self.account)
        self.assertEqual(self.request('POST', 'migration-prod', '/migration/trigger').status, 200)
        self.assertEqual(self.db.get(self.account), before)

    def test_wrong_service_does_not_match(self):
        self.assertEqual(self.request('GET', 'dauntless-prod', '/tags').status, 404)

    def test_unknown_post_returns_bodyless_404(self):
        self.assertEqual(self.request('POST', 'auth-prod', '/not-known').body(), b'')
        self.assertEqual(self.request('POST', 'auth-prod', '/not-known').status, 404)

    def test_browser_origin_rejected(self):
        self.headers['Origin'] = 'https://example.invalid'
        self.assertEqual(self.request('GET', 'auth-prod', '/tags').status, 403)

    def test_health_does_not_claim_game_login(self):
        payload = self.app.handle('GET', 'localhost', '/health', {}).payload
        self.assertFalse(payload['game_compatible'])
        self.assertTrue(payload['experimental_login_port'])
        self.assertEqual(payload['source_url'], SOURCE_URL)

    def test_notices_available_without_account(self):
        reply = self.app.handle('GET', 'localhost', '/__lab/notices', {})
        self.assertEqual(reply.payload['license'], 'AGPL-3.0-only')
        self.assertIn('Pranav Karande', reply.payload['attribution'])

    def test_maintenance_is_not_silently_assumed(self):
        self.assertEqual(self.request('GET', 'login-queue-prod', '/maintenance/status').status, 404)

    def test_explicit_maintenance_experiment(self):
        app = LoginPortApplication(self.db, maintenance_response={'isMaintenance': False})
        reply = app.handle('GET', 'login-queue-prod.steelyard.ca', '/maintenance/status', {}, secure=True)
        self.assertEqual(reply.payload, {'isMaintenance': False})
        self.assertEqual(reply.route, 'experimental-maintenance')

    def test_maintenance_rejects_non_object(self):
        with self.assertRaises(ValueError):
            LoginPortApplication(self.db, maintenance_response=[])

    def test_maintenance_payload_is_copied(self):
        original = {'isMaintenance': False}
        app = LoginPortApplication(self.db, maintenance_response=original)
        original['isMaintenance'] = True
        reply = app.handle('GET', 'login-queue-prod.steelyard.ca', '/maintenance/status', {}, secure=True)
        self.assertIs(reply.payload['isMaintenance'], False)


class PortTlsTests(unittest.TestCase):
    def test_synthetic_login_sequence_over_verified_tls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tls = generate(root / 'tls')
            db = Database(root / 'characters.sqlite3')
            app = LoginPortApplication(db, allow_unverified_eos_sub=True,
                                       maintenance_response={'isMaintenance': False})
            server = make_server(app, '127.0.0.1', 0, tls_context(tls / 'server.pem', tls / 'server-key.pem'))
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            worker.start()
            context = ssl.create_default_context(cafile=str(tls / 'ca.pem'))

            def call(method, service, path, data=None, token=None):
                conn = http.client.HTTPSConnection('127.0.0.1', server.server_port, context=context, timeout=5)
                headers = {'Host': service + '.steelyard.ca'}
                if token:
                    headers['Authorization'] = 'BEARER ' + token
                try:
                    conn.request(method, path, body=None if data is None else json.dumps(data).encode(), headers=headers)
                    response = conn.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200, (service, path, response.status))
                    return json.loads(body)
                finally:
                    conn.close()
            try:
                self.assertEqual(call('POST', 'login-queue-prod', '/login')['state'], 'OPEN')
                call('GET', 'gamesession-prod', '/features/platform/win')
                call('GET', 'login-queue-prod', '/maintenance/status')
                call('GET', 'gamesession-prod', '/account/link/epic/synthetic')
                result = call('PUT', 'gamesession-prod', '/gamesession/epiceos', token=fake_jwt('synthetic'))
                token = result['payload']['sessiontoken']
                self.assertNotEqual(token, fake_jwt('synthetic'))
                account = call('GET', 'auth-prod', '/accountinfo', token=token)['accountId']
                self.assertEqual(call('GET', 'auth-prod', '/tags', token=token)['accountId'], account)
                self.assertIs(call('GET', 'auth-prod', '/isbanned', token=token)['isBanned'], False)
                call('GET', 'migration-prod', '/migration/status', token=token)
                call('POST', 'auth-prod', '/accountinfo/public', {'accountId': account}, token)
                self.assertEqual(call('GET', 'dauntless-prod', '/character', token=token), [])
                created = call('PUT', 'dauntless-prod', '/character', {'name': 'SyntheticSlayer'}, token)
                call('POST', 'dauntless-prod', '/character',
                     {'characterId': created['id'], 'data': '{"PlayerAccountProgressStep":"EnteredRamsgate"}',
                      'updateVersion': 1}, token)
                # Token rotation must not create a new account or lose the character.
                second = call('PUT', 'gamesession-prod', '/gamesession/epiceos', token=fake_jwt('synthetic', 'two'))
                second_token = second['payload']['sessiontoken']
                self.assertNotEqual(token, second_token)
                characters = call('GET', 'dauntless-prod', '/character', token=second_token)
                self.assertEqual(characters[0]['id'], created['id'])
                self.assertEqual(characters[0]['updateVersion'], 1)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
                db.close()
