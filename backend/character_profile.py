# SPDX-License-Identifier: AGPL-3.0-only
# Based on Mystic Paradox NormalizeCharacterData: Copyright (C) 2026
# gwog / Gregory Morford and MysticFox / Pranav Karande. See NOTICE.md.
"""Opt-in 2.1.1 character-profile experiment, only for an isolated database copy.

Ports missing-field initialization, NOT the old progression enum, tutorial
bypass, quests, rewards, cosmetics or authoritative-game-server write override.
An initialized profile is not evidence of login or a playable character.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from .database import Database

PROFILE_NAME = 'mystic-profile-211-v2'
TARGET_CHANGELIST = '682875'
MAX_DATA_BYTES = 262144
FIELDS = frozenset({'RecentPlayers', 'CharacterFlagData', 'LoginFlagData',
                    'PlayerDataRepair', 'AppearanceData', 'LoginTime',
                    'LastLoginTime', 'LastChangelist'})
# A/B the seven added fields in clean database snapshots.
PROFILE_VARIANTS = {
    'full': FIELDS,
    'without-appearance': FIELDS - {'AppearanceData'},
    'without-flags': FIELDS - {'CharacterFlagData', 'LoginFlagData', 'PlayerDataRepair'},
    'without-metadata': FIELDS - {'LoginTime', 'LastLoginTime', 'LastChangelist'},
    'appearance-only': frozenset({'AppearanceData'}),
    'flags-only': frozenset({'CharacterFlagData', 'LoginFlagData', 'PlayerDataRepair'}),
    'metadata-only': frozenset({'LoginTime', 'LastLoginTime', 'LastChangelist'}),
    'baseline': frozenset(),
}
# 2.1.1 names, never Mystic's 1.12 numeric ordinal ordering.
CREATED_STATES = frozenset({'SavedCharacter', 'TrainingGroundsComplete',
    'DefeatedGnasher', 'EnteredRamsgate', 'FinishedFirstHunt', 'FinishedSecondHunt'})


def _object(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_DATA_BYTES:
        raise ValueError('Invalid bounded character profile')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate profile field')
            result[key] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique)
    except (ValueError, RecursionError):
        raise ValueError('Invalid character profile JSON') from None
    if not isinstance(value, dict) or any(type(v) is not str for v in value.values()):
        raise ValueError('Profile fields must remain strings for 2.1.1')
    return value


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def normalize_profile(text: str, *, previous: str | None = None,
                      now: datetime | None = None,
                      include_fields: frozenset[str] = FIELDS) -> tuple[str, tuple[str, ...]]:
    """Fill missing keys only. Preserve supplied strings, unknown fields and state.

    New dates/LastChangelist are synthetic test metadata, not recovered history.
    Existing values (including empty strings) are deliberately not overwritten.
    A new appearance contains the common structure, NOT unverified 1.12 cosmetics.
    """
    if not isinstance(include_fields, frozenset) or not include_fields.issubset(FIELDS):
        raise ValueError('Unrecognised character profile fields')
    data = _object(text)
    old = _object(previous) if previous is not None else {}
    missing = include_fields.difference(data)
    if not missing:
        return text, ()  # Keep exact bytes when no repair is needed.
    instant = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError('Profile time must be timezone-aware')
    timestamp = instant.astimezone(timezone.utc).strftime('%Y.%m.%d-%H.%M.%S')
    state = data.get('PlayerAccountProgressStep')
    appearance = {
        'CreationState': ('EArchonCharacterCreationState::FaceComplete'
                          if state in CREATED_STATES else
                          'EArchonCharacterCreationState::NewCharacter'),
        'Data': [{'SkeletalMeshComponentName': 'Head Slot', 'MorphData': []}],
        'AssetReferences': [], 'StringData': [],
    }
    defaults = {
        'RecentPlayers': _json({'RecentPlayers': [], 'Version': 0}),
        'CharacterFlagData': _json({'Flags': []}),
        'LoginFlagData': _json({'Flags': []}),
        'PlayerDataRepair': _json({'Data': []}),
        'AppearanceData': _json(appearance),
        'LoginTime': timestamp,
        'LastLoginTime': data.get('LoginTime', old.get('LoginTime', timestamp)),
        'LastChangelist': TARGET_CHANGELIST,
    }
    # A retry that omits a generated key reuses its stored value, not a new clock.
    for key in sorted(missing):
        data[key] = old[key] if key in old else defaults[key]
    result = _json(data)
    _object(result)
    return result, tuple(sorted(missing))


class ProfileDatabase(Database):
    """Use ONLY with a disposable/cloned DB selected by tools.profile_database.

    Normalize existing rows atomically before listeners start. Wire versions stay
    unchanged at that point; subsequent client saves keep ordinary version checks.
    Normalization is not run in GET and does not silently change a live version.
    """
    def __init__(self, path, *, variant: str = 'full'):
        if str(path) != ':memory:' and (Path(path).parent.name != 'profile-tests' or
                not re.fullmatch(r'mystic-profile-[0-9a-f]{32}\.sqlite3', Path(path).name)):
            raise ValueError('ProfileDatabase requires an isolated profile snapshot')
        if variant not in PROFILE_VARIANTS:
            raise ValueError('Unknown profile variant')
        self.variant = variant
        self.include_fields = PROFILE_VARIANTS[variant]
        super().__init__(path)
        self.profile_summary = {'profile': PROFILE_NAME, 'variant': variant, 'characters_changed': 0,
                                'fields_added': 0, 'original_database_used': False,
                                'snapshot_accounts': 0, 'snapshot_characters': 0}
        try:
            with self._lock, self._db:
                # Only counts. If the snapshot is empty, do not mistake a newly
                # created local account for a previously persisted identity.
                self.profile_summary['snapshot_accounts'] = self._db.execute(
                    'SELECT COUNT(*) FROM accounts').fetchone()[0]
                self.profile_summary['snapshot_characters'] = self._db.execute(
                    'SELECT COUNT(*) FROM characters').fetchone()[0]
                rows = self._db.execute('SELECT id,account_id,data FROM characters').fetchmany(129)
                if len(rows) > 128:
                    raise ValueError('Too many characters for the solo profile test')
                now = datetime.now(timezone.utc)
                for row in rows:
                    normalized, added = normalize_profile(row['data'], now=now, include_fields=self.include_fields)
                    if added:
                        self._db.execute('UPDATE characters SET data=? WHERE id=? AND account_id=?',
                                         (normalized, row['id'], row['account_id']))
                        self.profile_summary['characters_changed'] += 1
                        self.profile_summary['fields_added'] += len(added)
        except Exception:
            self.close()
            raise

    def create(self, account_id, name, seed):
        normalized, _ = normalize_profile(seed, include_fields=self.include_fields)
        return super().create(account_id, name, normalized)

    def save(self, account_id, character_id, data, version, *, allow_identical_retry=False):
        # Validate ownership/version through the same Database.save implementation.
        # RLock keeps read-normalize-write atomic against another client update.
        if not isinstance(character_id, str):
            raise ValueError('Invalid character update')
        with self._lock:
            row = self._db.execute('SELECT data FROM characters WHERE id=? AND account_id=?',
                                   (character_id, account_id)).fetchone()
            if row is None:
                raise KeyError('Character not found')
            normalized, _ = normalize_profile(data, previous=row['data'], include_fields=self.include_fields)
            return super().save(account_id, character_id, normalized, version,
                                allow_identical_retry=allow_identical_retry)
