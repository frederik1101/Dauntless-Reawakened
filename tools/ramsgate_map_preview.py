# SPDX-License-Identifier: AGPL-3.0-only
"""Stock-client Ramsgate MAP PREVIEW. Not a host, join test or login repair.

Uses a journalled GameDefaultMap setting, no native runtime or memory patch.
"""
from __future__ import annotations
import argparse
import http.client
import json
import logging
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.application import SERVICES
from backend.database import Database
from backend.map_preview import MapObservations, make_application
from tools.login_probe import inspect_client, windows_ready, no_running_game, flush_dns, ABOUT
from tools.local_tls import generate
from tools.probe_files import prepare, restore, _plain_path
from backend.server import make_server, tls_context
from tools.map_preview_support import (
    REVISION, EXACT_SHA256, install_config, watch, stop_owned, login_test_duration,
)

NOTICE = ('RAMSGATE MAP PREVIEW ONLY. No server, verified login or controllable player.\n'
          'The normal login map is replaced temporarily; this does NOT test normal city travel.\n'
          'An empty view, return to login, loading error or client crash remains possible.\n'
          'Map-preview limit: 180 seconds. Normal-login limit: 600 seconds.\n'
          'Memory watchdog: 5000 MiB (sampled, not a hard OS limit).')


def check(root: Path) -> dict:
    _plain_path(root)
    info = inspect_client(root)
    if info['sha256'] != EXACT_SHA256:
        raise ValueError('The map preview requires the exact reviewed 2.1.1 executable')
    for suffix in ('utoc', 'ucas'):
        path = root / 'Archon/Content/Paks' / ('Archon_Maps_2-WindowsClient.' + suffix)
        _plain_path(path)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('The documented Ramsgate content container is missing')
    return {**info, 'build_verified_by_hash': True, 'map_containers_present': True,
            'map_contents_verified': False, 'game_server_ready': False}


def pending(home: Path) -> bool:
    journal = home / 'active/journal.json'
    _plain_path(journal)
    if not journal.exists():
        return False
    return json.loads(journal.read_text(encoding='utf-8')).get('restored') is not True


def run_preview(root: Path, home: Path, seconds: int, *, normal_login: bool = False,
                external_server: bool = False) -> None:
    if external_server and not normal_login:
        raise ValueError('External server mode requires normal login')
    seconds = login_test_duration(seconds, normal_login)
    info = check(root)
    exe = Path(info['exe'])
    windows_ready(exe)
    legacy = Path(os.environ['LOCALAPPDATA']) / 'DauntlessReawakenedProbe'
    if pending(legacy):
        raise ValueError('Restore the previous LOGIN probe with its own --restore command first')
    _plain_path(home)
    if pending(home):
        raise ValueError('This map preview needs --restore first')
    active = home / 'active'
    if active.exists() and not (active / 'journal.json').is_file():
        raise ValueError('Unrecognised map preview state; retained for review')
    print('NORMAL LOGIN + CITY REQUEST TEST; no game host or playable character.' if normal_login else NOTICE)
    print('Temporary changes: Phoenix hosts entries, this game CA, and WindowsClient config.')
    print('Original game EXE, Epic domains, Windows trust and previous research database are unchanged.')
    if external_server:
        print('Character data belongs to the running standalone server; no competing backend is started.')
    elif normal_login:
        print('This mode stores local character data in a separate persistent normal-login.sqlite3 database.')
    print('Duration:', seconds, 'seconds including Epic login; memory watchdog remains 5000 MiB.')
    print('The local backend retains its existing authentication and unknown-route errors.')
    if input('Type MAP to consent, or Enter to cancel: ').strip() != 'MAP':
        print('Cancelled. Nothing changed.')
        return
    home.mkdir(parents=True, exist_ok=True)
    if active.exists():
        active.rename(home / ('completed-' + str(time.time_ns())))
    observations = MapObservations()
    # Normal login needs the same local character on successive test launches.
    # Keep it separate from the legacy research DB; direct map preview stays ephemeral.
    db = Database(':memory:' if external_server else
                  (home / 'normal-login.sqlite3' if normal_login else ':memory:'))
    app = make_application(db, observations)
    servers, workers = [], []
    process = journal = handler = None
    restored = False
    outcome = {'termination': 'setup_failed'}
    logger = logging.getLogger('reawakened.requests')
    try:
        tls = (Path(os.environ['LOCALAPPDATA']) / 'DauntlessReawakenedServer/tls'
               if external_server else generate(home / ('tls-' + str(time.time_ns()))))
        # External mode needs only the PUBLIC CA, not the server's private key.
        ctx = None if external_server else tls_context(tls / 'server.pem', tls / 'server-key.pem')
        # In external mode the standalone server already owns 80/443.
        # No second backend may intercept the game's requests.
        if not external_server:
            for port, context in ((443, ctx), (80, None)):
                for ip in ('127.0.0.1', '::1'):
                    servers.append(make_server(app, ip, port, context))
        for server in servers:
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={'poll_interval': .1}, daemon=True)
            worker.start()
            workers.append(worker)
        client = http.client.HTTPSConnection('127.0.0.1', 443, timeout=5,
                    context=ssl.create_default_context(cafile=str(tls / 'ca.pem')))
        try:
            client.request('GET', '/health')
            reply = client.getresponse()
            health = json.loads(reply.read())
            if reply.status != 200 or not health.get('experimental_login_port'):
                raise ValueError('Local backend self-check failed')
            if external_server and health.get('post_login_revision') != REVISION:
                raise ValueError('Update and restart the standalone server to match this client test')
        finally:
            client.close()
        config = Path(os.environ['LOCALAPPDATA']) / 'Archon/Saved/Config/WindowsClient'
        hosts = Path(os.environ['SystemRoot']) / 'System32/drivers/etc/hosts'
        ca = root / 'Engine/Content/Certificates/cacert.pem'
        names = sorted(s + '.steelyard.ca' for s in SERVICES) + ['steelyard.online']
        journal = prepare(active, ca, hosts, config, (tls / 'ca.pem').read_bytes(), names)
        install_config(config, journal, normal_login=normal_login)
        flush_dns()
        for name in ('auth-prod.steelyard.ca', 'tracking-prod.steelyard.ca'):
            addresses = {r[4][0] for r in socket.getaddrinfo(name, 443, type=socket.SOCK_STREAM)}
            if not addresses or not addresses <= {'127.0.0.1', '::1'}:
                raise ValueError('Expected exclusively loopback DNS; stopping')
        handler = logging.FileHandler(active / 'map-preview.log', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)sZ %(levelname)s %(message)s', '%Y-%m-%dT%H:%M:%S')
        formatter.converter = time.gmtime
        handler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info('MAP_PREVIEW_BEGIN revision=%s game_server=false mode=%s', REVISION,
                    'external_server' if external_server else
                    ('normal_login' if normal_login else 'map_preview'))
        print('Starting original client against standalone local API.' if external_server else
              'Starting original client with normal login map.' if normal_login else
              'Starting original client with temporary Ramsgate default map. Keep this window open.')
        process = subprocess.Popen([str(exe), '-EpicPortal', '-AUTH_TYPE=accountportal',
                    '-AUTH_LOGIN=unused', '-AUTH_PASSWORD=unused'], cwd=exe.parent,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        outcome = (watch(process, seconds, max_seconds=600) if normal_login else watch(process, seconds))
        if outcome.get('termination') == 'time_limit':
            print('TEST TIME LIMIT reached; this tool is stopping its client, not reporting a game crash.')
    except KeyboardInterrupt:
        outcome = {'termination': 'interrupted'}
    finally:
        try:
            # Do not restore while the launched client could still write config.
            stop_owned(process)
            if journal is not None:
                restore(journal)
                restored = True
                flush_dns()
                print('Original configuration, game CA and hosts entries restored.')
        finally:
            for server in servers[:len(workers)]:
                server.shutdown()
            for server in servers:
                server.server_close()
            for worker in workers:
                worker.join(timeout=6)
            db.close()
            if handler:
                logger.info('MAP_PREVIEW_END restored=%s', restored)
                logger.removeHandler(handler)
                handler.close()
            if journal is not None:
                report = {'revision': REVISION, 'test_kind':
                          'standalone_api_client_observation' if external_server else
                          ('normal_login_city_observation' if normal_login else 'stock_client_map_preview'),
                          **outcome, **observations.report(),
                          'backend_observations_collected_here': not external_server,
                          'external_server_logs_required': external_server,
                          'restored': restored,
                          'exit_code': process.poll() if process is not None else None}
                with (active / 'map-preview-result.json').open('x', encoding='utf-8') as stream:
                    json.dump(report, stream, indent=2)
                print(json.dumps(report, indent=2))
                print('Share only map-preview-result.json or a screenshot of the game, not the state folder.')



def offline_identity_self_test() -> dict:
    """Exercise local-only account/session/character/CITY without launching Dauntless.

    This never asserts Epic authentication or creates a game host.
    """
    db = Database(':memory:')
    try:
        app = make_application(db, MapObservations())
        # Lab key is scoped to this in-memory application and never written to disk.
        issued = app.handle('POST', 'localhost', '/__lab/session',
                            {'X-Reawakened-Lab-Key': app.lab_key},
                            b'{"subject":"offline-identity-test"}', secure=True)
        if issued.status != 200:
            raise ValueError('Local identity issuance failed')
        token = issued.payload['payload']['sessiontoken']
        session = app.sessions.resolve(token)
        if session is None:
            raise ValueError('Local session could not be resolved')
        headers = {'Authorization': 'Bearer ' + token}
        created = db.create(session.account_id, 'OfflineSlayer', '{}')
        character = app.handle('GET', 'dauntless-prod.steelyard.ca',
                               '/character', headers, secure=True)
        join_body = json.dumps({'playerId': session.account_id, 'gameMode': 'CITY',
                                'buildId': '682875_2.1.1_shipping'}).encode()
        join = app.handle('POST', 'mm2-prod.steelyard.ca', '/candidate/join',
                          headers, join_body, secure=True)
        if (character.status != 200 or len(character.payload) != 1 or
                character.payload[0]['id'] != created['id'] or
                join.status != 200 or join.payload['status'] != 'MATCHING' or
                'serverInfo' in join.payload):
            raise ValueError('Offline identity contract failed')
        if app.handle('GET', 'dauntless-prod.steelyard.ca',
                      '/character', {}, secure=True).status != 401:
            raise ValueError('Missing authorization was incorrectly accepted')
        return {'offline_identity': 'passed', 'local_character': 'passed',
                'city_request': 'matching_no_host',
                'epic_authentication': 'not_tested',
                'game_client': 'not_launched', 'game_server': 'not_started'}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for name in ('about', 'check', 'run', 'restore', 'self-test', 'offline-identity-test'):
        modes.add_argument('--' + name, action='store_true')
    parser.add_argument('--game-root', type=Path, default=Path(r'C:\Program Files\Epic Games\Dauntless'))
    parser.add_argument('--seconds', type=int, default=None,
                        help='Default 600 for normal login; 120 for direct map preview')
    parser.add_argument('--external-server', action='store_true',
                        help='Use running standalone API on loopback 80/443; requires --normal-login')
    parser.add_argument('--normal-login', action='store_true',
                        help='Keep original login map; observe authenticated CITY requests without a host')
    args = parser.parse_args()
    print('Preview revision:', REVISION)
    if args.external_server and not args.normal_login:
        parser.error('--external-server requires --normal-login')
    if args.normal_login and not args.run:
        parser.error('--normal-login requires --run')
    try:
        if args.about:
            print(NOTICE + '\n' + ABOUT)
        elif args.offline_identity_test:
            print(json.dumps(offline_identity_self_test(), indent=2))
        elif args.self_test:
            from tools.map_preview_support import process_memory_bytes
            from types import SimpleNamespace
            import ctypes
            db = Database(':memory:')
            try:
                app = make_application(db, MapObservations())
                if app.handle('GET', 'localhost', '/health', {}).status != 200:
                    raise ValueError('Packaged backend check failed')
                if os.name == 'nt':
                    fn = ctypes.WinDLL('kernel32').GetCurrentProcess
                    fn.restype = ctypes.c_void_p
                    if process_memory_bytes(SimpleNamespace(_handle=fn())) <= 0:
                        raise ValueError('Memory counter check failed')
            finally:
                db.close()
            print('Packaged imports/backend/resource query OK. No game launched or user files edited.')
        elif args.check:
            print(json.dumps(check(args.game_root.absolute()), indent=2))
        else:
            if os.name != 'nt':
                raise ValueError('This preview requires Windows')
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                raise ValueError('Run PowerShell as administrator for run/restore')
            home = Path(os.environ['LOCALAPPDATA']) / 'DauntlessReawakenedMapTest'
            if args.restore:
                no_running_game()
                restore(home / 'active/journal.json')
                flush_dns()
                print('Map preview changes restored.')
            else:
                run_preview(args.game_root.absolute(), home, login_test_duration(args.seconds, args.normal_login),
                            normal_login=args.normal_login,
                            external_server=args.external_server)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('STOP:', exc, file=sys.stderr)
        print('Keep all backups. If this preview changed files, use this EXE --restore with the game closed.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
