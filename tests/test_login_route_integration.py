"""Real HTTP/TLS checks with synthetic identities, NOT proof of game login."""
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


class LoginAliasTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.addCleanup(self.db.close)
        self.app = LoginPortApplication(self.db)
        self.host = 'gamesession-prod.steelyard.ca'
        self.path = '/account/link/epiceos/synthetic-player'

    def test_candidate_alias_returns_existing_wrapped_shape(self):
        result = self.app.handle('GET', self.host, self.path, {}, secure=True)
        self.assertEqual(result.status, 200)
        self.assertEqual(result.payload, {'code': 'OK', 'message': '', 'payload': {'isLinked': True}})
        self.assertEqual(result.route, 'candidate-account-link-epiceos')

    def test_default_application_does_not_enable_candidate(self):
        result = Application(self.db).handle('GET', self.host, self.path, {}, secure=True)
        self.assertEqual(result.status, 404)
        self.assertEqual(result.body(), b'')

    def test_candidate_requires_tls(self):
        self.assertEqual(self.app.handle('GET', self.host, self.path, {}).status, 503)

    def test_original_epic_route_is_unchanged(self):
        result = self.app.handle('GET', self.host, '/account/link/epic/synthetic-player', {}, secure=True)
        self.assertEqual(result.status, 200)
        self.assertEqual(result.route, 'account-link')

    def test_wrong_method_or_service_is_not_accepted(self):
        for method, host in [('POST', self.host), ('PUT', self.host), ('GET', 'auth-prod.steelyard.ca')]:
            with self.subTest(method=method, host=host):
                result = self.app.handle(method, host, self.path, {}, secure=True)
                self.assertEqual(result.status, 404)
                self.assertEqual(result.body(), b'')

    def test_link_does_not_issue_session_or_unlock_account(self):
        linked = self.app.handle('GET', self.host, self.path, {}, secure=True)
        self.assertNotIn('sessiontoken', json.dumps(linked.payload))
        result = self.app.handle('GET', 'auth-prod.steelyard.ca', '/accountinfo', {}, secure=True)
        self.assertEqual(result.status, 401)

    def test_browser_rejection_precedes_candidate(self):
        result = self.app.handle('GET', self.host, self.path, {'Origin': 'null'}, secure=True)
        self.assertEqual(result.status, 403)

    def test_health_still_denies_game_compatibility(self):
        result = self.app.handle('GET', 'localhost', '/health', {})
        self.assertFalse(result.payload['game_compatible'])


class RequestLogHttpTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.app = LoginPortApplication(self.db)
        self.server = make_server(self.app, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(5)
        self.db.close()

    def call(self, method, host, path, body=b'', extra_headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            with self.assertLogs('reawakened.requests', level='INFO') as captured:
                connection.request(method, path, body=body,
                                   headers={'Host': host, **(extra_headers or {})})
                response = connection.getresponse()
                content = response.read()
            return response.status, content, '\n'.join(captured.output)
        finally:
            connection.close()

    def test_unknown_post_distinguishes_heartbeat_without_inventing_success(self):
        status, body, logs = self.call('POST', 'tracking-prod.steelyard.ca', '/heartbeat?token=SECRET',
                                       b'{"private":"BODYSECRET"}', {'Authorization': 'Bearer HEADERSECRET'})
        self.assertEqual((status, body), (404, b''))
        self.assertIn('service=tracking-prod endpoint=/heartbeat transport=http', logs)
        for secret in ('SECRET', 'BODYSECRET', 'HEADERSECRET', '?token', 'Authorization'):
            self.assertNotIn(secret, logs)

    def test_unknown_get_identifies_account_link_family_without_provider_or_id(self):
        status, body, logs = self.call('GET', 'gamesession-prod.steelyard.ca',
                                       '/account/link/private-provider/private-id?code=SECRET')
        self.assertEqual((status, body), (404, b''))
        self.assertIn('endpoint=/account/link/{provider}/{id}', logs)
        self.assertNotIn('private-provider', logs)
        self.assertNotIn('private-id', logs)
        self.assertNotIn('SECRET', logs)

    def test_invalid_host_and_raw_path_are_not_logged(self):
        status, _, logs = self.call('GET', 'private-host.example', '/private-path?token=SECRET')
        self.assertEqual(status, 400)
        self.assertIn('service=unrecognised endpoint=<redacted>', logs)
        self.assertNotIn('private', logs)
        self.assertNotIn('SECRET', logs)

    def test_unknown_paths_are_grouped_without_raw_logging(self):
        status, _, logs = self.call('POST', 'auth-prod.steelyard.ca', '/private/path?x=SECRET')
        self.assertEqual(status, 404)
        self.assertIn('endpoint=<redacted>', logs)
        self.assertRegex(logs, r'route_key=[0-9a-f]{16}')
        self.assertNotIn('/private/path', logs)


class LoginAliasTlsTests(unittest.TestCase):
    def test_candidate_then_synthetic_session_and_character_over_tls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tls = generate(root / 'tls')
            db = Database(root / 'test.sqlite3')
            app = LoginPortApplication(db, allow_unverified_eos_sub=True,
                                       maintenance_response={'isMaintenance': False})
            server = make_server(app, port=0, tls=tls_context(tls / 'server.pem', tls / 'server-key.pem'))
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            worker.start()
            context = ssl.create_default_context(cafile=str(tls / 'ca.pem'))

            def call(method, service, path, token=None, data=None):
                connection = http.client.HTTPSConnection('127.0.0.1', server.server_port,
                                                          context=context, timeout=5)
                headers = {'Host': service + '.steelyard.ca'}
                if token:
                    headers['Authorization'] = 'BEARER ' + token
                try:
                    connection.request(method, path, headers=headers,
                                       body=None if data is None else json.dumps(data).encode())
                    response = connection.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, 200)
                    return json.loads(body)
                finally:
                    connection.close()
            try:
                with self.assertLogs('reawakened.requests', level='INFO') as captured:
                    call('GET', 'gamesession-prod', '/features/platform/win')
                    call('GET', 'gamesession-prod', '/account/link/epiceos/PRIVATE-SYNTHETIC-ID')
                    claims = base64.urlsafe_b64encode(b'{"sub":"PRIVATE-SYNTHETIC-ID"}').decode().rstrip('=')
                    fake_jwt = 'header.' + claims + '.fakeSignature'
                    token = call('PUT', 'gamesession-prod', '/gamesession/epiceos', fake_jwt)['payload']['sessiontoken']
                    account = call('GET', 'auth-prod', '/accountinfo', token)['accountId']
                    self.assertEqual(call('GET', 'auth-prod', '/tags', token)['accountId'], account)
                    self.assertIs(call('GET', 'auth-prod', '/isbanned', token)['isBanned'], False)
                    created = call('PUT', 'dauntless-prod', '/character', token, {'name': 'PRIVATE-NAME'})
                    characters = call('GET', 'dauntless-prod', '/character', token)
                    self.assertEqual(characters[0]['id'], created['id'])
                logs = '\n'.join(captured.output)
                self.assertIn('route=candidate-account-link-epiceos status=200', logs)
                self.assertIn('endpoint=/account/link/epiceos/{id} transport=https', logs)
                self.assertIn('route=epiceos-session-research status=200', logs)
                for secret in ('PRIVATE-SYNTHETIC-ID', 'PRIVATE-NAME', fake_jwt, token, account, created['id']):
                    self.assertNotIn(secret, logs)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
                db.close()


if __name__ == '__main__':
    unittest.main()
