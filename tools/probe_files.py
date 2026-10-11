# SPDX-License-Identifier: AGPL-3.0-only
"""Journalled, reversible LOCAL test edits. No trust-store or game-binary changes.

This helper does not run a game, elevate privileges or contact any service.
It is tested against temporary paths; the Windows wrapper chooses the real ones.
"""
from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path

MARKER = '.reawakened-probe'


def _plain_path(path: Path) -> None:
    for node in (path, *path.parents):
        reparse = node.exists() and (getattr(node.lstat(), 'st_file_attributes', 0) &
                                     getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if node.is_symlink() or reparse:
            raise ValueError('Symlink/junction targets are not supported')


def journal_write(path: Path, data: dict) -> None:
    temporary = path.with_suffix('.pending')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def hosts_addition(original: bytes, names: list[str], marker: str) -> bytes:
    if b'\x00' in original:
        raise ValueError('Unsupported hosts-file encoding')
    permitted = set(names)
    if not permitted or any(not n.isascii() or any(c.isspace() for c in n) for n in permitted):
        raise ValueError('Invalid host allowlist')
    for line in original.decode('utf-8-sig', errors='strict').splitlines():
        fields = line.split('#', 1)[0].split()
        if any(n.lower() in permitted for n in fields[1:]):
            raise ValueError('An existing hosts mapping overlaps the probe; refusing to change it')
    return ('\r\n# BEGIN REAWAKENED ' + marker + '\r\n' +
            ''.join(f'{ip} {name}\r\n' for name in sorted(permitted)
                    for ip in ('127.0.0.1', '::1')) +
            '# END REAWAKENED ' + marker + '\r\n').encode('ascii')


def prepare(state: Path, ca: Path, hosts: Path, config: Path,
            public_ca: bytes, names: list[str]) -> Path:
    """Save rollback data before the first change. On failure, try rollback immediately."""
    state, ca, hosts, config = [p.absolute() for p in (state, ca, hosts, config)]
    for p in (state, ca, hosts, config):
        _plain_path(p)
    if state.exists():
        raise FileExistsError('Probe state already exists; restore it first')
    if not hosts.is_file():
        raise ValueError('Original hosts file must exist')
    if ca.exists() and not ca.is_file():
        raise ValueError('CA path exists but is not a regular file')
    missing_dirs = []
    if not ca.exists():
        parent = ca.parent
        while not parent.exists():
            missing_dirs.append(parent)
            parent = parent.parent
        if not parent.is_dir():
            raise ValueError('CA ancestor is not a directory')
        if len(missing_dirs) > 3:
            raise ValueError('Too many missing CA parent directories; refusing unsafe creation')
    if config.exists() and not config.is_dir():
        raise ValueError('Config path must be a directory')
    if b'-----BEGIN CERTIFICATE-----' not in public_ca:
        raise ValueError('Expected a public PEM certificate')
    ca_existed = ca.is_file()
    original_ca, original_hosts = (ca.read_bytes() if ca_existed else b''), hosts.read_bytes()
    marker = uuid.uuid4().hex
    host_block = hosts_addition(original_hosts, names, marker)
    ca_block = (f'\n# BEGIN REAWAKENED {marker}\n'.encode() + public_ca.rstrip() +
                f'\n# END REAWAKENED {marker}\n'.encode())
    backup = config.with_name(config.name + '.reawakened-backup-' + marker)
    after = config.with_name(config.name + '.reawakened-test-' + marker)
    if backup.exists() or after.exists():
        raise FileExistsError('Config backup collision')
    state.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name, value in [('ca.original', original_ca), ('hosts.original', original_hosts),
                        ('ca.block', ca_block), ('hosts.block', host_block)]:
        fd = os.open(state / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
    record = {'version': 1, 'marker': marker, 'ca': str(ca), 'hosts': str(hosts),
              'config': str(config), 'config_backup': str(backup), 'config_after': str(after),
              'config_existed': config.exists(), 'ca_existed': ca_existed,
              'ca_created_dirs': [str(p) for p in missing_dirs], 'restored': False}
    journal = state / 'journal.json'
    journal_write(journal, record)
    try:
        # Backups and complete rollback plan already exist at this point.
        if record['config_existed']:
            config.rename(backup)
        config.mkdir(parents=True, exist_ok=False)
        (config / MARKER).write_text(marker, encoding='ascii')
        for directory in reversed(missing_dirs):
            directory.mkdir(exist_ok=False)
        ca.write_bytes(original_ca + ca_block)
        hosts.write_bytes(original_hosts + host_block)
    except BaseException:
        restore(journal)
        raise
    return journal


def restore(journal: Path) -> None:
    """Remove only our additions; preserve unrelated later file edits or fail closed."""
    record = json.loads(journal.read_text(encoding='utf-8'))
    if record.get('version') != 1:
        raise ValueError('Unknown journal version')
    if record['restored']:
        return
    state = journal.parent
    updates = []
    # Validate all file changes before restoring any.
    for name in ('ca', 'hosts'):
        target = Path(record[name])
        _plain_path(target)
        current = target.read_bytes() if target.is_file() else b''
        original = (state / (name + '.original')).read_bytes()
        block = (state / (name + '.block')).read_bytes()
        if current == original and (name != 'ca' or record.get('ca_existed', True) or not target.exists()):
            continue
        if current.count(block) != 1:
            raise ValueError(f'{name} was modified during the probe; backup retained, refusing overwrite')
        updates.append((target, current.replace(block, b'', 1)))
    config, backup, after = [Path(record[k]) for k in ('config', 'config_backup', 'config_after')]
    for path in (config, backup, after):
        _plain_path(path)
    is_probe = config.exists() and (
        ((config / MARKER).is_file() and (config / MARKER).read_text(encoding='ascii') == record['marker'])
        or (backup.exists() and config.is_dir() and not any(config.iterdir())))
    # If preparation failed before the rename, leave the untouched directory alone.
    untouched = record['config_existed'] and config.exists() and not backup.exists() and not is_probe
    if record['config_existed'] and not backup.exists() and not untouched:
        raise ValueError('Original config backup is missing; refusing unsafe restore')
    if config.exists() and not is_probe and not untouched:
        raise ValueError('Unrecognised config directory; refusing overwrite')
    if is_probe and after.exists():
        raise ValueError('Test-config archive already exists')
    for target, value in updates:
        if target == Path(record['ca']) and not record.get('ca_existed', True):
            if value:
                raise ValueError('Temporary CA contains unexpected data; refusing deletion')
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(value)
    if is_probe:
        config.rename(after)  # Retain test configuration locally; never upload it.
    elif config.exists() and not untouched:
        raise ValueError('Cannot restore config safely')
    if backup.exists():
        backup.rename(config)
    for directory_name in record.get('ca_created_dirs', []):
        directory = Path(directory_name)
        _plain_path(directory)
        if directory.exists():
            try:
                directory.rmdir()  # Only remove our empty directory; never delete other files.
            except OSError as exc:
                raise ValueError('Temporary CA directory contains other files; retained for review') from exc
    record['restored'] = True
    journal_write(journal, record)
