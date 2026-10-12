# SPDX-License-Identifier: AGPL-3.0-only
"""Standalone loopback-only research API server. NOT a Dauntless gameplay host.

Owns a persistent SQLite database and locally generated TLS certificate.
Never changes the Windows trust store, hosts file, game files or Epic login.
"""
from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
from pathlib import Path

from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.post_login_contracts import REVISION
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.post_login_backup import backup_before_post_login


def default_home() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    if not root:
        raise ValueError('LOCALAPPDATA is required')
    return Path(root) / 'DauntlessReawakenedServer'


def serve(home: Path, port: int, *, stop: threading.Event | None = None,
          client_ports: bool = False, diagnostic: bool = False,
          presence: bool = False, mystic_profile: bool = False,
          profile_variant: str = 'full') -> None:
    from backend.character_profile import PROFILE_VARIANTS
    if profile_variant not in PROFILE_VARIANTS or (profile_variant != 'full' and not mystic_profile):
        raise ValueError('A profile variant requires --mystic-profile and a known variant')
    if presence and not client_ports:
        raise ValueError('Presence requires explicit --client-ports mode')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Choose an unprivileged port (1024-65535)')
    home = home.absolute()
    home.mkdir(parents=True, exist_ok=True)
    tls = home / 'tls'
    if not tls.exists():
        generate(tls)
    for filename in ('server.pem', 'server-key.pem', 'ca.pem'):
        if not (tls / filename).is_file():
            raise ValueError('Incomplete TLS directory; preserve it for review')
    context = tls_context(tls / 'server.pem', tls / 'server-key.pem')
    database_path = home / 'players.sqlite3'
    if mystic_profile:
        from tools.profile_database import profile_snapshot
        database_path = profile_snapshot(home)
    backup = backup_before_post_login(database_path)
    if backup is not None:
        print('Pre-upgrade SQLite backup retained:', backup, flush=True)
    if mystic_profile:
        from backend.character_profile import ProfileDatabase
        database = ProfileDatabase(database_path, variant=profile_variant)
        print('EXPERIMENTAL MYSTIC PROFILE: fresh DB copy; original players.sqlite3 unchanged.', flush=True)
        print('PROFILE_INITIALIZATION ' + json.dumps(database.profile_summary), flush=True)
    else:
        database = Database(database_path)
    servers = []
    workers = []
    presence_hub = None
    diagnostic_handler = None
    try:
        if diagnostic:
            from tools.probe_files import _plain_path
            log_dir = home / 'logs'
            _plain_path(log_dir)
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / ('server-diagnostic-' + str(time.time_ns()) + '.log')
            diagnostic_handler = RotatingFileHandler(log_path, maxBytes=2*1024*1024,
                                                       backupCount=1, encoding='utf-8')
            formatter = logging.Formatter('%(asctime)sZ %(levelname)s %(message)s',
                                          '%Y-%m-%dT%H:%M:%S')
            formatter.converter = time.gmtime
            diagnostic_handler.setFormatter(formatter)
            logging.getLogger('reawakened.requests').addHandler(diagnostic_handler)
            print('Sanitized server log:', log_path, flush=True)
        # Client research mode matches the old preview's local-only EOS-sub lookup.
        # It does NOT validate Epic tokens or prove account ownership.
        app = PostLoginApplication(database, allow_unverified_eos_sub=client_ports,
                                   maintenance_response={'isMaintenance': False})
        if presence:
            from backend.presence import PresenceHub
            presence_hub = PresenceHub(app.sessions)
        # Bind every requested listener before starting any worker.
        endpoints = [('127.0.0.1', port, context)] if not client_ports else [
            (ip, listen_port, security) for listen_port, security in ((443, context), (80, None))
            for ip in ('127.0.0.1', '::1')]
        for ip, listen_port, tls_context_or_none in endpoints:
            servers.append(make_server(app, ip, listen_port, tls_context_or_none,
                                       diagnostic=diagnostic, presence=presence_hub))
        for server in servers:
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={'poll_interval': 0.1}, daemon=True)
            worker.start()
            workers.append(worker)
        print('Reawakened standalone API: https://127.0.0.1:%d/health' % (443 if client_ports else port), flush=True)
        print('Database: ' + str(database_path), flush=True)
        print('LOCAL API ONLY. No Epic login, native gameplay host, Ramsgate join or playable character.', flush=True)
        if presence:
            print('PRESENCE TRANSPORT enabled; no game updates or native host.', flush=True)
        if client_ports:
            print('CLIENT PORTS READY on loopback 80/443. No game redirect performed.', flush=True)
            print('WARNING: EOS-sub is an UNVERIFIED local lookup key, not Epic authentication.', flush=True)
        try:
            (stop or threading.Event()).wait()
        except KeyboardInterrupt:
            pass
    finally:
        if presence_hub is not None:
            presence_hub.close()
        for server in servers[:len(workers)]:
            server.shutdown()
        for server in servers:
            server.server_close()
        for worker in workers:
            worker.join(timeout=5)
        if diagnostic_handler is not None:
            logging.getLogger('reawakened.requests').removeHandler(diagnostic_handler)
            diagnostic_handler.close()
        database.close()


def self_test() -> dict:
    database = Database(':memory:')
    try:
        app = PostLoginApplication(database)
        health = app.handle('GET', 'localhost', '/health', {})
        denied = app.handle('GET', 'dauntless-prod.steelyard.ca',
                            '/character', {}, secure=True)
        if (health.status != 200 or denied.status != 401 or
                health.payload.get('post_login_revision') != REVISION):
            raise ValueError('Backend self-test failed')
        account = database.account('packaged-self-test')['accountId']
        session = app.sessions.create(account, linked_epic_id='synthetic-epic-id')
        mapped = app.handle('POST', 'auth-prod.steelyard.ca', '/account/mapping',
            {'Authorization': 'Bearer ' + session.session_token},
            b'{"srcAccountType":"epic","ids":["synthetic-epic-id"]}', secure=True)
        if (mapped.status != 200 or
                mapped.payload['accountMappings']['synthetic-epic-id']['accountId'] != account):
            raise ValueError('Packaged account mapping failed')
        from backend.post_login_contracts import tuning_response
        if tuning_response('huntpass_xp_config')['code'] != 'OK':
            raise ValueError('Packaged tuning envelope type check failed')
        from wsproto import WSConnection, ConnectionType
        from wsproto.events import AcceptConnection, Request
        codec = WSConnection(ConnectionType.SERVER)
        codec.receive_data(b'GET /test HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
            b'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
            b'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Protocol: json\r\n\r\n')
        if not any(isinstance(event, Request) for event in codec.events()):
            raise ValueError('Packaged presence parser failed')
        if b'101 Switching Protocols' not in codec.send(AcceptConnection(subprotocol='json')):
            raise ValueError('Packaged presence handshake failed')
        character = database.create(account, 'Synthetic', '{}')
        database.save(account, character['id'], '{}', 1, allow_identical_retry=True)
        if database.save(account, character['id'], '{}', 1, allow_identical_retry=True) != {'data': '{}'}:
            raise ValueError('Packaged character retry failed')
        # Exercise the packaged typed-identity path with synthetic values only.
        import base64
        from backend.research_identity import parse_research_identity
        from backend.post_login_contracts import mapping_response
        claims = {'sub': 'a1' * 16, 'act': {'eat': 'epicgames', 'eaid': 'b2' * 16}}
        synthetic = 'e30.' + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=') + '.c3ludGhldGlj'
        projection = parse_research_identity(synthetic)
        query = json.dumps({'srcAccountType': 'epic', 'ids': [('b2' * 16).upper()]}).encode()
        result = mapping_response(query, account, projection.epic_id)
        if (projection.subject == projection.epic_id or
                len(result['accountMappings']) != 1):
            raise ValueError('Packaged typed identity mapping failed')
        from backend.character_profile import normalize_profile
        profile, added = normalize_profile('{"PlayerAccountProgressStep":"EnteredRamsgate"}')
        if len(added) != 8 or not all(isinstance(v, str) for v in json.loads(profile).values()):
            raise ValueError('Packaged profile initializer failed')
        from backend.character_profile import PROFILE_VARIANTS
        if set(PROFILE_VARIANTS) != {'full', 'without-appearance', 'without-flags',
            'without-metadata', 'appearance-only', 'flags-only', 'metadata-only', 'baseline'}:
            raise ValueError('Packaged variant allowlist mismatch')
        return {'profile_initializer': 'passed', 'api': 'passed', 'unauthenticated_character': 'denied',
                'post_login_revision': REVISION, 'local_mapping': 'passed',
                'presence_codec': 'passed', 'character_retry': 'passed',
                'typed_identity_mapping': 'passed',
                'gameplay_host': 'not_implemented', 'epic_auth': 'not_implemented'}
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--mystic-profile', action='store_true',
                        help='Test missing-field initialization on a fresh SQLite copy, never the original')
    from backend.character_profile import PROFILE_VARIANTS
    parser.add_argument('--profile-variant', choices=sorted(PROFILE_VARIANTS), default='full',
                        help='Select which documented character fields are added (requires --mystic-profile)')
    parser.add_argument('--presence', action='store_true',
                        help='Optional local presence WebSocket; not game-host emulation')
    parser.add_argument('--diagnostic', action='store_true',
                        help='Extra value-free JSON shape, timing and session diagnostics')
    parser.add_argument('--client-ports', action='store_true',
                        help='Bind loopback HTTP 80 and HTTPS 443 for a separate reversible client test')
    args = parser.parse_args()
    print('Server revision:', REVISION)
    try:
        if args.self_test:
            print(json.dumps(self_test(), indent=2))
        else:
            logging.Formatter.converter = time.gmtime
            logging.basicConfig(level=logging.INFO, format='%(asctime)sZ %(levelname)s %(message)s',
                                datefmt='%Y-%m-%dT%H:%M:%S')
            serve(args.home or default_home(), args.port, client_ports=args.client_ports,
                  diagnostic=args.diagnostic, presence=args.presence,
                  mystic_profile=args.mystic_profile, profile_variant=args.profile_variant)
    except (OSError, ValueError) as exc:
        parser.exit(1, 'Server stopped: %s\n' % exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
