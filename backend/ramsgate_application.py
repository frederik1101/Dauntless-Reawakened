# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in CITY routing for the native-host workstream; not a ready game server.

Uses the unwrapped candidate experiment described in RAMSGATE_MATCHMAKING.md.
The existing LoginPortApplication/probe stays unchanged. The default provider has
no host and cannot give a client a destination. No ticket/key or ready shortcuts.
"""
from .application import Response, bearer, target
from .mystic_login_port import LoginPortApplication
from .ramsgate_matchmaker import PlayerBinding, RamsgateMatchmaker


class RamsgateApplication(LoginPortApplication):
    def __init__(self, database, *, matchmaker=None, **kwargs):
        super().__init__(database, **kwargs)
        self.matchmaker = matchmaker if matchmaker is not None else RamsgateMatchmaker()

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
            return Response(old.status, {**old.payload, 'ramsgate_matchmaking_experiment': True,
                                         'game_compatible': False,
                                         'native_host_started_by_this_application': False}, old.route)
        routes = {
            ('POST', '/candidate/player/register'): 'ramsgate-register',
            ('POST', '/candidate/join'): 'ramsgate-join',
            ('GET', '/candidate/status'): 'ramsgate-status',
            ('DELETE', '/candidate'): 'ramsgate-cancel',
            ('DELETE', '/candidate/leave'): 'ramsgate-cancel',
        }
        label = routes.get((method, endpoint)) if service == 'mm2-prod' else None
        if label is None:
            return super().handle(method, host, path, headers, body, secure=secure)
        if not secure:
            return Response(503, route=label)
        try:
            session = self.sessions.resolve(bearer(lower))
            if session is None:
                raise PermissionError()
            characters = self.database.get(session.account_id)
            # No guessed first character, no data creation as a side effect of
            # matchmaking. The initial solo target has exactly one owned profile.
            if len(characters) != 1:
                return Response(409, route='ramsgate-character-selection-required')
            character = characters[0]['id']
            if not self.database.owns_character(session.account_id, character):
                raise PermissionError()
            player = PlayerBinding(session.account_id, session.session_id, character)
            if label == 'ramsgate-register':
                data = {} if not body else self._json(body)
                if data.get('playerId', player.account_id) != player.account_id:
                    raise PermissionError()
                return Response(200, {}, label)
            if label == 'ramsgate-join':
                result = self.matchmaker.join(player, self._json(body))
            elif label == 'ramsgate-status':
                result = self.matchmaker.status(player)
            else:
                self.matchmaker.cancel(player)
                return Response(204, route=label)
            return Response(200, result, label)
        except PermissionError:
            return Response(401, route=label)
        except NotImplementedError:
            return Response(422, route='ramsgate-request-unsupported')
        except KeyError:
            return Response(404, route=label)
        except OverflowError:
            return Response(503, route=label)
        except (ValueError, TypeError, RecursionError):
            return Response(400, route=label)
