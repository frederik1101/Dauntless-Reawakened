# SPDX-License-Identifier: AGPL-3.0-only
"""Standalone loopback-only research API server. NOT a Dauntless gameplay host.

Owns a persistent SQLite database and locally generated TLS certificate.
Never changes the Windows trust store, hosts file, game files or Epic login.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
from pathlib import Path

from backend.database import Database
from backend.ramsgate_application import RamsgateApplication
from backend.server import make_server, tls_context
from tools.local_tls import generate


def default_home() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    if not root:
        raise ValueError('LOCALAPPDATA is required')
    return Path(root) / 'DauntlessReawakenedServer'


def serve(home: Path, port: int, *, stop: threading.Event | None = None,
          client_ports: bool = False) -> None:
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
    database = Database(home / 'players.sqlite3')
    servers = []
    workers = []
    try:
        app = RamsgateApplication(database, allow_unverified_eos_sub=False,
                                  maintenance_response={'isMaintenance': False})
        # Bind every requested listener before starting any worker.
        endpoints = [(port, context)] if not client_ports else [(443, context), (80, None)]
        for listen_port, tls_context_or_none in endpoints:
            servers.append(make_server(app, '127.0.0.1', listen_port, tls_context_or_none))
        for server in servers:
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={'poll_interval': 0.1}, daemon=True)
            worker.start()
            workers.append(worker)
        print('Reawakened standalone API: https://127.0.0.1:%d/health' % (443 if client_ports else port), flush=True)
        print('Database: ' + str(home / 'players.sqlite3'), flush=True)
        print('LOCAL API ONLY. No Epic login, native gameplay host, Ramsgate join or playable character.', flush=True)
        if client_ports:
            print('CLIENT PORTS READY on loopback 80/443. No game redirect performed.', flush=True)
        try:
            (stop or threading.Event()).wait()
        except KeyboardInterrupt:
            pass
    finally:
        for server in servers[:len(workers)]:
            server.shutdown()
        for server in servers:
            server.server_close()
        for worker in workers:
            worker.join(timeout=5)
        database.close()


def self_test() -> dict:
    database = Database(':memory:')
    try:
        app = RamsgateApplication(database)
        health = app.handle('GET', 'localhost', '/health', {})
        denied = app.handle('GET', 'dauntless-prod.steelyard.ca',
                            '/character', {}, secure=True)
        if health.status != 200 or denied.status != 401:
            raise ValueError('Backend self-test failed')
        return {'api': 'passed', 'unauthenticated_character': 'denied',
                'gameplay_host': 'not_implemented', 'epic_auth': 'not_implemented'}
    finally:
        database.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--client-ports', action='store_true',
                        help='Bind loopback HTTP 80 and HTTPS 443 for a separate reversible client test')
    args = parser.parse_args()
    try:
        if args.self_test:
            print(json.dumps(self_test(), indent=2))
        else:
            logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
            serve(args.home or default_home(), args.port, client_ports=args.client_ports)
    except (OSError, ValueError) as exc:
        parser.exit(1, 'Server stopped: %s\n' % exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
