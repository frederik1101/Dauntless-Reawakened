# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded protocol metadata, never raw tokens, bodies, IDs or dynamic JSON keys.

Identity aliases are HMACs under a random process-only key. They correlate calls
within one server run, not across runs; they are not proof of authentication.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from .safe_diagnostics import kind, shape

_KEY = secrets.token_bytes(32)
MAX_JSON_BYTES = 262144
PROGRESS = frozenset({'New', 'SavedCharacter', 'TrainingGroundsComplete',
                     'DefeatedGnasher', 'EnteredRamsgate', 'FinishedFirstHunt',
                     'FinishedSecondHunt'})
DATA_FIELDS = frozenset({'PlayerAccountProgressStep', 'AppearanceData', 'RecentPlayers',
    'CharacterFlagData', 'LoginFlagData', 'PlayerDataRepair', 'LoginTime', 'LastLoginTime',
    'LastChangelist', 'HasFinishedTutorial'})
PUBLIC_ROUTES = frozenset({'health', 'status-banner', 'experimental-maintenance',
    'platform-features', 'account-link', 'candidate-account-link-epiceos', 'login-queue'})


def identity_alias(value: str, purpose: str) -> str:
    if not isinstance(value, str) or len(value) > 512:
        return 'invalid'
    return hmac.new(_KEY, (purpose + ':' + value).encode(), hashlib.sha256).hexdigest()[:16]


def object_body(body: bytes):
    if not isinstance(body, bytes) or not body or len(body) > MAX_JSON_BYTES:
        return None
    try:
        result = json.loads(body)
        return result if isinstance(result, dict) else None
    except (ValueError, UnicodeError, RecursionError):
        return None


def data_summary(value: object) -> dict:
    result = {'wire_type': kind(value)}
    if not isinstance(value, str) or len(value) > MAX_JSON_BYTES:
        return result
    try:
        if len(value.encode('utf-8')) > MAX_JSON_BYTES:
            return {**result, 'decode': 'too_large'}
        data = json.loads(value)
    except (ValueError, UnicodeError, RecursionError):
        return {**result, 'decode': 'invalid_json'}
    if not isinstance(data, dict):
        return {**result, 'decode': 'not_object'}
    result.update({'decode': 'object', 'field_count': len(data),
                   'all_values_strings': all(isinstance(v, str) for v in data.values()),
                   'unknown_field_count': sum(k not in DATA_FIELDS for k in data),
                   'known_field_types': {k: kind(v) for k, v in data.items() if k in DATA_FIELDS}})
    progress = data.get('PlayerAccountProgressStep')
    result['progress_state'] = progress if isinstance(progress, str) and progress in PROGRESS else 'unrecognised_or_missing'
    # Presence is load-bearing in 2.1.1 even when its value says false.
    result['legacy_tutorial_key_present'] = 'HasFinishedTutorial' in data
    for field in ('AppearanceData', 'RecentPlayers', 'CharacterFlagData', 'LoginFlagData', 'PlayerDataRepair'):
        if field not in data:
            continue
        raw = data[field]
        entry = {'wire_type': kind(raw)}
        if isinstance(raw, str):
            try:
                inner = json.loads(raw)
                entry['decoded_type'] = kind(inner)
                # Field names inside these blobs may be private; emit types/counts only.
                if isinstance(inner, (dict, list)):
                    entry['element_count'] = len(inner)
            except (ValueError, UnicodeError, RecursionError):
                entry['decoded_type'] = 'invalid_json'
        result.setdefault('nested_data', {})[field] = entry
    return result


def character_summary(payload: object) -> dict:
    if isinstance(payload, list):
        result = {'character_count': len(payload), 'sample_limit': 8, 'characters': []}
        for row in payload[:8]:
            if not isinstance(row, dict):
                result['characters'].append({'type': kind(row)})
                continue
            version = row.get('updateVersion')
            result['characters'].append({
                'character_alias': identity_alias(row.get('id'), 'character'),
                'required_field_types': {k: kind(row.get(k)) for k in ('id','name','updateVersion','data')},
                'version': version if type(version) is int and 0 <= version < 2**31 else None,
                'data': data_summary(row.get('data')),
            })
        return result
    if isinstance(payload, dict) and 'data' in payload:
        return {'data': data_summary(payload['data'])}
    return {'shape': shape(payload)}


def authentication(app, headers, route: str) -> dict:
    from .application import bearer
    lower = {k.lower(): v for k, v in headers.items()}
    if route == 'epiceos-session-research':
        return {'input': 'external_exchange_not_a_local_token'}
    try:
        token = bearer(lower)
    except PermissionError:
        return {'input': 'public_no_local_session_required' if route in PUBLIC_ROUTES else
                ('missing_bearer' if 'authorization' not in lower else 'malformed_bearer')}
    session = app.sessions.resolve(token)
    if session is None:
        return {'input': 'unrecognised_local_bearer'}
    return {'input': 'valid_local_session',
            'session_alias': identity_alias(session.session_id, 'session'),
            'account_alias': identity_alias(session.account_id, 'account'),
            'external_binding_present': bool(getattr(session, 'linked_epic_id', None))}


def response_details(route: str, payload: object, request_body: bytes) -> dict:
    """Only route-specific, finite metadata; no generic JSON dump."""
    details = {}
    if isinstance(payload, dict):
        if 'code' in payload:
            code = payload['code']
            details['code_type'] = kind(code)
            if isinstance(code, str) and code in {'OK','NONE','ERROR'}:
                details['code_enum'] = code
        if 'payload' in payload:
            details['payload_shape'] = shape(payload['payload'])
    request = object_body(request_body)
    if route == 'character':
        details['character_response'] = character_summary(payload)
        if request is not None:
            version = request.get('updateVersion')
            details['character_request'] = {
                'required_field_types': {k: kind(request.get(k)) for k in ('characterId','data','updateVersion')},
                'version': version if type(version) is int and 0 <= version < 2**31 else None,
                'character_alias': identity_alias(request.get('characterId'), 'character'),
                'data': data_summary(request.get('data')),
            }
            if isinstance(payload, dict) and 'data' in payload and 'data' in request:
                details['saved_data_matches_request'] = payload['data'] == request['data']
    if route == 'post-login-account-mapping' and isinstance(payload, dict):
        mapping = payload.get('accountMappings')
        ids = request.get('ids') if request is not None else None
        if isinstance(mapping, dict) and isinstance(ids, list) and len(ids) <= 100 and all(isinstance(i,str) for i in ids):
            details['mapping'] = {'requested_count': len(ids), 'returned_count': len(mapping),
                                  'all_requested_ids_mapped': all(i in mapping for i in ids)}
    if route == 'ramsgate-register':
        details['register_reply'] = 'empty_object_ack' if isinstance(payload, dict) and not payload else 'other_shape'
    return details
