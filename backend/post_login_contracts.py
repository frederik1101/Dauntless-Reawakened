# SPDX-License-Identifier: AGPL-3.0-only
# Original work Copyright (C) 2026 gwog :3 / SyST3MDeV/Undaunted.
# Modified work Copyright (C) 2026 MysticFox / Pranav Karande.
# Selected response-shape adaptation; see NOTICE.md and ADDITIONAL_TERMS.md.
"""Post-login contracts. Research defaults, not authentic 2.1.1 live-ops data.

Mystic-Paradox tuning.ts/store.ts at 386302c1333fe3dfcb2baf176edc101e200f5081.
Mapping shape: Revived docs/findings/social.md blob 4ea2ddf4444f0c018b109e6c0aaba15545ca6f64.
The mapping parser evidence is 1.4.4; its request was also observed on 2.1.1.
"""
from __future__ import annotations

import copy
import json
import re
from .research_identity import same_identity

REVISION = 'character-profile-20261012.6'
MAX_BODY = 65536
TUNING = {
    'seasonal_event_schedule': {'ScheduledItems': []},
    'huntpass_xp_config': {
        'EventConfigs': [],
        'GlobalConfig': {'DifficultyBias': 1.0, 'GlobalMultiplier': 1.0, 'MaxXPAwarded': 200},
    },
    'island_content_config': {'DisallowedIslandContentAssets': []},
}
TUNING_LABELS = {
    'seasonal_event_schedule': 'post-login-tuning-seasonal-events',
    'huntpass_xp_config': 'post-login-tuning-huntpass-xp',
    'island_content_config': 'post-login-tuning-island-content',
}


class UnsupportedRequest(ValueError):
    """Recognised route, but this operation/body is not implemented."""


def read_object(body: bytes, *, empty: bool = False) -> dict:
    if not isinstance(body, bytes) or len(body) > MAX_BODY:
        raise ValueError('Invalid post-login body')
    if empty and not body:
        return {}

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError('Nonfinite number')

    try:
        result = json.loads(body, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError('Invalid post-login JSON') from None
    if not isinstance(result, dict):
        raise ValueError('Expected an object')
    return result


def identifier(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 256 and
            all(33 <= ord(c) <= 126 for c in value))


def mapping_request(body: bytes) -> tuple[str, tuple[str, ...]]:
    data = read_object(body)
    if set(data) != {'srcAccountType', 'ids'}:
        raise UnsupportedRequest('Unsupported mapping request')
    source = data['srcAccountType']
    ids = data['ids']
    if not isinstance(source, str) or source.lower() not in ('epic', 'phoenix'):
        raise UnsupportedRequest('Unsupported account type')
    if not isinstance(ids, list) or len(ids) > 100 or any(not identifier(i) for i in ids):
        raise ValueError('Invalid mapping IDs')
    return source.lower(), tuple(dict.fromkeys(ids))


def mapping_response(body: bytes, account: str, epic: str | None) -> dict:
    """Only map the authenticated session's own binding; never arbitrary IDs."""
    source, ids = mapping_request(body)
    if not identifier(account) or (epic is not None and not identifier(epic)):
        raise ValueError('Invalid session binding')
    mappings = {}
    if epic is not None:
        asked, answer, kind = (epic, account, 'phoenix') if source == 'epic' else (account, epic, 'epic')
        for requested in ids:
            if same_identity(requested, asked):
                mappings[requested] = {'accountId': answer, 'accountType': kind}
    # Root and wrapped object are both documented in Revived's compatibility reply.
    return {'accountMappings': mappings, 'code': 'OK', 'message': '',
            'payload': {'accountMappings': copy.deepcopy(mappings)}}


def public_account_response(body: bytes, account: str, epic: str | None) -> dict:
    data = read_object(body)
    if set(data) != {'accountId'}:
        raise UnsupportedRequest('Unsupported public-account query')
    if not identifier(data['accountId']):
        raise ValueError('Invalid account ID')
    if not same_identity(data['accountId'], account):
        raise PermissionError('Other account not available in solo test')
    # Do not claim the local hashed Phoenix ID is an Epic ID. A lab account has none.
    links = [] if epic is None else [{'accountId': epic, 'accountType': 'epic'}]
    return {'accountId': account, 'username': 'LocalSlayer', 'linkedAccounts': links,
            'isSubscribed': True, 'language': None}


def reconcile_request(body: bytes) -> None:
    data = read_object(body, empty=True)
    # The documented request carries authorization, not purchases/receipts/grants.
    if set(data) - {'authorization'}:
        raise UnsupportedRequest('External store transaction not implemented')
    value = data.get('authorization')
    if value is not None and (not isinstance(value, str) or len(value) > 16384):
        raise ValueError('Invalid store authorization field')
    # Never log/store/echo this field; the HTTP bearer remains the local authority.


def reconcile_response(balances: dict) -> dict:
    if not isinstance(balances, dict):
        raise ValueError('Invalid balance snapshot')
    result = {'CURRENCY_NOTES': 0, 'CURRENCY_PLATINUM': 0}
    for key, value in balances.items():
        if (not isinstance(key, str) or not re.fullmatch(r'CURRENCY_[A-Z0-9_]{1,64}', key)
                or type(value) is not int or not 0 <= value < 2**31):
            raise ValueError('Invalid local balance')
        result[key] = value
    result.update({'id_' + key.lower(): value for key, value in tuple(result.items())})
    # Read-only local snapshot: no external purchase or inventory grant is claimed.
    return {'balances': result, 'refreshInventory': False}


def tuning_response(blob: str) -> dict:
    if blob not in TUNING:
        raise KeyError('Unimplemented tuning blob')
    # 2.1.1's wrapped response uses a string reader for code. Keep payload
    # as an OBJECT: the game serializes it to its internal string itself.
    # This is a type correction, not proof that it caused the login reset.
    return {'code': 'OK', 'message': 'OK', 'payload': copy.deepcopy(TUNING[blob])}


def creator_response() -> dict:
    # Shape from store.ts, but no invented affiliate code or active enrollment.
    # Negative empty state is a research choice, not a captured 2.1.1 response.
    return {'expirationDate': '1970-01-01T00:00:00.000Z', 'slug': '', 'success': False}
