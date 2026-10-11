# SPDX-License-Identifier: AGPL-3.0-only
# Original work Copyright (C) 2026 gwog :3 (SyST3MDeV/Undaunted)
# Modified work Copyright (C) 2026 MysticFox / Pranav Karande
# Python adaptation for Dauntless Reawakened, 11 October 2026.
# Additional terms apply to upstream material: see ADDITIONAL_TERMS.md and NOTICE.md.
"""Bounded port of the inventory migration *gate*, not item transactions.

Upstream distinguishes POST /inventory/{characterId}/{changeList} from
GET /inventory/{accountId}/{characterId} and POST /inventory (transactions).
The NONE response below means that no migration is performed for the local
research profile. It does not import official saves, grant items or complete a hunt.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import unquote_to_bytes

SOURCE_URL = ('https://github.com/pranav158/Mystic-Paradox/blob/'
              'fcf915cb918edbe9f030d03b62c94f4879dc655a/'
              'ParadoxBackend/src/routes/inventory.ts')


@dataclass(frozen=True)
class MigrationRequest:
    character_id: str = field(repr=False)
    build: str = field(repr=False)


def parse_migration_path(endpoint: str) -> MigrationRequest | None:
    """Parse exactly two bounded slots, including upstream's empty-character form.

    This recognises a route shape, NOT the original game's supported build set.
    Both decoded values remain private; never log or interpolate them into paths.
    """
    if not isinstance(endpoint, str) or len(endpoint) > 1024:
        return None
    if any(ord(c) < 33 or ord(c) == 127 for c in endpoint):
        return None
    parts = endpoint.split('/')
    if len(parts) != 4 or parts[:2] != ['', 'inventory'] or not parts[3]:
        return None
    try:
        character, build = (unquote_to_bytes(part).decode('utf-8', errors='strict')
                            for part in parts[2:])
    except (UnicodeError, ValueError):
        return None
    # No slashes, controls, query text, arbitrary Unicode or double-encoded values.
    if character and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', character):
        return None
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:+-]{0,127}', build):
        return None
    return MigrationRequest(character, build)


def is_empty_migration_body(body: bytes) -> bool:
    """Only the no-payload case is implemented; never acknowledge unknown writes.

    Non-empty objects, arrays, scalars, malformed JSON and transaction-shaped
    bodies are rejected rather than silently discarded as a successful migration.
    """
    if not isinstance(body, bytes) or len(body) > 4096:
        return False
    if not body.strip():
        return True
    try:
        value = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        return False
    return isinstance(value, dict) and not value


def no_migration_response() -> dict:
    # Port of inventory.ts's response, not a generic empty-success fallback.
    return {'code': 'NONE', 'message': ''}
