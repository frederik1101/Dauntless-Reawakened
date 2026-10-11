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

    def observe(self, body):
        label = heartbeat_map(body)
        with self._lock:
            self._counts[label] = min(self._counts[label] + 1, 100000)
            if label != self._last and self._changes < 16:
                self._changes += 1
                self._last = label
                logging.getLogger('reawakened.requests').info('MAP_SELF_REPORT label=%s', label)

    def report(self):
        with self._lock:
            return {'map_report_counts': dict(self._counts),
                    'ramsgate_self_report_seen': self._counts['ramsgate'] > 0,
                    'renderer_verified': False, 'game_server_started': False,
                    'client_join_verified': False, 'controllable_player_verified': False}


def make_application(database, observations):
    from .application import target
    from .mystic_login_port import LoginPortApplication
    class MapPreviewApplication(LoginPortApplication):
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
            return super().handle(method, host, path, headers, body, secure=secure)
    return MapPreviewApplication(database, allow_unverified_eos_sub=True,
                                 maintenance_response={'isMaintenance': False})
