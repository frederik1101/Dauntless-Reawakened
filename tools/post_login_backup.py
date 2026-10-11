# SPDX-License-Identifier: AGPL-3.0-only
"""Backup an existing SQLite database before the additive post-login schema update."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def backup_before_post_login(path: Path) -> Path | None:
    from tools.probe_files import _plain_path
    path = path.absolute()
    _plain_path(path)
    if not path.exists():
        return None
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    destination = None
    target = None
    created = False
    try:
        if source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_store_balances'").fetchone():
            return None
        target = path.with_name('players.before-post-login-' + str(time.time_ns()) + '.sqlite3')
        with target.open('xb'):
            pass
        created = True
        destination = sqlite3.connect(str(target), timeout=5)
        deadline = time.monotonic() + 15
        def progress(_status, _remaining, _total):
            if time.monotonic() >= deadline:
                raise TimeoutError('SQLite backup timed out; original retained')
        source.backup(destination, pages=64, progress=progress, sleep=0.1)
        destination.close()
        destination = None
        return target
    except BaseException:
        if destination is not None:
            destination.close()
        if created and target is not None:
            target.unlink(missing_ok=True)
        raise
    finally:
        source.close()
