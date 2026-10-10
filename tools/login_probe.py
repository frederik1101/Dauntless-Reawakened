# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded Windows login experiment, not a playable game launcher.

Run --about without side effects. Run --check to inspect the installed client.
--run requires explicit consent, Windows admin rights, a signed original client,
free local ports, and no running Dauntless. All edits have a rollback journal.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import http.client
import json
import logging
import os
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

from backend.application import SERVICES
from backend.database import Database
from backend.mystic_login_port import LoginPortApplication, ATTRIBUTION, SOURCE_URL
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.probe_files import prepare, restore

ABOUT = ('Dauntless Reawakened - experimental login probe 0.3\n'
         'AGPL-3.0-only. NO WARRANTY. Not an official Mystic Paradox release.\n'
         + ATTRIBUTION + '\nSource: https://github.com/frederik1101/Dauntless-Reawakened\n'
         'Upstream login handlers: ' + SOURCE_URL + '\n'
         'No working game server or verified Dauntless login is claimed.')
EXE_RELATIVE = Path('Archon/Binaries/Win64/Dauntless-Win64-Shipping.exe')
EXPECTED_SIZE = 151448856  # User-observed 2.1.1 installation; not a cryptographic identity check.


def inspect_client(root: Path) -> dict:
    exe = root / EXE_RELATIVE
    ca = root / 'Engine/Content/Certificates/cacert.pem'
    if not exe.is_file():
        raise ValueError('The original game executable is missing')
    if exe.is_symlink() or ca.is_symlink():
        raise ValueError('Symlinked game files are not supported')
    with exe.open('rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('Not a Windows executable')
        stream.seek(0x3c)
        offset = struct.unpack('<I', stream.read(4))[0]
        stream.seek(offset)
        if stream.read(6) != b'PE\0\0\x64\x86':
            raise ValueError('Expected a Windows x64 PE executable')
    if exe.stat().st_size != EXPECTED_SIZE:
        raise ValueError('This executable differs in size from the documented 2.1.1 copy; stop for review')
    with exe.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _digest(stream)
    return {'exe': str(exe.absolute()), 'size': exe.stat().st_size, 'sha256': digest,
            'build_verified_by_hash': False, 'ca_bundle_found': ca.is_file()}


def _digest(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


def windows_ready(exe: Path) -> None:
    if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
        raise ValueError('Use Windows PowerShell as administrator for the temporary hosts-file edit')
    no_running_game()
    env = os.environ.copy()
    env['REAWAKENED_PROBE_EXE'] = str(exe)
    signature_script = ("$s=Get-AuthenticodeSignature -LiteralPath $env:REAWAKENED_PROBE_EXE; "
                        "if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'Phoenix Labs'){exit 12}")
    check = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', signature_script],
                           env=env, capture_output=True, timeout=30)
    if check.returncode != 0:
        raise ValueError('The original Phoenix Labs signature could not be verified; nothing has been changed')


def no_running_game():
    result = subprocess.run(['tasklist.exe', '/FO', 'CSV', '/NH'], capture_output=True,
                            text=True, timeout=15, check=True)
    for row in csv.reader(result.stdout.splitlines()):
        if row and row[0].lower() in {'dauntless-win64-shipping.exe', 'archon-win64-shipping.exe'}:
            raise ValueError('Close Dauntless and Revived before this isolated test')


def flush_dns():
    subprocess.run(['ipconfig.exe', '/flushdns'], capture_output=True, timeout=15, check=True)


def run_probe(root: Path, home: Path, seconds: int, maintenance: bool):
    metadata = inspect_client(root)
    exe = Path(metadata['exe'])
    windows_ready(exe)
    if (home / 'active' / 'journal.json').exists():
        previous = json.loads((home / 'active' / 'journal.json').read_text())
        if not previous.get('restored'):
            raise ValueError('An earlier probe needs --restore before another test')
        # Keep previous backup and log; never overwrite a recovery set.
        (home / 'active').rename(home / ('completed-' + str(time.time_ns())))
    print(ABOUT)
    print('\nThis is a LOGIN/REQUEST TEST ONLY. No Ramsgate server or hunts exist.')
    print('It temporarily adds localhost mappings for Phoenix service names and a LOCAL CA')
    print('to this game only, and switches aside the shared WindowsClient config.')
    if not metadata['ca_bundle_found']:
        print('No original game CA bundle exists; a temporary CA file will be created and removed on restore.')
    print('The original EXE is not modified. Epic domains and system trust are not changed.')
    if maintenance:
        print('WARNING: maintenance uses the UNVERIFIED candidate {"isMaintenance": false}.')
    print('Unverified EOS subjects are local lookup keys, not secure Epic authentication.')
    if input('Type TEST to consent, or press Enter to cancel: ').strip() != 'TEST':
        print('Cancelled. No configuration changed.')
        return
    home.mkdir(parents=True, exist_ok=True)
    tls_dir = generate(home / ('tls-' + str(time.time_ns())))
    context = tls_context(tls_dir / 'server.pem', tls_dir / 'server-key.pem')
    db = Database(home / 'research.sqlite3')
    app = LoginPortApplication(db, allow_unverified_eos_sub=True,
                              maintenance_response={'isMaintenance': False} if maintenance else None)
    servers, workers = [], []
    process = None
    journal = None
    handler = None
    try:
        # Bind ALL four listeners before editing any files. Busy ports => no changes.
        for port, ctx in [(443, context), (80, None)]:
            for ip in ('127.0.0.1', '::1'):
                servers.append(make_server(app, ip, port, ctx))
        for server in servers:
            worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
            worker.start()
            workers.append(worker)
        # Real TLS verification against the newly generated root (not verify=False).
        client_context = ssl.create_default_context(cafile=str(tls_dir / 'ca.pem'))
        connection = http.client.HTTPSConnection('127.0.0.1', 443, context=client_context, timeout=5)
        try:
            connection.request('GET', '/health')
            response = connection.getresponse()
            if response.status != 200 or not json.loads(response.read()).get('experimental_login_port'):
                raise ValueError('Local backend self-check failed')
        finally:
            connection.close()
        config = Path(os.environ['LOCALAPPDATA']) / 'Archon/Saved/Config/WindowsClient'
        hosts = Path(os.environ['SystemRoot']) / 'System32/drivers/etc/hosts'
        ca = root / 'Engine/Content/Certificates/cacert.pem'
        names = sorted(s + '.steelyard.ca' for s in SERVICES) + ['steelyard.online']
        journal = prepare(home / 'active', ca, hosts, config, (tls_dir / 'ca.pem').read_bytes(), names)
        (home / 'active/client-inspection.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        flush_dns()
        for host in ('auth-prod.steelyard.ca', 'login-queue-prod.steelyard.ca'):
            addresses = {row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
            if not addresses or not addresses <= {'127.0.0.1', '::1'}:
                raise ValueError('DNS is not resolving exclusively to this computer; stopping')
        handler = logging.FileHandler(home / 'active/probe.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
        logger = logging.getLogger('reawakened.requests')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info('CLIENT_PROBE_BEGIN - subsequent requests may be from the real client')
        print('Starting the original client. Epic sign-in, when requested, is in Epic\'s browser UI.')
        print('Close the game when you see the outcome. This test stops automatically after', seconds, 'seconds.')
        print('Do not run Revived concurrently. Keep this console open for automatic restoration.')
        process = subprocess.Popen([str(exe), '-EpicPortal', '-AUTH_TYPE=accountportal',
                                    '-AUTH_LOGIN=unused', '-AUTH_PASSWORD=unused',
                                    '-windowed', '-ResX=1280', '-ResY=720', '-nosplash'], cwd=exe.parent)
        deadline = time.monotonic() + seconds
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(.25)
    finally:
        # Terminate ONLY the game process launched by this probe before restoring files.
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=8)
        try:
            if journal is not None:
                restore(journal)
                flush_dns()
                print('Original CA, hosts mappings and config restored. Local log:', home / 'active/probe.log')
        finally:
            for server in servers[:len(workers)]:
                server.shutdown()
            for server in servers:
                server.server_close()
            for worker in workers:
                worker.join(timeout=6)
            db.close()
            if handler:
                logging.getLogger('reawakened.requests').removeHandler(handler)
                handler.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--about', action='store_true')
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--run', action='store_true')
    mode.add_argument('--restore', action='store_true')
    parser.add_argument('--game-root', type=Path, default=Path(r'C:\Program Files\Epic Games\Dauntless'))
    parser.add_argument('--state', type=Path, default=Path(os.environ.get('LOCALAPPDATA', '.')) / 'DauntlessReawakenedProbe')
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--experimental-maintenance', action='store_true')
    args = parser.parse_args()
    try:
        if args.about:
            print(ABOUT)
        elif args.check:
            print(json.dumps(inspect_client(args.game_root), indent=2))
            print('Read-only check. This does not prove client/backend compatibility.')
        elif args.restore:
            if os.name != 'nt' or not ctypes.windll.shell32.IsUserAnAdmin():
                raise ValueError('Restore requires Windows administrator rights')
            no_running_game()
            restore(args.state / 'active/journal.json')
            flush_dns()
            print('Probe changes restored. Original files retained.')
        else:
            if not 30 <= args.seconds <= 600:
                raise ValueError('Probe duration must be 30 to 600 seconds')
            run_probe(args.game_root.absolute(), args.state.absolute(), args.seconds, args.experimental_maintenance)
    except KeyboardInterrupt:
        print('Probe interrupted. Check restoration message; use --restore if necessary.')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Errors may contain LOCAL paths; never ask users to publish whole state folders.
        print('STOP:', error, file=sys.stderr)
        print('Do not start Revived until any active probe is restored with --restore.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
