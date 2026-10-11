# SPDX-License-Identifier: AGPL-3.0-only
# Original work Copyright (C) 2026 gwog :3 (SyST3MDeV/Undaunted)
# Modified work Copyright (C) 2026 MysticFox / Pranav Karande
# Python adaptation for Dauntless Reawakened, 10 October 2026.
# Additional terms apply to upstream material: see ADDITIONAL_TERMS.md and NOTICE.md.
"""Opt-in port of Mystic Paradox login.ts, not a verified Dauntless 2.1.1 login.

Pinned source and a route-by-route change list: docs/MYSTIC_LOGIN_PORT.md.
Default Application remains unchanged. This subclass deliberately exposes only
single-player identity, tags, ban-state and empty-new-account migration responses.
It DOES NOT port the token-echo shortcut, launcher auth, SDK or UE4 runtime hooks.
"""
from __future__ import annotations

import copy
import json

from .application import Application, Response, bearer, target
from .contract import linked_account
from .login_routes import is_eos_account_link
from .inventory_migration import (
    parse_migration_path, is_empty_migration_body, no_migration_response,
    SOURCE_URL as INVENTORY_SOURCE_URL,
)

SOURCE_URL = ('https://github.com/pranav158/Mystic-Paradox/blob/'
              'fd795c6434abd63872f4af277c90747239f1ed40/ParadoxBackend/src/routes/login.ts')
ATTRIBUTION = ("Mystic Paradox's Dauntless 1.12.0 port and related modifications were "
               "developed by Pranav Karande. See NOTICE.md for contribution "
               "and provenance information.")
PORT_ROUTES = {
    ('GET', 'auth-prod', '/tags'): 'ported-tags',
    ('GET', 'auth-prod', '/isbanned'): 'ported-ban-check',
    ('POST', 'auth-prod', '/accountinfo/public'): 'ported-public-account',
    ('GET', 'migration-prod', '/migration/status'): 'ported-migration-status',
    ('POST', 'migration-prod', '/migration/trigger'): 'ported-migration-trigger',
}


class LoginPortApplication(Application):
    """LOCAL experiment: cross-version handlers require TLS and local session tokens.

    maintenance_response is an explicit experiment, not an upstream-derived shape.
    None preserves the baseline's bodyless 404, rather than guessing silently.
    """
    def __init__(self, database, *, maintenance_response: dict | None = None, **kwargs):
        super().__init__(database, **kwargs)
        if maintenance_response is not None:
            if not isinstance(maintenance_response, dict):
                raise ValueError('Maintenance experiment must be a JSON object')
            encoded = json.dumps(maintenance_response, allow_nan=False).encode()
            if len(encoded) > 16384:
                raise ValueError('Maintenance experiment is too large')
        self.maintenance_response = copy.deepcopy(maintenance_response)

    def handle(self, method, host, path, headers, body=b'', *, secure=False):
        lower = {key.lower(): value for key, value in headers.items()}
        if 'origin' in lower:
            return Response(403, route='origin-rejected')
        try:
            service, endpoint = target(host, path)
        except ValueError:
            return Response(400, route='invalid-host-or-target')
        if (method, service, endpoint) == ('GET', 'local', '/health'):
            result = super().handle(method, host, path, headers, body, secure=secure)
            payload = {**result.payload, 'experimental_login_port': True,
                       'maintenance_candidate_enabled': self.maintenance_response is not None,
                       'source_url': SOURCE_URL,
                       'inventory_migration_port_enabled': True,
                       'inventory_migration_source': INVENTORY_SOURCE_URL}
            # Never promotes prototype health to verified game compatibility.
            return Response(result.status, payload, result.route)
        if (method, service, endpoint) == ('GET', 'local', '/__lab/notices'):
            return Response(200, {'license': 'AGPL-3.0-only', 'attribution': ATTRIBUTION,
                                  'source': 'https://github.com/frederik1101/Dauntless-Reawakened',
                                  'upstream': SOURCE_URL, 'warranty': 'NO WARRANTY'}, 'notices')
        if (method, service, endpoint) == ('GET', 'login-queue-prod', '/maintenance/status'):
            if not secure:
                return Response(503, route='experimental-maintenance')
            if self.maintenance_response is not None:
                return Response(200, copy.deepcopy(self.maintenance_response), 'experimental-maintenance')
        # Candidate compatibility alias. The old log does not identify its 404:
        # this must remain a hypothesis until a real client requests this route.
        # The existing epic route and all session/ownership checks are unchanged.
        if (method == 'GET' and service == 'gamesession-prod'
                and is_eos_account_link(endpoint)):
            if not secure:
                return Response(503, route='candidate-account-link-epiceos')
            return Response(200, linked_account(), 'candidate-account-link-epiceos')
        if method == 'POST' and service == 'dauntless-prod':
            migration = parse_migration_path(endpoint)
            if migration is not None:
                return self._inventory_migration(migration, lower, body, secure)
        label = PORT_ROUTES.get((method, service, endpoint))
        if label is None:
            return super().handle(method, host, path, headers, body, secure=secure)
        if not secure:
            return Response(503, route=label)
        try:
            session = self.sessions.resolve(bearer(lower))
            if session is None:
                raise PermissionError()
            account = session.account_id
            if label == 'ported-tags':
                # login.ts: accountId from authenticated identity, empty tag list.
                payload = {'accountId': account, 'tags': []}
            elif label == 'ported-ban-check':
                # Local account state only, not a claim about Epic's ban records.
                payload = {'isBanned': False}
            elif label == 'ported-public-account':
                data = self._json(body)
                requested = data['accountId']
                if not isinstance(requested, str) or requested != account:
                    raise PermissionError()
                # Preserve the requested identity, never return self for another user.
                # Single-player restriction replaces upstream's cross-account lookup.
                payload = {'accountId': requested, 'isSubscribed': True, 'language': None,
                           'linkedAccounts': [{'accountId': requested, 'accountType': 'epic'}],
                           'username': 'LocalSlayer'}
            else:
                # New local account: no external data is imported or migrated.
                # Deliberate 2.1.1 correction: flat, NOT upstream GET's wrapper.
                payload = {'migration_failed': False, 'migration_finished': True}
            return Response(200, payload, label)
        except PermissionError:
            return Response(401, route=label)
        except (KeyError, ValueError, TypeError, RecursionError):
            return Response(400, route=label)

    def _inventory_migration(self, request, headers, body, secure):
        """Cross-version gate for this fresh local profile, NOT an item write.

        Source: Mystic Paradox inventory.ts (pinned in inventory_migration.py).
        No external inventory exists in this research database to upgrade.
        No data is created, changed, granted or deleted by this endpoint.
        """
        label = 'ported-inventory-migration-none'
        if not secure:
            return Response(503, route=label)
        try:
            session = self.sessions.resolve(bearer(headers))
            if session is None:
                raise PermissionError()
            if request.character_id:
                if not self.database.owns_character(session.account_id, request.character_id):
                    return Response(404, route='inventory-migration-character-not-owned')
            elif len(self.database.get(session.account_id)) > 1:
                # The upstream permits an empty character slot. Do not silently
                # choose one when more than one local character could be intended.
                return Response(409, route='inventory-migration-character-ambiguous')
            if not is_empty_migration_body(body):
                # We have not observed the user's body. Preserve unknown payloads
                # as an explicit error instead of claiming a mutation succeeded.
                return Response(422, route='inventory-migration-body-unsupported')
            return Response(200, no_migration_response(), label)
        except PermissionError:
            return Response(401, route=label)
