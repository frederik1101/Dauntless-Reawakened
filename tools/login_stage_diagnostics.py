# SPDX-License-Identifier: AGPL-3.0-only
"""Offline, privacy-safe diagnosis of SANITIZED 2.1.1 HTTP traces.

Local socket writes are not proof of client parsing, authentication or gameplay.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from .login_session_stages import summarize_sessions

LIMIT = 2 * 1024 * 1024
STAGES = ('no_exchange', 'local_exchange', 'character_empty', 'character_created',
          'character_loaded', 'post_character_request', 'city_join_request')
POST = frozenset({
    'ported-inventory-migration-none', 'ported-migration-trigger',
    'inventory-bootstrap', 'loadouts-bootstrap', 'loadout-slots',
    'progression-config-bootstrap', 'progression-objectives-bootstrap',
    'progression-tracks-bootstrap', 'cooldowns-bootstrap', 'bounties-bootstrap',
    'escalation-bootstrap', 'post-login-tuning-seasonal-events',
    'post-login-tuning-huntpass-xp', 'post-login-tuning-island-content',
    'post-login-store-reconcile', 'post-login-store-balance',
    'post-login-account-mapping', 'post-login-public-account',
    'post-login-creator-none', 'ramsgate-register', 'ramsgate-status'})
VARIANTS = frozenset({'baseline', 'full', 'without-appearance', 'without-flags',
    'without-metadata', 'appearance-only', 'flags-only', 'metadata-only'})
PROGRESS = frozenset({'New', 'SavedCharacter', 'TrainingGroundsComplete',
    'DefeatedGnasher', 'EnteredRamsgate', 'FinishedFirstHunt', 'FinishedSecondHunt'})
END = re.compile(r'\brequest_id=([a-f0-9]{16}) delivery=(written_to_socket|socket_write_failed)\b')


def summarize(text: str) -> dict:
    if not isinstance(text, str) or len(text.encode('utf-8')) > LIMIT:
        raise ValueError('Expected sanitized UTF-8 diagnostic under 2 MiB')
    requests, delivery = [], {}
    truncated = False
    for line in text.splitlines():
        if len(requests) >= 4096:
            truncated = True
            break
        if ' PROTOCOL_TRACE ' in line and len(line) <= 32768:
            try:
                rec = json.loads(line.split(' PROTOCOL_TRACE ', 1)[1])
                if not isinstance(rec, dict) or rec.get('phase') != 'prepared':
                    continue
                if not re.fullmatch('[0-9a-f]{16}', rec.get('request_id', '')):
                    continue
                if rec.get('method') not in {'GET', 'PUT', 'POST', 'DELETE'}:
                    continue
                if type(rec.get('status')) is not int or not 100 <= rec['status'] <= 599:
                    continue
                if not isinstance(rec.get('route'), str) or len(rec['route']) > 100:
                    continue
                requests.append(rec)
            except (ValueError, TypeError, RecursionError):
                continue
        elif ' PROTOCOL_TRACE_END ' in line:
            match = END.search(line)
            if match:
                delivery[match[1]] = match[2]
    written = [r for r in requests if delivery.get(r['request_id']) == 'written_to_socket']
    ok = [r for r in written if r['status'] == 200]
    exchange = [r for r in ok if r['route'] == 'epiceos-session-research']
    character = [r for r in ok if r['route'] == 'character']
    reads = [r for r in character if r['method'] == 'GET'
             and isinstance(r.get('character_response'), dict)]
    empty = [r for r in reads if r['character_response'].get('character_count') == 0]
    created = [r for r in character if r['method'] == 'PUT'
               and isinstance(r.get('character_response'), dict) and
               r['character_response'].get('shape') == 'object[id:string,name:string]']
    loaded = [r for r in reads if type(r['character_response'].get('character_count')) is int
              and r['character_response']['character_count'] > 0]
    last = max((i for i, r in enumerate(ok) if r in loaded), default=-1)
    post = [r for i, r in enumerate(ok) if last >= 0 and i > last and (r['route'] in POST or
               (r['route'] == 'character' and r['method'] == 'POST'))]
    city = [r for i, r in enumerate(ok) if last >= 0 and i > last and r['route'] == 'ramsgate-join']
    stage = ('city_join_request' if city else 'post_character_request' if post else
             'character_loaded' if loaded else 'character_created' if created else
             'character_empty' if empty else 'local_exchange' if exchange else 'no_exchange')
    field_counts, appearance, progress = [], [], []
    for record in loaded:
        for row in record['character_response'].get('characters', [])[:8]:
            data = row.get('data') if isinstance(row, dict) else None
            if not isinstance(data, dict):
                continue
            n = data.get('field_count')
            if type(n) is int and 0 <= n <= 256:
                field_counts.append(n)
            fields = data.get('known_field_types')
            if isinstance(fields, dict):
                appearance.append('AppearanceData' in fields)
            if data.get('progress_state') in PROGRESS:
                progress.append(data['progress_state'])
    audit, variants = [], []
    for r in exchange:
        a = r.get('local_account_at_exchange')
        if isinstance(a, dict) and type(a.get('preexisting')) is bool:
            n = a.get('owned_characters')
            if type(n) is int and 0 <= n <= 100000:
                audit.append({'preexisting': a['preexisting'], 'owned_characters': n})
        profile = r.get('profile_selection')
        if isinstance(profile, dict) and profile.get('variant') in VARIANTS:
            variants.append(profile['variant'])
    return {
        'stage': stage, 'exchange_200_written': len(exchange),
        'character_get_empty_200_written': len(empty),
        'character_put_create_200_written': len(created),
        'character_get_populated_200_written': len(loaded),
        'post_character_200_written': len(post), 'city_join_200_written': len(city),
        'observed_field_counts': sorted(set(field_counts)),
        'appearance_field_observed': any(appearance) if appearance else None,
        'observed_progress_states': sorted(set(progress)),
        'account_at_exchange': audit[:8], 'explicit_profile_variants': sorted(set(variants)),
        'prepared_without_socket_write_confirmation': sum(
            r['request_id'] not in delivery for r in requests),
        'socket_write_failures': sum(delivery.get(r['request_id']) == 'socket_write_failed'
                                     for r in requests),
        'unimplemented_404_written': sum(r['status'] == 404 and r['route'] == 'unknown'
                                         for r in written),
        'truncated_at_record_limit': truncated,
        'session_flows': summarize_sessions(written),
        'interpretation': 'Server-side socket writes only; no verified Epic login, client parsing, or gameplay.',
    }


def compare(previous: dict, latest: dict) -> dict:
    return {'previous_stage': previous['stage'], 'newer_stage': latest['stage'],
            'stage_regressed': STAGES.index(latest['stage']) < STAGES.index(previous['stage']),
            'field_counts_differ': previous['observed_field_counts'] != latest['observed_field_counts'],
            'previous_post_character_calls': previous['post_character_200_written'],
            'newer_post_character_calls': latest['post_character_200_written'],
            'interpretation': 'Observed server difference, not causal evidence or game acceptance.'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Data-free offline comparison of sanitized 2.1.1 server logs')
    parser.add_argument('latest', type=Path)
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    def read(path):
        if path.stat().st_size > LIMIT:
            raise ValueError('Log exceeds 2 MiB limit')
        return summarize(path.read_text(encoding='utf-8'))
    latest = read(args.latest)
    output = {'latest': latest}
    if args.previous:
        output['comparison'] = compare(read(args.previous), latest)
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
