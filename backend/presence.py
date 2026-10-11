# SPDX-License-Identifier: AGPL-3.0-only
"""Optional local presence transport, not game updates or a gameplay host.

2.1.1 static reference: presence-prod /ws/{accountid}, subprotocol 'json',
accept and stay open. This route has NOT been seen in the user's logs.
RFC 6455 parsing uses wsproto; no proprietary message schema is invented.
"""
from __future__ import annotations

import base64
import binascii
import logging
import re
import socket
import threading
from dataclasses import dataclass, field
from time import monotonic

from wsproto import WSConnection, ConnectionType
from wsproto.events import AcceptConnection, Request, Ping, Pong, CloseConnection, TextMessage, BytesMessage
from wsproto.utilities import LocalProtocolError, RemoteProtocolError

LOG = logging.getLogger('reawakened.requests')


@dataclass
class Lease:
    connection: socket.socket = field(repr=False)
    token: str = field(repr=False)
    started: float = field(default_factory=monotonic)
    end_reason: str = 'peer_closed'


class PresenceHub:
    """Capacity-bounded, owned connections; no account discovery/data API.

    A missing bearer is allowed ONLY for an already-active local account and
    only for this data-free keep-open service. This is not proof of ownership
    and MUST NOT be used to authorize character, inventory or matchmaking.
    If a bearer is supplied it MUST match that account and remain valid.
    """
    def __init__(self, sessions, *, capacity: int = 8, poll_seconds: float = .2):
        if type(capacity) is not int or not 1 <= capacity <= 64 or not .01 <= poll_seconds <= 1:
            raise ValueError('Invalid local presence settings')
        self.sessions, self.capacity, self.poll_seconds = sessions, capacity, poll_seconds
        self._leases: dict[int, Lease] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._reap, name='local-presence-lifetime', daemon=True)
        self._worker.start()

    def acquire(self, account: str, headers, connection: socket.socket) -> Lease | None:
        from .application import bearer
        lower = {k.lower(): v for k, v in headers.items()}
        if 'origin' in lower:
            raise PermissionError('Browser origin not allowed')
        if 'authorization' in lower:
            session = self.sessions.resolve(bearer(lower))
        else:
            session = self.sessions.active_for_account(account)
        if session is None or session.account_id != account:
            raise PermissionError('Local account session required')
        with self._lock:
            if self._stop.is_set() or len(self._leases) >= self.capacity:
                return None
            lease = Lease(connection, session.session_token)
            self._leases[id(lease)] = lease
            return lease

    def release(self, lease: Lease) -> None:
        with self._lock:
            self._leases.pop(id(lease), None)

    @staticmethod
    def _disconnect(lease: Lease, reason: str) -> None:
        lease.end_reason = reason
        # Wake a blocking read on THIS owned socket; never locate/kill a process.
        try:
            lease.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _reap(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            with self._lock:
                leases = list(self._leases.values())
            for lease in leases:
                if self.sessions.resolve(lease.token) is None:
                    self._disconnect(lease, 'local_session_ended')

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            leases = list(self._leases.values())
        for lease in leases:
            self._disconnect(lease, 'server_stopped')
        self._worker.join(timeout=2)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._leases)


def is_presence_path(service: str, endpoint: str) -> bool:
    return service == 'presence-prod' and endpoint.startswith('/ws/')


def _handshake(handler, endpoint: str):
    headers = handler.headers
    if handler.command != 'GET' or handler.request_version != 'HTTP/1.1':
        raise ValueError('Invalid WebSocket method or version')
    if '?' in handler.path or '#' in handler.path or '%' in handler.path:
        raise ValueError('Unexpected presence path suffix')
    if re.fullmatch(r'/ws/[0-9a-f]{32}', endpoint) is None:
        raise ValueError('Invalid local account path')
    for name in ('Host', 'Origin', 'Authorization', 'Connection', 'Upgrade',
                 'Sec-WebSocket-Key', 'Sec-WebSocket-Version', 'Sec-WebSocket-Protocol',
                 'Sec-WebSocket-Extensions', 'Content-Length', 'Transfer-Encoding'):
        if len(headers.get_all(name, [])) > 1:
            raise ValueError('Duplicate handshake header')
    if 'Origin' in headers:
        raise PermissionError('No browser access')
    if headers.get('Content-Length', '0') != '0' or 'Transfer-Encoding' in headers:
        raise ValueError('Handshake may not carry an HTTP body')
    if headers.get('Upgrade', '').lower() != 'websocket':
        raise ValueError('WebSocket upgrade required')
    if 'upgrade' not in {v.strip().lower() for v in headers.get('Connection', '').split(',')}:
        raise ValueError('Missing connection upgrade')
    if headers.get('Sec-WebSocket-Version') != '13':
        raise ValueError('Unsupported WebSocket version')
    if 'json' not in [p.strip() for p in headers.get('Sec-WebSocket-Protocol', '').split(',')]:
        raise ValueError('json subprotocol required')
    key = headers.get('Sec-WebSocket-Key', '')
    if len(key) > 32:
        raise ValueError('Invalid WebSocket key')
    try:
        if len(base64.b64decode(key, validate=True)) != 16:
            raise ValueError('Invalid WebSocket key length')
    except (binascii.Error, UnicodeError) as exc:
        raise ValueError('Invalid WebSocket key') from None
    # Feed the parsed HTTP upgrade to the RFC parser. No log of headers/path.
    websocket = WSConnection(ConnectionType.SERVER)
    websocket.initiate_upgrade_connection(
        [(k.encode('ascii'), v.encode('ascii')) for k, v in headers.items()], handler.path)
    events = list(websocket.events())
    if len(events) != 1 or not isinstance(events[0], Request):
        raise ValueError('No WebSocket request')
    return websocket, endpoint.rsplit('/', 1)[1]


def handle_presence(handler, hub: PresenceHub, endpoint: str) -> None:
    """Upgrade one connection, keep it open, respond only to RFC control frames."""
    from .application import Response
    lease = None
    websocket = None
    received = frames = 0
    try:
        if 'Origin' in handler.headers:
            return handler._send(Response(403, route='origin-rejected'))
        try:
            websocket, account = _handshake(handler, endpoint)
            lease = hub.acquire(account, handler.headers, handler.connection)
        except PermissionError:
            return handler._send(Response(401, route='presence-session-rejected'))
        except (ValueError, UnicodeError, LocalProtocolError, RemoteProtocolError):
            return handler._send(Response(400, route='presence-upgrade-rejected'))
        if lease is None:
            return handler._send(Response(503, route='presence-capacity'))
        handler._response_started = True
        handler.connection.settimeout(None)
        handler.wfile.write(websocket.send(AcceptConnection(subprotocol='json')))
        handler.wfile.flush()
        LOG.info('PRESENCE event=opened protocol=json admission=existing_local_session game_host=false')
        saw_data = False
        while True:
            chunk = handler.rfile.read1(4096)
            if not chunk:
                break
            received += len(chunk)
            if received > 1048576:
                lease.end_reason = 'wire_byte_limit'
                handler.wfile.write(websocket.send(CloseConnection(code=1009)))
                break
            websocket.receive_data(chunk)
            for event in websocket.events():
                frames += 1
                if frames > 10000:
                    lease.end_reason = 'event_limit'
                    handler.wfile.write(websocket.send(CloseConnection(code=1008)))
                    return
                if isinstance(event, Ping):
                    # Required control-frame echo only; never echo game JSON or tokens.
                    handler.wfile.write(websocket.send(event.response()))
                elif isinstance(event, Pong):
                    pass
                elif isinstance(event, CloseConnection):
                    lease.end_reason = 'peer_or_protocol_close'
                    try:
                        handler.wfile.write(websocket.send(event.response()))
                    except LocalProtocolError:
                        pass
                    return
                elif isinstance(event, (TextMessage, BytesMessage)):
                    if not saw_data:
                        LOG.info('PRESENCE event=application_data_unhandled payload_not_logged=true')
                        saw_data = True
                    # No documented server-push/update schema. Deliberately no ack.
            handler.wfile.flush()
    except (OSError, LocalProtocolError, RemoteProtocolError):
        if lease is not None and lease.end_reason == 'peer_closed':
            lease.end_reason = 'transport_or_protocol_error'
    finally:
        handler.close_connection = True
        if lease is not None:
            hub.release(lease)
            LOG.info('PRESENCE event=closed reason=%s received_bytes=%d events=%d',
                     lease.end_reason, received, frames)
