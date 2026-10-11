"""HTTP/TLS integration for CITY routing. Synthetic hosts are NOT real game servers."""
from dataclasses import replace
import http.client
import json
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from backend.database import Database
from backend.mystic_login_port import LoginPortApplication
from backend.ramsgate_application import RamsgateApplication
from backend.ramsgate_matchmaker import HostAssignment, RAMSGATE_MAP, RamsgateMatchmaker
from backend.server import make_server, tls_context
from tools.local_tls import generate


class SyntheticHost:
    def __init__(self):
        self.alive = True
        self.ready = False
        self.generation = 'synthetic-generation'
        self.calls = 0
        self.released = []

    def reserve(self, player, candidate, request):
        self.calls += 1
        if not self.ready:
            return None
        return HostAssignment('synthetic-instance', 'synthetic-game-session', self.generation,
                              request.build_id, RAMSGATE_MAP, 8777, 110.0)

    def refresh(self, assignment, player, candidate):
        return replace(assignment, generation=self.generation, expires_at=110.0)

    def is_live(self, assignment, player, candidate):
        return self.alive

    def release(self, player, candidate):
        self.released.append(candidate)


class RamsgateApplicationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.addCleanup(self.db.close)
        self.host = SyntheticHost()
        self.mm = RamsgateMatchmaker(self.host, clock=lambda: 100.0)
        self.app = RamsgateApplication(self.db, matchmaker=self.mm, lab_key='unit-lab-key')
        reply = self.app.handle('POST', 'localhost', '/__lab/session',
                                {'X-Reawakened-Lab-Key': 'unit-lab-key'}, b'{"subject":"synthetic"}')
        self.token = reply.payload['payload']['sessiontoken']
        self.session = self.app.sessions.resolve(self.token)
        self.account = self.session.account_id
        self.db.create(self.account, 'SyntheticSlayer', '{}')
        self.headers = {'Authorization': 'BEARER ' + self.token}
        self.join_body = {'playerId': self.account, 'gameMode': 'CITY',
                          'buildId': '682875_2.1.1_shipping'}

    def call(self, method, path, body=None, secure=True, service='mm2-prod'):
        return self.app.handle(method, service + '.steelyard.ca', path, self.headers,
                               b'' if body is None else json.dumps(body).encode(), secure=secure)

    def test_default_application_has_no_native_host(self):
        app = RamsgateApplication(self.db, sessions=self.app.sessions)
        reply = app.handle('POST', 'mm2-prod.steelyard.ca', '/candidate/join',
                           self.headers, json.dumps(self.join_body).encode(), secure=True)
        self.assertEqual(reply.status, 200)
        self.assertEqual(reply.payload['status'], 'MATCHING')
        self.assertNotIn('serverInfo', reply.payload)

    def test_baseline_probe_remains_unchanged(self):
        app = LoginPortApplication(self.db, sessions=self.app.sessions)
        result = app.handle('POST', 'mm2-prod.steelyard.ca', '/candidate/join',
                            self.headers, json.dumps(self.join_body).encode(), secure=True)
        self.assertEqual((result.status, result.body()), (404, b''))

    def test_registration_ack_does_not_assign_destination(self):
        reply = self.call('POST', '/candidate/player/register')
        self.assertEqual((reply.status, reply.payload), (200, {}))
        self.assertEqual(self.host.calls, 0)

    def test_requires_local_session(self):
        self.headers = {}
        for method, path in [('POST', '/candidate/join'), ('GET', '/candidate/status'),
                             ('DELETE', '/candidate'), ('POST', '/candidate/player/register')]:
            with self.subTest(path=path):
                self.assertEqual(self.call(method, path, self.join_body).status, 401)
        self.assertEqual(self.host.calls, 0)

    def test_tls_required(self):
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body, secure=False).status, 503)
        self.assertEqual(self.host.calls, 0)

    def test_origin_rejected_before_matchmaking(self):
        self.headers['Origin'] = 'https://example.invalid'
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).status, 403)
        self.assertEqual(self.host.calls, 0)

    def test_revoked_session_cannot_retrieve_address(self):
        self.host.ready = True
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).payload['status'], 'IN_PROGRESS')
        self.app.sessions.revoke(self.token)
        self.assertEqual(self.call('GET', '/candidate/status').status, 401)

    def test_session_rotation_does_not_take_old_candidate(self):
        self.call('POST', '/candidate/join', self.join_body)
        other = self.app.sessions.create(self.account)
        self.headers['Authorization'] = 'BEARER ' + other.session_token
        self.assertEqual(self.call('GET', '/candidate/status').status, 404)

    def test_other_account_and_character_are_rejected(self):
        self.join_body['playerId'] = 'other-account'
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).status, 401)
        self.join_body['playerId'] = self.account
        self.join_body['characterId'] = 'other-character'
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).status, 401)
        self.assertEqual(self.host.calls, 0)

    def test_no_character_is_not_auto_created(self):
        account = self.db.account('no-character')['accountId']
        session = self.app.sessions.create(account)
        self.headers['Authorization'] = 'Bearer ' + session.session_token
        self.join_body['playerId'] = account
        reply = self.call('POST', '/candidate/join', self.join_body)
        self.assertEqual(reply.status, 409)
        self.assertEqual(self.db.get(account), [])

    def test_multiple_characters_require_explicit_selection_work(self):
        self.db.create(self.account, 'Second', '{}')
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).status, 409)
        self.assertEqual(self.host.calls, 0)

    def test_hunts_not_silently_redirected_to_city(self):
        self.join_body['gameMode'] = 'ISLAND'
        self.assertEqual(self.call('POST', '/candidate/join', self.join_body).status, 422)

    def test_wrong_methods_and_service_stay_bodyless_404(self):
        for method, path, service in [('POST', '/candidate', 'mm2-prod'),
                                     ('PUT', '/candidate/join', 'mm2-prod'),
                                     ('POST', '/candidate/join', 'auth-prod')]:
            with self.subTest(path=path, method=method, service=service):
                reply = self.call(method, path, self.join_body, service=service)
                self.assertEqual((reply.status, reply.body()), (404, b''))

    def test_ready_shape_comes_only_from_test_provider(self):
        first = self.call('POST', '/candidate/join', self.join_body)
        self.assertNotIn('serverInfo', first.payload)
        self.host.ready = True
        reply = self.call('GET', '/candidate/status')
        body = reply.payload
        self.assertEqual(body['candidateId'], first.payload['candidateId'])
        self.assertIs(body['isNewMatchmaker'], True)
        self.assertEqual(set(body['playerStates']), {self.account})
        self.assertEqual(set(body['serverInfo']), {'host', 'port', 'gameArgs', 'gameSessionId', 'instanceId'})
        self.assertIs(type(body['serverInfo']['port']), int)
        self.assertNotIn(self.token, reply.body().decode())
        self.assertNotIn(self.session.session_id, reply.body().decode())

    def test_dead_host_removes_previously_offered_address(self):
        self.host.ready = True
        self.call('POST', '/candidate/join', self.join_body)
        self.host.alive = False
        reply = self.call('GET', '/candidate/status')
        self.assertEqual(reply.payload['status'], 'FAILED')
        self.assertNotIn('serverInfo', reply.payload)

    def test_cancel_drops_address_and_leaves_database_unchanged(self):
        before = self.db.get(self.account)
        self.host.ready = True
        self.call('POST', '/candidate/join', self.join_body)
        self.assertEqual(self.call('DELETE', '/candidate/leave').status, 204)
        reply = self.call('GET', '/candidate/status')
        self.assertEqual(reply.payload['status'], 'CANCELED')
        self.assertNotIn('serverInfo', reply.payload)
        self.assertEqual(self.db.get(self.account), before)

    def test_health_not_gameplay_ready(self):
        reply = self.app.handle('GET', 'localhost', '/health', {})
        self.assertIs(reply.payload['ramsgate_matchmaking_experiment'], True)
        self.assertIs(reply.payload['game_compatible'], False)
        self.assertIs(reply.payload['native_host_started_by_this_application'], False)


class RamsgateTlsTests(unittest.TestCase):
    def test_session_character_join_poll_cancel_over_tls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            tls = generate(root / 'tls')
            db = Database(root / 'characters.sqlite3')
            host = SyntheticHost()
            mm = RamsgateMatchmaker(host, clock=lambda: 100.0)
            app = RamsgateApplication(db, matchmaker=mm, lab_key='tls-lab-key')
            server = make_server(app, '127.0.0.1', 0, tls_context(tls / 'server.pem', tls / 'server-key.pem'))
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            worker.start()
            context = ssl.create_default_context(cafile=str(tls / 'ca.pem'))

            def request(method, service, path, body=None, token=None, lab=False):
                conn = http.client.HTTPSConnection('127.0.0.1', server.server_port, context=context, timeout=5)
                headers = {'Host': service}
                if token:
                    headers['Authorization'] = 'BEARER ' + token
                if lab:
                    headers['X-Reawakened-Lab-Key'] = 'tls-lab-key'
                try:
                    conn.request(method, path, body=None if body is None else json.dumps(body).encode(), headers=headers)
                    response = conn.getresponse()
                    raw = response.read()
                    return response.status, json.loads(raw) if raw else None
                finally:
                    conn.close()
            try:
                with self.assertLogs('reawakened.requests', level='INFO') as records:
                    status, session = request('POST', 'localhost', '/__lab/session', {'subject': 'private-synthetic-name'}, lab=True)
                    self.assertEqual(status, 200)
                    token = session['payload']['sessiontoken']
                    status, info = request('GET', 'auth-prod.steelyard.ca', '/accountinfo', token=token)
                    self.assertEqual(status, 200)
                    status, char = request('PUT', 'dauntless-prod.steelyard.ca', '/character', {'name': 'PrivateSyntheticSlayer'}, token)
                    self.assertEqual(status, 200)
                    body = {'playerId': info['accountId'], 'gameMode': 'CITY', 'buildId': '682875_2.1.1_shipping'}
                    status, _ = request('POST', 'mm2-prod.steelyard.ca', '/candidate/player/register', token=token)
                    self.assertEqual(status, 200)
                    status, waiting = request('POST', 'mm2-prod.steelyard.ca', '/candidate/join', body, token)
                    self.assertEqual((status, waiting['status']), (200, 'MATCHING'))
                    self.assertNotIn('serverInfo', waiting)
                    host.ready = True
                    status, offered = request('GET', 'mm2-prod.steelyard.ca', '/candidate/status', token=token)
                    self.assertEqual((status, offered['status']), (200, 'IN_PROGRESS'))
                    self.assertEqual(offered['serverInfo']['host'], '127.0.0.1')
                    self.assertEqual(offered['serverInfo']['port'], 8777)
                    status, _ = request('DELETE', 'mm2-prod.steelyard.ca', '/candidate', token=token)
                    self.assertEqual(status, 204)
                    status, canceled = request('GET', 'mm2-prod.steelyard.ca', '/candidate/status', token=token)
                    self.assertEqual((status, canceled['status']), (200, 'CANCELED'))
                    self.assertNotIn('serverInfo', canceled)
                log = '\n'.join(records.output)
                for secret in (token, info['accountId'], char['id'], 'PrivateSyntheticSlayer', 'private-synthetic-name'):
                    self.assertNotIn(secret, log)
                self.assertIn('route=ramsgate-join', log)
                self.assertIn('route=ramsgate-status', log)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)
                db.close()
