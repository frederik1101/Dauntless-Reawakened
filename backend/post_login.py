# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in post-login compatibility handlers, not an Epic verifier or game host."""
from __future__ import annotations

from .application import Response, bearer, target
from .protocol_211 import game_session_response
from .research_identity import parse_research_identity
from .database import VersionConflict
from .ramsgate_application import RamsgateApplication
from .post_login_contracts import (
    REVISION, TUNING_LABELS, UnsupportedRequest, mapping_response,
    public_account_response, reconcile_request, reconcile_response,
    tuning_response, creator_response,
)


class PostLoginApplication(RamsgateApplication):
    def _session(self, subject: str, route: str) -> Response:
        account = self.database.account(subject)
        # Only the already-parsed EOS research exchange can supply this binding.
        # It remains UNVERIFIED; never import Epic credentials or echo their token.
        prefix = 'eos-research:'
        epic = subject[len(prefix):] if subject.startswith(prefix) else None
        session = self.sessions.create(account['accountId'], linked_epic_id=epic)
        return Response(200, game_session_response(session.session_id, session.session_token), route)

    def _research_exchange(self, lower, *, secure: bool) -> Response:
        route = 'epiceos-session-research'
        if not self.allow_unverified_eos_sub or not secure:
            return Response(503, route=route)
        try:
            identity = parse_research_identity(bearer(lower))
            # Preserve the exact old lookup key. Never re-key or merge a player
            # database using the external ID, an account-link URL or mapping body.
            account = self.database.account('eos-research:' + identity.subject)
            session = self.sessions.create(account['accountId'],
                linked_epic_id=identity.epic_id, research_identity=identity)
            payload = game_session_response(session.session_id, session.session_token)
            # Mystic login.ts compatibility fields. These are OUR local session
            # values, not an echo of the real Epic token or a fabricated Epic JWT.
            payload['payload']['error_code'] = None
            payload['payload']['sessionToken'] = session.session_token
            return Response(200, payload, route)
        except PermissionError:
            return Response(401, route=route)
        except (ValueError, TypeError, RecursionError):
            return Response(400, route=route)
        except OverflowError:
            return Response(503, route=route)

    def handle(self, method, host, path, headers, body=b'', *, secure=False):
        lower = {key.lower(): value for key, value in headers.items()}
        if 'origin' in lower:
            return Response(403, route='origin-rejected')
        try:
            service, endpoint = target(host, path)
        except (ValueError, TypeError):
            return Response(400, route='invalid-host-or-target')
        if (method, service, endpoint) == ('GET', 'local', '/health'):
            old = super().handle(method, host, path, headers, body, secure=secure)
            return Response(old.status, {**old.payload, 'post_login_revision': REVISION,
                'post_login_compatibility': True, 'post_login_client_verified': False,
                'game_compatible': False,
                'character_profile_experiment': getattr(self.database, 'profile_summary', None)}, old.route)
        if (method, service, endpoint) == (
                'PUT', 'gamesession-prod', '/gamesession/epiceos'):
            return self._research_exchange(lower, secure=secure)
        routes = {
            ('POST', 'dauntless-prod', '/character'): 'character',
            ('POST', 'auth-prod', '/account/mapping'): 'post-login-account-mapping',
            ('POST', 'auth-prod', '/accountinfo/public'): 'post-login-public-account',
            ('POST', 'store-prod', '/reconcile'): 'post-login-store-reconcile',
            ('GET', 'store-prod', '/balance'): 'post-login-store-balance',
            ('GET', 'store-prod', '/creator'): 'post-login-creator-none',
        }
        label = routes.get((method, service, endpoint))
        blob = None
        if method == 'GET' and service == 'progression-prod' and endpoint.startswith('/game_tuning/'):
            blob = endpoint[len('/game_tuning/'):]
            label = TUNING_LABELS.get(blob, 'post-login-tuning-unimplemented')
        if label is None:
            return super().handle(method, host, path, headers, body, secure=secure)
        if not secure:
            return Response(503, route=label)
        try:
            session = self.sessions.resolve(bearer(lower))
            if session is None:
                raise PermissionError()
            if label == 'character':
                data = self._json(body)
                payload = self.database.save(session.account_id, data['characterId'],
                    data['data'], data['updateVersion'], allow_identical_retry=True)
            elif blob is not None:
                if label == 'post-login-tuning-unimplemented':
                    return Response(404, route=label)
                payload = tuning_response(blob)
            elif label == 'post-login-account-mapping':
                payload = mapping_response(body, session.account_id, session.linked_epic_id)
            elif label == 'post-login-public-account':
                payload = public_account_response(body, session.account_id, session.linked_epic_id)
            elif label in ('post-login-store-reconcile', 'post-login-store-balance'):
                if method == 'POST':
                    reconcile_request(body)
                payload = reconcile_response(self.database.local_balances(session.account_id))
                if method == 'GET':
                    payload = payload['balances']
            else:
                payload = creator_response()
            return Response(200, payload, label)
        except PermissionError:
            return Response(401, route=label)
        except VersionConflict:
            return Response(409, route=label)
        except KeyError:
            return Response(400, route=label)
        except UnsupportedRequest:
            return Response(422, route=label)
        except (ValueError, TypeError, RecursionError):
            return Response(400, route=label)
