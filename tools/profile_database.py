# SPDX-License-Identifier: AGPL-3.0-only
"""Create a fresh SQLite snapshot for the opt-in profile test. Never edit source.

Every invocation gets its own new file. The existing TLS folder remains in use.
There is no automatic replacement, promotion or merge into players.sqlite3.
"""
from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import time
import uuid
from tools.probe_files import _plain_path


def profile_snapshot(home: Path) -> Path:
    home = Path(home).absolute()
    source = home / 'players.sqlite3'
    directory = home / 'profile-tests'
    for path in (home, source, directory):
        _plain_path(path)
    home.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=True)
    destination = directory / ('mystic-profile-' + uuid.uuid4().hex + '.sqlite3')
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    # Keep an incomplete copy on failure for inspection; never select/reuse it.
    out = sqlite3.connect(str(destination), timeout=5)
    try:
        if source.exists():
            if not source.is_file() or source.stat().st_size > 128*1024*1024:
                raise ValueError('Profile source is not a database file')
            started = time.monotonic()
            def progress(status, remaining, total):
                if total > 65536 or time.monotonic() - started > 15:
                    raise ValueError('Profile snapshot exceeds solo test budget')
            original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)
            try:
                if original.execute('PRAGMA quick_check(1)').fetchone() != ('ok',):
                    raise ValueError('Source database integrity check failed')
                original.backup(out, pages=128, progress=progress, sleep=.05)
            finally:
                original.close()
        if out.execute('PRAGMA quick_check(1)').fetchone() != ('ok',):
            raise ValueError('Profile snapshot integrity check failed')
    finally:
        out.close()
    return destination
