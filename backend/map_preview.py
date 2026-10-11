# SPDX-License-Identifier: AGPL-3.0-only
"""Observe allowlisted map names without changing any backend response."""
import logging
import threading
from tools.map_preview_support import heartbeat_map


class MapObservations:
    def __init__(self):
        self._lock = threading.Lock()
        self._counts = dict.fromkeys(('ramsgate', 'login_menu', 'unknown', 'invalid'), 0)
        self._last = None
        self._changes = 0
        self._stages = {name: {'success': 0, 'unauthorized': 0, 'other': 0} for name in
                        ('account_link', 'login_queue', 'local_session', 'character', 'entitlements', 'city_join')}

    def observe(self, body):
        label = heartbeat_map(body)
        with self._lock:
            self._counts[label] = min(self._counts[label] + 1, 100000)
            if label != self._last and self._changes < 16:
                self._changes += 1
                self._last = label
                logging.getLogger('reawakened.requests').info('MAP_SELF_REPORT label=%s', label)

    def stage(self, name, status):
        if name not in self._stages:
            return
        category = 'success' if status == 200 else ('unauthorized' if status == 401 else 'other')
        with self._lock:
            counts = self._stages[name]
            counts[category] = min(counts[category] + 1, 100000)

    def report(self):
        with self._lock:
            stages = {k: dict(v) for k, v in self._stages.items()}
            # A conservative report: success means only that an HTTP response was sent,
            # not that the client accepted it or that Epic authenticated the player.
            order = ('account_link', 'login_queue', 'local_session', 'character',
                     'entitlements', 'city_join')
            reached = [name for name in order if stages[name]['success']]
            rejected = [name for name in order if stages[name]['unauthorized']]
            if not reached:
                outcome = 'no_successful_login_stage_observed'
            elif not stages['local_session']['success']:
                outcome = 'pre_session_responses_only'
            elif not stages['character']['success']:
                outcome = 'local_session_response_only'
            elif not stages['city_join']['success']:
                outcome = 'character_response_no_city_join'
            else:
                outcome = 'city_join_http_response_no_host_proof'
            return {'map_report_counts': dict(self._counts),
                    'ramsgate_self_report_seen': self._counts['ramsgate'] > 0,
                    'backend_stage_counts': stages,
                    'backend_observation': outcome,
                    'unauthorized_stage_labels': rejected,
                    'renderer_verified': False, 'game_server_started': False,
                    'client_join_verified': False, 'controllable_player_verified': False}


def make_application(database, observations):
    from .application import target
    from .ramsgate_application import RamsgateApplication
    class MapPreviewApplication(RamsgateApplication):
        def handle(self, method, host, path, headers, body=b'', *, secure=False):
            # Observe only HTTPS heartbeat requests without a browser Origin.
            # This is client self-reporting, not authenticated proof of world load.
            if secure and method == 'POST' and not any(k.lower() == 'origin' for k in headers):
                try:
                    service, endpoint = target(host, path)
                except (ValueError, TypeError):
                    service, endpoint = '', ''
                if (service, endpoint) == ('tracking-prod', '/heartbeat'):
                    observations.observe(body)
            response = super().handle(method, host, path, headers, body, secure=secure)
            # Record fixed route labels only. Never retain raw paths, headers or tokens.
            stages = {'account-link': 'account_link',
                      'candidate-account-link-epiceos': 'account_link',
                      'login-queue': 'login_queue',
                      'epiceos-session-research': 'local_session',
                      'character': 'character', 'entitlementsv2': 'entitlements',
                      'ramsgate-join': 'city_join'}
            if secure:
                label = stages.get(response.route)
                if label:
                    observations.stage(label, response.status)
            return response
    return MapPreviewApplication(database, allow_unverified_eos_sub=True,
                                 maintenance_response={'isMaintenance': False})
