"""Bounded, value-free diagnostics for local Dauntless protocol experiments.

No raw paths, request bodies, bearer tokens, account IDs, character IDs,
dynamic JSON keys or payload values are emitted.
"""
from __future__ import annotations

import json
import time

SAFE_FIELDS = frozenset({
    'code', 'message', 'payload', 'data', 'name', 'id', 'characterId',
    'updateVersion', 'accountId', 'accountType', 'linkedAccounts',
    'accountMappings', 'balances', 'refreshInventory', 'characters',
    'instancedItems', 'stackedItems', 'status', 'success', 'serverInfo',
    'ScheduledItems', 'EventConfigs', 'GlobalConfig',
    'DisallowedIslandContentAssets', 'isMaintenance', 'entitlements',
    'username', 'language', 'isSubscribed',
})
MAX_FIELDS = 24


def shape(value: object) -> str:
    """Only static, allowlisted field names and primitive types; never values."""
    if value is None:
        return 'null'
    if isinstance(value, dict):
        entries = []
        for key, item in list(value.items())[:MAX_FIELDS]:
            if key in SAFE_FIELDS:
                entries.append(key + ':' + kind(item))
            else:
                entries.append('other:' + kind(item))
        return 'object[' + ','.join(entries) + ']'
    return kind(value)


def kind(value: object) -> str:
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'boolean'
    if type(value) is int:
        return 'integer'
    if type(value) is float:
        return 'number'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, dict):
        return 'object'
    return 'other'


def diagnostic_record(method: str, route: str, status: int, payload: object,
                      request_size: int, started_ns: int, *, session_valid: bool | None) -> str:
    if session_valid is None:
        session = 'not_checked'
    else:
        session = 'valid' if session_valid else 'absent_or_invalid'
    return json.dumps({
        'method': method if method in ('GET','POST','PUT','DELETE','HEAD','OPTIONS','PATCH') else 'OTHER',
        'route': route if route.isascii() and len(route) <= 80 and
                 all(c.isalnum() or c in '-_' for c in route) else 'unknown',
        'status': int(status),
        'duration_ms': round(max(0, time.perf_counter_ns()-started_ns)/1_000_000, 3),
        'request_bytes': max(0, int(request_size)),
        'response_shape': shape(payload),
        'session': session,
    }, separators=(',', ':'))
