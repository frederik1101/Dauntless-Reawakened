# SPDX-License-Identifier: AGPL-3.0-only
"""Allowlisted request labels: never raw URLs, identities, queries, headers or bodies.

This module describes requests; it never implements or changes their responses.
Unrecognised paths get a process-local keyed fingerprint, not a reversible path.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

# This set is only a logging allowlist. It does NOT add listeners, hosts entries,
# certificate names or application routes.
SAFE_SERVICES = frozenset({
    'local', 'status', 'auth-prod', 'gamesession-prod', 'login-queue-prod',
    'dauntless-prod', 'loadout-prod', 'progression-prod', 'mm2-prod',
    'presence-prod', 'cohort-prod', 'mailbox-prod', 'migration-prod',
    'store-prod', 'tracking-prod',
})

# Only whole templates are disclosed. Values occupying {slots} are always
# redacted, even when a username happens to equal a literal such as 'login'.
TEMPLATES = {
    'local': ('/health', '/__lab/session', '/__lab/notices', '/dauntless-status'),
    'status': ('/dauntless-status',),
    'login-queue-prod': ('/login', '/maintenance/status'),
    'gamesession-prod': (
        '/features/platform/{platform}', '/account/link/epic/{id}',
        '/account/link/epiceos/{id}', '/account/link/{provider}/{id}',
        '/gamesession/epic', '/gamesession/epiceos', '/gamesession/{provider}',
        '/account',
    ),
    'auth-prod': (
        '/accountinfo', '/tags', '/isbanned', '/game/login', '/entitlementsv2',
        '/accountinfo/public', '/account/mapping',
    ),
    'dauntless-prod': ('/character', '/inventory', '/inventory/{account}/{character}'),
    'loadout-prod': (
        '/loadout/{account}/{character}/all',
        '/loadout/{account}/{character}/slotcount', '/loadout/{account}/slotcount',
    ),
    'progression-prod': (
        '/progression/config', '/progression/objectives/{account}',
        '/progression/{account}', '/progression/{account}/{track}',
        '/pjm/{account}', '/cooldown/{account}', '/bounty/{account}',
        '/escalation/{season}/{account}', '/game_tuning/{blob}',
    ),
    'mm2-prod': (
        '/candidate/regions', '/candidate/player/register', '/candidate/join',
        '/candidate/join/{candidate}', '/candidate/status', '/candidate/leave',
        '/candidate', '/candidate/player/ready', '/candidate/player/{player}/loadout',
        '/candidate/players/loadout',
    ),
    'presence-prod': ('/ws/{account}',),
    'cohort-prod': ('/playertreatments/{account}',),
    'mailbox-prod': ('/eventstats', '/all', '/survey/config'),
    'migration-prod': ('/migration/status', '/migration/trigger'),
    'store-prod': ('/reconcile', '/creator'),
    'tracking-prod': ('/heartbeat',),
}


def _compile(template: str) -> re.Pattern:
    parts = template.split('/')[1:]
    pattern = '/' + '/'.join('[^/]+' if p.startswith('{') else re.escape(p) for p in parts)
    return re.compile(pattern)


_RULES = {service: tuple((_compile(t), t) for t in templates)
          for service, templates in TEMPLATES.items()}
_PROCESS_KEY = secrets.token_bytes(32)  # Never saved, printed or reused between processes.


@dataclass(frozen=True)
class RequestLabel:
    service: str
    endpoint: str
    route_key: str = '-'


def describe_request(service: str, endpoint: str, method: str | None = None) -> RequestLabel:
    """Accept an already-routed path, but defensively strip queries/fragments too.

    No unrecognised segment is ever returned. Malformed and excessive input gets
    fixed labels. Trailing slash is reported, not silently normalised for routing.
    """
    if service not in SAFE_SERVICES:
        return RequestLabel('unrecognised', '<redacted>')
    if not isinstance(endpoint, str) or len(endpoint) > 8192:
        return RequestLabel(service, '<invalid>')
    if any(ord(c) < 32 or ord(c) == 127 for c in endpoint):
        return RequestLabel(service, '<invalid>')
    path = endpoint.split('?', 1)[0].split('#', 1)[0]
    if not path.startswith('/') or path.startswith('//') or '\\' in path:
        return RequestLabel(service, '<invalid>')
    trailing = path.endswith('/') and path != '/'
    candidate = path[:-1] if trailing else path
    # POST's slots have DIFFERENT meanings from GET, according to inventory.ts.
    # This is classification only: malformed/unsupported payloads still fail.
    if service == 'dauntless-prod' and re.fullmatch(r'/inventory/[^/]*/[^/]+', candidate):
        if method == 'POST':
            template = '/inventory/{character}/{build}'
        elif method == 'GET':
            template = '/inventory/{account}/{character}'
        else:
            template = '/inventory/{first}/{second}'
        return RequestLabel(service, template + ('/' if trailing else ''))
    for pattern, template in _RULES.get(service, ()):
        if pattern.fullmatch(candidate):
            return RequestLabel(service, template + ('/' if trailing else ''))
    # The HMAC groups repeated unknown paths only within this process. It does
    # not retain the raw path or permit comparison across separate probe runs.
    key = hmac.new(_PROCESS_KEY, (service + '\0' + path).encode('utf-8', errors='replace'),
                   hashlib.sha256).hexdigest()[:16]
    return RequestLabel(service, '<redacted>', key)
