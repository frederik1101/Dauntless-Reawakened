"""Known 2.1.1 HTTP contracts, not a game server or an Epic authentication service.

Protocol evidence: docs/CONNECTION_BASELINE.md. Unknown responses are never invented.
"""
from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from .contract import linked_account, login_queue
from .database import Database, VersionConflict
from .protocol_211 import account_info, character_seed, features, game_session_response
from .session_store import SessionStore, unverified_subject
from .player_data import match_read, initial_loadouts, initial_progression, slot_counts, wrapped

SERVICES = frozenset({
    'auth-prod', 'gamesession-prod', 'login-queue-prod', 'dauntless-prod',
    'loadout-prod', 'progression-prod', 'mm2-prod', 'presence-prod', 'cohort-prod',
    'mailbox-prod', 'migration-prod', 'store-prod', 'tracking-prod',
})
LOCAL_HOSTS = frozenset({'127.0.0.1', '::1', 'localhost'})
BLOCKERS = [
    'maintenance/status, auth/tags and auth/isbanned response schemas unverified',
    'only initial player-data reads implemented; inventory transactions, loadout saves and gameplay progression absent',
    'matchmaking, presence and dedicated UE5 game server not implemented',
    'no end-to-end test with a Dauntless client',
]


@dataclass(frozen=True)
class Response:
    status: int
    payload: object = None
    route: str = 'unknown'

    def body(self) -> bytes:
        return b'' if self.payload is None else json.dumps(
            self.payload, ensure_ascii=False, allow_nan=False).encode('utf-8')


def bearer(headers: Mapping[str, str]) -> str:
    value = headers.get('authorization', '')
    pieces = value.split()
    if len(pieces) != 2 or pieces[0].lower() != 'bearer' or len(pieces[1]) > 16384:
        raise PermissionError('Missing or invalid local session')
    return pieces[1]


def target(host: str, path: str) -> tuple[str, str]:
    """Use real Host routing; preserve prefixed localhost URLs for contract tests."""
    if not host or any(c in host for c in '/\\@?#'):
        raise ValueError('Invalid host')
    parsed = urlsplit('//' + host)
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid port')
    name = parsed.hostname or ''
    url = urlsplit(path)
    if url.scheme or url.netloc or not url.path.startswith('/'):
        raise ValueError('Only origin-form requests are accepted')
    route = url.path
    if name in LOCAL_HOSTS:
        pieces = route.split('/', 2)
        if len(pieces) == 3 and pieces[1] in SERVICES:
            return pieces[1], '/' + pieces[2]
        return 'local', route
    if name == 'steelyard.online':
        return 'status', route
    suffix = '.steelyard.ca'
    if name.endswith(suffix) and name[:-len(suffix)] in SERVICES:
        return name[:-len(suffix)], route
    raise ValueError('Host not allowed')


class Application:
    def __init__(self, database: Database, *, allow_unverified_eos_sub: bool = False,
                 lab_key: str | None = None, sessions: SessionStore | None = None):
        self.database = database
        self.sessions = sessions or SessionStore()
        self.allow_unverified_eos_sub = allow_unverified_eos_sub
        self.lab_key = lab_key or secrets.token_urlsafe(32)

    def handle(self, method: str, host: str, path: str, headers: Mapping[str, str],
               body: bytes = b'', *, secure: bool = False) -> Response:
        headers = {k.lower(): v for k, v in headers.items()}
        # No browser access or CORS, including requests from file:// pages.
        if 'origin' in headers:
            return Response(403, route='origin-rejected')
        try:
            service, endpoint = target(host, path)
        except ValueError:
            return Response(400, route='invalid-host-or-target')
        route = 'unknown'
        try:
            if service == 'local' and endpoint == '/health' and method == 'GET':
                return Response(200, {'status': 'ok', 'game_compatible': False,
                                      'stage': 'transport-contract-prototype',
                                      'unverified_eos_identity_enabled': self.allow_unverified_eos_sub,
                                      'blockers': BLOCKERS}, 'health')
            if service == 'local' and endpoint == '/__lab/session' and method == 'POST':
                route = 'lab-session'
                if not secrets.compare_digest(headers.get('x-reawakened-lab-key', ''), self.lab_key):
                    raise PermissionError()
                data = self._json(body)
                subject = data.get('subject', 'offline-demo')
                if not isinstance(subject, str) or not 1 <= len(subject) <= 256:
                    raise ValueError()
                return self._session('lab:' + subject, route)
            if service == 'local' and endpoint == '/__lab/session' and method == 'DELETE':
                route = 'lab-session-revoke'
                token = bearer(headers)
                if not self.sessions.revoke(token):
                    raise PermissionError()
                return Response(204, route=route)
            if service == 'login-queue-prod' and endpoint == '/login' and method == 'POST':
                return Response(200, login_queue(), 'login-queue')
            if service == 'gamesession-prod' and endpoint == '/features/platform/win' and method == 'GET':
                return Response(200, features(), 'platform-features')
            if (service == 'gamesession-prod' and method == 'GET' and
                    re.fullmatch(r'/account/link/epic/[^/]{1,256}', endpoint)):
                return Response(200, linked_account(), 'account-link')
            if service == 'gamesession-prod' and endpoint == '/gamesession/epiceos' and method == 'PUT':
                route = 'epiceos-session-research'
                if not self.allow_unverified_eos_sub or not secure:
                    return Response(503, route=route)
                subject = unverified_subject(bearer(headers))
                return self._session('eos-research:' + subject, route)
            if service in {'status', 'local'} and endpoint == '/dauntless-status' and method == 'GET':
                payload = {language: '' for language in ('en', 'fr', 'it', 'es', 'de', 'pt', 'ru', 'ja')}
                return Response(200, {'show-status': False, **payload}, 'status-banner')

            # Authentication and ownership apply to all initial player-data reads.
            data_route = match_read(service, endpoint) if method == 'GET' else None
            if data_route:
                route = data_route.label
                session = self.sessions.resolve(bearer(headers))
                if session is None or (data_route.account and data_route.account != session.account_id):
                    raise PermissionError()
                if data_route.character and not self.database.owns_character(session.account_id, data_route.character):
                    return Response(404, route=route)
                if route == 'inventory-bootstrap':
                    payload = self.database.bootstrap_inventory(session.account_id, data_route.character)
                elif route == 'loadouts-bootstrap':
                    payload = initial_loadouts()
                elif route == 'loadout-slots':
                    payload = wrapped(slot_counts())
                else:
                    payload = initial_progression(route)
                return Response(200, payload, route)
            if service == 'dauntless-prod' and endpoint == '/inventory' and method == 'POST':
                # Never echo a transaction or claim items were granted before a real
                # atomic transaction/retry/cost-validation implementation exists.
                return Response(503, route='unimplemented-inventory-transaction')

            known = ((service == 'auth-prod' and endpoint in {'/accountinfo', '/entitlementsv2'} and method == 'GET')
                     or (service == 'dauntless-prod' and endpoint == '/character' and method in {'GET', 'PUT', 'POST'})
                     or (service == 'cohort-prod' and method == 'GET'
                         and re.fullmatch(r'/playertreatments/[^/]*', endpoint)))
            if not known:
                # Leave these failures visible rather than fabricating successful login/gameplay.
                labels = {('login-queue-prod', '/maintenance/status'): 'unimplemented-maintenance',
                          ('auth-prod', '/tags'): 'unimplemented-tags',
                          ('auth-prod', '/isbanned'): 'unimplemented-ban-check',
                          ('dauntless-prod', '/inventory'): 'unimplemented-inventory'}
                return Response(404, route=labels.get((service, endpoint), 'unknown'))
            route = {'auth-prod': endpoint.lstrip('/'), 'dauntless-prod': 'character',
                     'cohort-prod': 'cohort-treatments'}[service]
            session = self.sessions.resolve(bearer(headers))
            if session is None:
                raise PermissionError()
            account = session.account_id
            if service == 'auth-prod':
                payload = account_info(account, 'LocalSlayer') if endpoint == '/accountinfo' else {'entitlements': []}
                return Response(200, payload, route)
            if service == 'cohort-prod':
                account_in_path = endpoint.rsplit('/', 1)[-1]
                if account_in_path and account_in_path != account:
                    raise PermissionError()
                return Response(200, {'code': 'OK', 'message': '', 'payload': {'treatments': []}}, route)
            if method == 'GET':
                return Response(200, self.database.get(account), route)
            data = self._json(body)
            if method == 'PUT':
                return Response(200, self.database.create(account, data['name'], character_seed()), route)
            # 2.1.1 sends characterId, NOT the old prototype's id field.
            saved = self.database.save(account, data['characterId'], data['data'], data['updateVersion'])
            return Response(200, saved, route)
        except PermissionError:
            return Response(401, route=route)
        except VersionConflict:
            return Response(409, route=route)
        except KeyError:
            return Response(400, route=route)
        except (ValueError, TypeError, RecursionError):
            return Response(400, route=route)
        except OverflowError:
            return Response(503, route=route)

    def _session(self, subject: str, route: str) -> Response:
        account = self.database.account(subject)
        session = self.sessions.create(account['accountId'])
        return Response(200, game_session_response(session.session_id, session.session_token), route)

    @staticmethod
    def _json(body: bytes) -> dict:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate JSON key')
                result[key] = value
            return result
        def reject_constant(_):
            raise ValueError('Non-finite JSON number')
        data = json.loads(body, object_pairs_hook=unique, parse_constant=reject_constant)
        if not isinstance(data, dict):
            raise ValueError('Expected JSON object')
        return data
