"""Real loopback HTTP tests; never contact Epic or launch a game."""
import base64
import concurrent.futures
import http.client
import json
import socket
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from backend.application import Application, target
from backend.database import Database, VersionConflict, character_data
from backend.server import make_server, tls_context
from backend.session_store import SessionStore, unverified_subject


def fake_jwt(subject, suffix='fixture'):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    return encode({'alg': 'RS256'}) + '.' + encode({'sub': subject}) + '.' + suffix


class HttpContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'state.sqlite3'
        self.db = Database(self.path)
        self.app = Application(self.db, lab_key='test-only-key')
        self.http = make_server(self.app, port=0)
        self.worker = threading.Thread(target=self.http.serve_forever, kwargs={'poll_interval': .01})
        self.worker.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join(timeout=5)
        self.db.close()
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None, host='127.0.0.1'):
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            body = json.dumps(data).encode() if data is not None else None
            connection.request(method, path, body=body, headers={'Host': host, **(headers or {})})
            response = connection.getresponse()
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
        finally:
            connection.close()

    def login(self, subject='test-player'):
        status, result = self.request('POST', '/__lab/session', {'subject': subject},
                                     {'X-Reawakened-Lab-Key': 'test-only-key'})
        self.assertEqual(status, 200)
        return {'Authorization': 'BEARER ' + result['payload']['sessiontoken']}

    def test_health_admits_game_is_not_ready(self):
        self.assertFalse(self.request('GET', '/health')[1]['game_compatible'])

    def test_real_host_login_queue(self):
        code, reply = self.request('POST', '/login', host='login-queue-prod.steelyard.ca')
        self.assertEqual(code, 200)
        self.assertEqual(set(reply), {'state', 'error_code', 'message', 'title', 'timeout'})

    def test_prefixed_features(self):
        self.assertTrue(self.request('GET', '/gamesession-prod/features/platform/win')[1]['crossplay'])

    def test_real_host_linking(self):
        self.assertTrue(self.request('GET', '/account/link/epic/example',
                                     host='gamesession-prod.steelyard.ca')[1]['payload']['isLinked'])

    def test_unknown_methods_return_bodyless_404(self):
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']:
            with self.subTest(method=method):
                self.assertEqual(self.request(method, '/unknown'), (404, None))

    def test_unverified_known_routes_stay_unimplemented(self):
        for host, path in [('auth-prod', '/tags'), ('auth-prod', '/isbanned'),
                           ('login-queue-prod', '/maintenance/status')]:
            self.assertEqual(self.request('GET', path, host=host + '.steelyard.ca'), (404, None))

    def test_lab_endpoint_requires_key(self):
        self.assertEqual(self.request('POST', '/__lab/session', {})[0], 401)

    def test_account_requires_session(self):
        self.assertEqual(self.request('GET', '/auth-prod/accountinfo'), (401, None))
        self.assertEqual(self.request('GET', '/auth-prod/accountinfo',
                                     headers={'Authorization': 'BEARER wrong'}), (401, None))

    def test_session_identity_is_stable(self):
        one = self.request('GET', '/auth-prod/accountinfo', headers=self.login())[1]
        two = self.request('GET', '/auth-prod/accountinfo', headers=self.login())[1]
        self.assertEqual(one, two)
        other = self.request('GET', '/auth-prod/accountinfo', headers=self.login('other'))[1]
        self.assertNotEqual(one['accountId'], other['accountId'])

    def test_character_create_save_restart(self):
        auth = self.login()
        account = self.request('GET', '/auth-prod/accountinfo', headers=auth)[1]['accountId']
        _, created = self.request('PUT', '/character', {'name': 'Slayer'}, auth,
                                  host='dauntless-prod.steelyard.ca')
        data = json.dumps({'PlayerAccountProgressStep': 'EnteredRamsgate', 'Fixture': 'value'})
        body = {'characterId': created['id'], 'data': data, 'updateVersion': 7}
        self.assertEqual(self.request('POST', '/character', body, auth,
                                      host='dauntless-prod.steelyard.ca'), (200, {'data': data}))
        reopened = Database(self.path)
        try:
            record = reopened.get(account)[0]
            self.assertEqual(record['data'], data)
            self.assertEqual(record['updateVersion'], 7)
        finally:
            reopened.close()

    def test_character_isolation(self):
        auth = self.login('a')
        _, record = self.request('PUT', '/dauntless-prod/character', {'name': 'Slayer'}, auth)
        other = self.login('b')
        self.assertEqual(self.request('GET', '/dauntless-prod/character', headers=other)[1], [])
        self.assertEqual(self.request('POST', '/dauntless-prod/character',
                                     {'characterId': record['id'], 'data': '{}', 'updateVersion': 1}, other)[0], 400)

    def test_reject_wrong_character_id_field(self):
        auth = self.login()
        self.assertEqual(self.request('POST', '/dauntless-prod/character',
                                     {'id': 'wrong-field', 'data': '{}', 'updateVersion': 1}, auth)[0], 400)

    def test_version_conflict(self):
        auth = self.login()
        _, record = self.request('PUT', '/dauntless-prod/character', {'name': 'Slayer'}, auth)
        body = {'characterId': record['id'], 'data': '{}', 'updateVersion': 1}
        self.assertEqual(self.request('POST', '/dauntless-prod/character', body, auth)[0], 200)
        self.assertEqual(self.request('POST', '/dauntless-prod/character', body, auth)[0], 409)

    def test_revoked_token_rejected(self):
        auth = self.login()
        self.assertEqual(self.request('DELETE', '/__lab/session', headers=auth)[0], 204)
        self.assertEqual(self.request('GET', '/auth-prod/accountinfo', headers=auth)[0], 401)

    def test_eos_extraction_is_disabled_by_default(self):
        self.assertEqual(self.request('PUT', '/gamesession/epiceos',
                                     headers={'Authorization': 'BEARER ' + fake_jwt('user')},
                                     host='gamesession-prod.steelyard.ca')[0], 503)

    def test_browser_and_foreign_host_rejected(self):
        self.assertEqual(self.request('GET', '/health', headers={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/health', host='example.com')[0], 400)

    def test_log_never_contains_tokens_or_queries(self):
        secret = 'SENSITIVE-FIXTURE-123456'
        with self.assertLogs('reawakened.requests', level='INFO') as captured:
            self.request('GET', '/auth-prod/accountinfo?token=' + secret,
                         headers={'Authorization': 'BEARER ' + secret})
        self.assertNotIn(secret, '\n'.join(captured.output))
        self.assertIn('accountinfo', '\n'.join(captured.output))

    def test_status_banner_has_boolean_and_languages(self):
        code, reply = self.request('GET', '/dauntless-status', host='steelyard.online')
        self.assertEqual(code, 200)
        self.assertEqual(len(reply), 9)
        self.assertIs(reply['show-status'], False)

    def test_entitlements_object(self):
        self.assertEqual(self.request('GET', '/entitlementsv2', headers=self.login(),
                                      host='auth-prod.steelyard.ca')[1], {'entitlements': []})

    def test_invalid_body_types_do_not_crash(self):
        auth = self.login()
        for value in [[], 'text', True, 5, {'name': []}, {'name': '\n'}, {'name': ''}]:
            self.assertEqual(self.request('PUT', '/dauntless-prod/character', value, auth)[0], 400)
        self.assertEqual(self.request('GET', '/health')[0], 200)

    def test_oversized_body_rejected_before_read(self):
        self.assertEqual(self.request('POST', '/unknown', headers={'Content-Length': '1048577'})[0], 413)

    def test_transfer_encoding_rejected(self):
        self.assertEqual(self.request('POST', '/unknown', headers={'Transfer-Encoding': 'chunked'})[0], 400)


class StorageAndSessionTests(unittest.TestCase):
    def test_expiry_and_limit(self):
        now = [0.0]
        sessions = SessionStore(ttl=5, limit=1, clock=lambda: now[0])
        first = sessions.create('account')
        with self.assertRaises(OverflowError):
            sessions.create('account')
        now[0] = 5
        self.assertIsNone(sessions.resolve(first.session_token))
        self.assertIsNotNone(sessions.create('account'))

    def test_repr_redacts_token(self):
        session = SessionStore().create('account')
        self.assertNotIn(session.session_token, repr(session))

    def test_unverified_subject_not_raw_token(self):
        self.assertEqual(unverified_subject(fake_jwt('same', 'signatureA')),
                         unverified_subject(fake_jwt('same', 'signatureB')))

    def test_bad_jwt_rejected(self):
        for token in ['', 'not.a.jwt', '..', 'x' * 17000, fake_jwt(None), fake_jwt('a\nb')]:
            with self.subTest(token=token[:20]), self.assertRaises(ValueError):
                unverified_subject(token)

    def test_data_string_types_required(self):
        for data in ['[]', 'null', '{"x":true}', '{"x":1}', '{}not-json', 7]:
            with self.subTest(data=data), self.assertRaises((ValueError, TypeError)):
                character_data(data)
        self.assertEqual(character_data('{"x":"true"}'), '{"x":"true"}')

    def test_concurrent_character_creation(self):
        db = Database(':memory:')
        try:
            account = db.account('test')['accountId']
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                records = list(pool.map(lambda _: db.create(account, 'Slayer', '{}'), range(20)))
            self.assertEqual(len({r['id'] for r in records}), 20)
            self.assertEqual(len(db.get(account)), 20)
        finally:
            db.close()

    def test_boolean_version_rejected(self):
        db = Database(':memory:')
        try:
            account = db.account('test')['accountId']
            record = db.create(account, 'Slayer', '{}')
            with self.assertRaises(ValueError):
                db.save(account, record['id'], '{}', True)
        finally:
            db.close()

    def test_loopback_binding_only(self):
        with self.assertRaises(ValueError):
            make_server(None, '0.0.0.0', 0)

    def test_host_routing_rejects_bad_targets(self):
        for host, path in [('example.com', '/'), ('user@127.0.0.1', '/'),
                           ('127.0.0.1', 'http://example.com/login')]:
            with self.assertRaises(ValueError):
                target(host, path)

    def test_research_exchange_stable_but_explicit(self):
        db = Database(':memory:')
        try:
            app = Application(db, allow_unverified_eos_sub=True)
            result = app.handle('PUT', 'gamesession-prod.steelyard.ca', '/gamesession/epiceos',
                                {'Authorization': 'BEARER ' + fake_jwt('test')}, secure=True)
            self.assertEqual(result.status, 200)
            token = result.payload['payload']['sessiontoken']
            self.assertIsNotNone(app.sessions.resolve(token))
            self.assertEqual(app.handle('PUT', 'gamesession-prod.steelyard.ca', '/gamesession/epiceos',
                                        {'Authorization': 'BEARER ' + fake_jwt('test')}, secure=False).status, 503)
        finally:
            db.close()


class TlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import cryptography
        except ImportError:
            raise unittest.SkipTest('Install requirements-dev.txt to run real TLS tests')
        from tools.local_tls import generate
        cls.tmp = tempfile.TemporaryDirectory()
        cls.certs = generate(Path(cls.tmp.name) / 'tls')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_tls_certificates_are_not_overwritten(self):
        from tools.local_tls import generate
        with self.assertRaises(FileExistsError):
            generate(self.certs)
        self.assertFalse((self.certs / 'ca-key.pem').exists())

    def _tls_roundtrip(self, host):
        db = Database(':memory:')
        app = Application(db, allow_unverified_eos_sub=True)
        server = None
        worker = None
        try:
            try:
                server = make_server(app, host, 0, tls_context(self.certs / 'server.pem', self.certs / 'server-key.pem'))
            except OSError:
                if host == '::1':
                    self.skipTest('IPv6 loopback unavailable in this environment')
                raise
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            worker.start()
            context = ssl.create_default_context(cafile=str(self.certs / 'ca.pem'))
            # Real handshake with a game-service SNI name, without DNS or hosts changes.
            with socket.create_connection((host, server.server_port), timeout=3) as raw:
                with context.wrap_socket(raw, server_hostname='gamesession-prod.steelyard.ca') as stream:
                    stream.sendall(('PUT /gamesession/epiceos HTTP/1.0\r\n'
                                    'Host: gamesession-prod.steelyard.ca\r\n'
                                    'Authorization: BEARER ' + fake_jwt('tls-test') + '\r\n'
                                    'Content-Length: 0\r\n\r\n').encode())
                    response = http.client.HTTPResponse(stream)
                    response.begin()
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read())
                    self.assertIn('sessiontoken', payload['payload'])
        finally:
            if worker:
                server.shutdown()
            if server:
                server.server_close()
            if worker:
                worker.join(timeout=5)
            db.close()

    def test_ipv4_https_with_real_sni_and_session(self):
        self._tls_roundtrip('127.0.0.1')

    def test_ipv6_https_with_real_sni_and_session(self):
        self._tls_roundtrip('::1')

    def test_untrusted_certificate_rejected(self):
        db = Database(':memory:')
        server = make_server(Application(db), port=0,
                             tls=tls_context(self.certs / 'server.pem', self.certs / 'server-key.pem'))
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        worker.start()
        try:
            context = ssl.create_default_context()
            with socket.create_connection(('127.0.0.1', server.server_port), timeout=3) as raw:
                with self.assertRaises(ssl.SSLCertVerificationError):
                    context.wrap_socket(raw, server_hostname='localhost')
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
            db.close()


if __name__ == '__main__':
    unittest.main()
