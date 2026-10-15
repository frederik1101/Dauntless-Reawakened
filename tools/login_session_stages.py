# SPDX-License-Identifier: AGPL-3.0-only
"""Summarize socket-written 2.1.1 requests per process-local session.

Input is already-sanitized PROTOCOL_TRACE metadata; no raw identity or token
is returned. Session aliases are used in memory only, never serialized.
This describes server observations, not real Epic verification or client parsing.
"""
from __future__ import annotations

import re

MAX_SESSIONS = 16
HEX_ALIAS = re.compile(r'[0-9a-f]{16}\\Z')
POST_ROUTES = frozenset({
    'ported-inventory-migration-none', 'ported-migration-trigger',
    'inventory-bootstrap', 'loadouts-bootstrap', 'loadout-slots',
    'progression-config-bootstrap', 'progression-objectives-bootstrap',
    'progression-tracks-bootstrap', 'cooldowns-bootstrap', 'bounties-bootstrap',
    'escalation-bootstrap', 'post-login-tuning-seasonal-events',
    'post-login-tuning-huntpass-xp', 'post-login-tuning-island-content',
    'post-login-store-reconcile', 'post-login-store-balance',
    'post-login-account-mapping', 'post-login-public-account',
    'post-login-creator-none', 'ramsgate-register', 'ramsgate-status',
})
CATEGORIES = {
    'ported-inventory-migration-none': 'inventory_migration',
    'ported-migration-trigger': 'migration_trigger',
    'post-login-account-mapping': 'account_mapping',
    'ramsgate-register': 'player_registration',
    'ramsgate-join': 'city_join',
}


def _auth_alias(record: dict) -> str | None:
    auth = record.get('authentication')
    if not isinstance(auth, dict) or auth.get('input') != 'valid_local_session':
        return None
    alias = auth.get('session_alias')
    return alias if isinstance(alias, str) and HEX_ALIAS.fullmatch(alias) else None


def _is_loaded(record: dict) -> bool:
    payload = record.get('character_response')
    return (record.get('method') == 'GET' and record.get('route') == 'character'
            and record.get('status') == 200 and isinstance(payload, dict)
            and type(payload.get('character_count')) is int and payload['character_count'] > 0)


def _stage(records: list[dict]) -> dict:
    last_loaded = max((i for i, r in enumerate(records) if _is_loaded(r)), default=-1)
    created = sum(r.get('route') == 'character' and r.get('method') == 'PUT'
                  and r.get('status') == 200 and isinstance(r.get('character_response'), dict)
                  and r['character_response'].get('shape') == 'object[id:string,name:string]'
                  for r in records)
    empty = sum(r.get('route') == 'character' and r.get('method') == 'GET'
                and r.get('status') == 200 and isinstance(r.get('character_response'), dict)
                and r['character_response'].get('character_count') == 0 for r in records)
    loaded = sum(_is_loaded(r) for r in records)
    after = records[last_loaded + 1:] if last_loaded >= 0 else []
    post = [r for r in after if r.get('status') == 200 and
            (r.get('route') in POST_ROUTES or (r.get('route') == 'character' and r.get('method') == 'POST'))]
    city = [r for r in after if r.get('route') == 'ramsgate-join' and r.get('status') == 200]
    categories = sorted(set(CATEGORIES.get(r['route'], 'character_save' if
        r['route'] == 'character' and r['method'] == 'POST' else 'other_post_character')
        for r in post + city))
    failures = [r for r in after if type(r.get('status')) is int and r['status'] >= 400]
    failure = None
    if failures:
        f = failures[0]
        failure = {'status': f['status'], 'route_family': f['route'] if f.get('route') in (
            POST_ROUTES | frozenset({'character', 'ramsgate-join'})) else 'other'}
    return {
        'stage': 'city_join_request' if city else 'post_character_request' if post else
                 'character_loaded' if loaded else 'character_created' if created else
                 'character_empty' if empty else 'session_without_character',
        'character_get_empty_200_written': empty,
        'character_put_create_200_written': created,
        'character_get_populated_200_written': loaded,
        'post_character_200_written': len(post),
        'city_join_200_written': len(city),
        'post_character_categories': categories,
        'first_http_failure_after_loaded': failure,
    }


def summarize_sessions(written: list[dict]) -> dict:
    """Classify at most 16 within-process flows; no alias or ID leaves memory.

    Requires records already confirmed written_to_socket by the caller. An EOS
    exchange has no local-bearer alias and cannot be attributed to a session.
    Ordering is prepared-trace ordering; parallel requests may interleave.
    """
    if not isinstance(written, list) or len(written) > 4096:
        raise ValueError('Expected at most 4096 previously validated records')
    groups: dict[str, list[dict]] = {}
    unlinked_characters = 0
    over_limit = False
    for record in written:
        if not isinstance(record, dict):
            continue
        alias = _auth_alias(record)
        if alias is None:
            if record.get('route') == 'character':
                unlinked_characters += 1
            continue
        if alias not in groups and len(groups) >= MAX_SESSIONS:
            over_limit = True
            continue
        groups.setdefault(alias, []).append(record)
    return {
        'authenticated_session_count': len(groups),
        'session_results': [_stage(records) for records in groups.values()],
        'character_records_without_session_alias': unlinked_characters,
        'truncated_session_count': over_limit,
        'interpretation': 'Per-process HMAC session grouping; local socket writes only, not client parsing, verified Epic login or causation.',
    }
