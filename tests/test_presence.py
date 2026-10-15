"""Real local sockets, independent RFC frames; no Dauntless or Epic access."""
import base64
import hashlib
import json
import socket
import struct
import threading
import time
import unittest
from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.presence import PresenceHub
from backend.server import make_server
from backend.session_store import SessionStore

KEY = 'dGhlIHNhbXBsZSBub25jZQ=='


def read_exact(sock, n):
    parts = bytearray()
    while len(parts) < n:
        chunk = sock.recv(n-len(parts))
        if not chunk:
            raise EOFError('peer closed')
        parts.extend(chunk)
    return bytes(parts)


def frame(opcode, data=b'', *, fin=True, masked=True):
    assert len(data) < 126
    mask = b'ABCD'
    encoded = bytes(v ^ mask[i % 4] for i, v in enumerate(data))
    return (bytes([(0x80 if fin else 0) | opcode, len(data) | (0x80 if masked else 0)])
            + (mask+encoded if masked else data))


def received_frame(sock):
    first, second = read_exact(sock, 2)
    assert not second & 0x80, 'Server frames must not be masked'
    length = second & 127
    if length == 126:
        length = struct.unpack('!H', read_exact(sock, 2))[0]
    if length == 127:
        length = struct.unpack('!Q', read_exact(sock, 8))[0]
    assert length <= 4096
    return first & 15, read_exact(sock, length)


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:')
        self.app = PostLoginApplication(self.db)
        self.account = self.db.account('presence-synthetic')['accountId']
        self.session = self.app.sessions.create(self.account)
        self.hub = PresenceHub(self.app.sessions, poll_seconds=.02)
        self.server = make_server(self.app, '127.0.0.1', 0, presence=self.hub)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01}, daemon=True)
        self.worker.start()
        self.sockets = []

    def tearDown(self):
        for connection in self.sockets:
            connection.close()
        self.hub.close()
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)
        self.assertFalse(self.worker.is_alive())
        self.db.close()

    def connect(self, *, account=None, overrides=None, extra=None, tail=b''):
        connection = socket.create_connection(('127.0.0.1', self.server.server_port), timeout=2)
        self.sockets.append(connection)
        headers = {
            'Host': 'presence-prod.steelyard.ca', 'Connection': 'Upgrade',
            'Upgrade': 'websocket', 'Sec-WebSocket-Key': KEY,
            'Sec-WebSocket-Version': '13', 'Sec-WebSocket-Protocol': 'json',
        }
        for k, v in (overrides or {}).items():
            if v is None:
                headers.pop(k, None)
            else:
                headers[k] = v
        request = 'GET /ws/'+(account or self.account)+' HTTP/1.1\r\n'
        request += ''.join(k+': '+v+'\r\n' for k,v in headers.items())
        request += extra or ''
        connection.sendall((request+'\r\n').encode('ascii')+tail)
        data = bytearray()
        while not data.endswith(b'\r\n\r\n'):
            data.extend(read_exact(connection, 1))
            self.assertLess(len(data), 8192)
        return connection, data.decode('ascii')

    def test_standard_upgrade_echoes_protocol_and_correct_accept(self):
        _, head = self.connect()
        self.assertTrue(head.startswith('HTTP/1.1 101'))
        expected = base64.b64encode(hashlib.sha1((KEY+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.assertIn(expected, head)
        self.assertIn('sec-websocket-protocol: json', head.lower())
        self.assertNotIn('content-length', head.lower())

    def test_authenticated_bearer_matches_path(self):
        _, head = self.connect(overrides={'Authorization': 'Bearer '+self.session.session_token})
        self.assertIn('101 Switching Protocols', head)

    def test_invalid_bearer_cannot_fallback_to_active_account(self):
        _, head = self.connect(overrides={'Authorization': 'Bearer invalid'})
        self.assertIn('401', head)

    def test_other_account_rejected(self):
        other = self.app.sessions.create(self.db.account('other-synthetic')['accountId'])
        _, head = self.connect(overrides={'Authorization': 'Bearer '+other.session_token})
        self.assertIn('401', head)

    def test_no_session_not_auto_created(self):
        before = self.db._db.total_changes
        _, head = self.connect(account='f'*32)
        self.assertIn('401', head)
        self.assertEqual(before, self.db._db.total_changes)

    def test_browser_origin_rejected(self):
        _, head = self.connect(overrides={'Origin': 'null'})
        self.assertIn('403', head)

    def test_wrong_subprotocol_rejected(self):
        _, head = self.connect(overrides={'Sec-WebSocket-Protocol': 'secret-game-protocol'})
        self.assertIn('400', head)

    def test_duplicate_key_rejected(self):
        _, head = self.connect(extra='Sec-WebSocket-Key: '+KEY+'\r\n')
        self.assertIn('400', head)

    def test_bad_key_rejected(self):
        _, head = self.connect(overrides={'Sec-WebSocket-Key': 'not-base64'})
        self.assertIn('400', head)

    def test_path_not_a_general_websocket_proxy(self):
        _, head = self.connect(overrides={'Host': 'store-prod.steelyard.ca'})
        self.assertIn('404', head)

    def test_no_http_body_on_upgrade(self):
        _, head = self.connect(overrides={'Content-Length': '1'}, tail=b'x')
        self.assertIn('400', head)

    def test_capacity_rejects_not_hangs(self):
        self.hub.capacity = 1
        _, first = self.connect()
        self.assertIn('101', first)
        _, second = self.connect()
        self.assertIn('503', second)

    def test_ping_in_prefetched_data_gets_pong(self):
        sock, head = self.connect(tail=frame(9, b'check'))
        self.assertIn('101', head)
        self.assertEqual(received_frame(sock), (10, b'check'))

    def test_unmasked_frame_rejected_by_rfc_parser(self):
        sock, _ = self.connect()
        sock.sendall(frame(9, b'x', masked=False))
        opcode, data = received_frame(sock)
        self.assertEqual(opcode, 8)
        self.assertEqual(struct.unpack('!H', data[:2])[0], 1002)

    def test_fragmentation_and_payload_not_logged(self):
        with self.assertLogs('reawakened.requests', level='INFO') as logs:
            sock, _ = self.connect()
            sock.sendall(frame(1, b'PRIVATE_', fin=False)+frame(9, b'alive')+
                         frame(0, b'VALUE'))
            self.assertEqual(received_frame(sock), (10, b'alive'))
            sock.sendall(frame(8, struct.pack('!H', 1000)))
            self.assertEqual(received_frame(sock)[0], 8)
        self.assertNotIn('PRIVATE_', str(logs.output))
        self.assertNotIn(self.account, str(logs.output))
        self.assertNotIn(self.session.session_token, str(logs.output))
        self.assertIn('application_data_unhandled', str(logs.output))

    def test_revoking_session_closes_presence(self):
        sock, _ = self.connect()
        self.app.sessions.revoke(self.session.session_token)
        self.assertEqual(sock.recv(1), b'')

    def test_shutdown_closes_idle_presence_without_hanging(self):
        sock, _ = self.connect()
        self.hub.close()
        self.assertEqual(sock.recv(1), b'')

    def test_idle_connection_not_dropped_by_http_five_second_timeout(self):
        sock, _ = self.connect()
        time.sleep(5.1)
        sock.sendall(frame(9, b'still-here'))
        self.assertEqual(received_frame(sock), (10, b'still-here'))

    def test_presence_does_not_authorize_character_reads(self):
        self.connect()
        response = self.app.handle('GET','dauntless-prod.steelyard.ca','/character',{},secure=True)
        self.assertEqual(response.status, 401)
        self.assertFalse(self.app.handle('GET','localhost','/health',{}).payload['game_compatible'])


class PresenceSessionTests(unittest.TestCase):
    def test_expired_lookup_is_not_active(self):
        now = [1.]
        sessions = SessionStore(ttl=2, clock=lambda: now[0])
        created = sessions.create('synthetic')
        self.assertEqual(sessions.active_for_account('synthetic'), created)
        now[0] += 3
        self.assertIsNone(sessions.active_for_account('synthetic'))

    def test_revoke_one_of_two_accounts(self):
        sessions = SessionStore()
        first = sessions.create('first')
        second = sessions.create('second')
        sessions.revoke(first.session_token)
        self.assertIsNone(sessions.active_for_account('first'))
        self.assertEqual(sessions.active_for_account('second'), second)
