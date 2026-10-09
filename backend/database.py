"""Transactional, account-scoped storage for the 2.1.1 research backend.

No automatic import of the old prototype's characters.json. Keep that file intact.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path


class VersionConflict(ValueError):
    pass


def character_data(value: object) -> str:
    if not isinstance(value, str) or len(value.encode('utf-8')) > 262144:
        raise ValueError('Character data must be a bounded JSON string')
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or any(not isinstance(v, str) for v in parsed.values()):
        raise ValueError('Character data must contain only string values')
    return value


class Database:
    def __init__(self, path: str | Path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys=ON')
        self._db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY, username TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
                name TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS character_account ON characters(account_id);
        ''')
        self._db.commit()

    def account(self, subject: str) -> dict:
        if not isinstance(subject, str) or not subject or len(subject) > 512:
            raise ValueError('Invalid local identity key')
        # Stable lookup, not an authentication check and not an anonymisation guarantee.
        account_id = hashlib.sha256(('reawakened-211:' + subject).encode()).hexdigest()[:32]
        with self._lock, self._db:
            self._db.execute('INSERT OR IGNORE INTO accounts VALUES (?,?)',
                             (account_id, 'LocalSlayer'))
        return {'accountId': account_id, 'username': 'LocalSlayer'}

    def get(self, account_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                'SELECT id,name,version AS updateVersion,data FROM characters '
                'WHERE account_id=? ORDER BY rowid', (account_id,)).fetchall()
        return [dict(row) for row in rows]

    def create(self, account_id: str, name: object, seed: str) -> dict:
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise ValueError('Invalid character name')
        if any(ord(c) < 32 for c in name):
            raise ValueError('Invalid character name')
        character_data(seed)
        record = {'id': uuid.uuid4().hex, 'name': name}
        with self._lock, self._db:
            self._db.execute('INSERT INTO characters VALUES (?,?,?,?,?)',
                             (record['id'], account_id, name, 0, seed))
        return record

    def save(self, account_id: str, character_id: object, data: object, version: object) -> dict:
        if not isinstance(character_id, str) or type(version) is not int or not 0 <= version < 2**31:
            raise ValueError('Invalid character update')
        data = character_data(data)
        with self._lock, self._db:
            row = self._db.execute('SELECT version FROM characters WHERE id=? AND account_id=?',
                                   (character_id, account_id)).fetchone()
            if row is None:
                raise KeyError('Character not found')
            if version <= row['version']:
                raise VersionConflict('Stale character version')
            self._db.execute('UPDATE characters SET version=?,data=? WHERE id=? AND account_id=?',
                             (version, data, character_id, account_id))
        return {'data': data}

    def close(self) -> None:
        with self._lock:
            self._db.close()
