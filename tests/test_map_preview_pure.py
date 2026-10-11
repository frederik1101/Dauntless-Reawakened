"""Synthetic tests. No game, network, accounts or process memory contents."""
import json
import logging
import unittest
from unittest.mock import Mock
from backend.map_preview import MapObservations
from tools.map_preview_support import (MAP, ENGINE_INI, EXACT_SHA256, heartbeat_map,
                                       watch, stop_owned)


class MapLabelTests(unittest.TestCase):
    def test_short_name(self):
        self.assertEqual(heartbeat_map(b'{"map":"ramsgate_01_persistent"}'), 'ramsgate')
    def test_full_name(self):
        self.assertEqual(heartbeat_map(json.dumps({'map': MAP}).encode()), 'ramsgate')
    def test_object_name(self):
        self.assertEqual(heartbeat_map(json.dumps({'map': MAP+'.ramsgate_01_persistent'}).encode()), 'ramsgate')
    def test_case(self):
        self.assertEqual(heartbeat_map(b'{"map":"RAMSGATE_01_PERSISTENT"}'), 'ramsgate')
    def test_login(self):
        self.assertEqual(heartbeat_map(b'{"map":"Map_LoginMenu"}'), 'login_menu')
    def test_unknown_is_not_copied(self):
        self.assertEqual(heartbeat_map(b'{"map":"private-account-token"}'), 'unknown')
    def test_substring_not_enough(self):
        self.assertEqual(heartbeat_map(b'{"map":"secret/ramsgate_01_persistent"}'), 'unknown')
    def test_query_not_accepted(self):
        self.assertEqual(heartbeat_map(b'{"map":"ramsgate_01_persistent?token=secret"}'), 'unknown')
    def test_invalid_json(self):
        self.assertEqual(heartbeat_map(b'bad'), 'invalid')
    def test_bounds(self):
        self.assertEqual(heartbeat_map(b'x'*65537), 'invalid')
    def test_wrong_types(self):
        for body in (b'[]', b'1', b'null', b'{"map":{}}', b'{"map":null}'):
            self.assertEqual(heartbeat_map(body), 'unknown')
    def test_no_listen_or_host_or_identity_settings(self):
        for forbidden in ('?listen', 'AuthToken', 'AccountId', 'CharacterId', 'HangsAreFatal', 'ServerDefaultMap'):
            self.assertNotIn(forbidden, ENGINE_INI)
        self.assertIn('GameDefaultMap='+MAP, ENGINE_INI)
        self.assertEqual(len(EXACT_SHA256), 64)


class ObservationTests(unittest.TestCase):
    def test_initial_is_not_success(self):
        self.assertFalse(MapObservations().report()['ramsgate_self_report_seen'])
    def test_map_is_not_join_or_render_proof(self):
        obs = MapObservations()
        obs.observe(b'{"map":"ramsgate_01_persistent"}')
        result = obs.report()
        self.assertTrue(result['ramsgate_self_report_seen'])
        for name in ('renderer_verified', 'game_server_started', 'client_join_verified', 'controllable_player_verified'):
            self.assertIs(result[name], False)
    def test_secret_never_logged_or_reported(self):
        obs = MapObservations()
        with self.assertLogs('reawakened.requests', logging.INFO) as logs:
            obs.observe(b'{"map":"secret-name", "server":"secret-ip", "token":"secret-token"}')
        self.assertNotIn('secret', repr(logs.output) + repr(obs.report()))
    def test_log_changes_bounded(self):
        obs = MapObservations()
        with self.assertLogs('reawakened.requests', logging.INFO) as logs:
            for i in range(100):
                obs.observe(b'{"map":"Map_LoginMenu"}' if i % 2 else b'{"map":"ramsgate_01_persistent"}')
        self.assertEqual(len(logs.output), 16)
    def test_report_is_copy(self):
        obs = MapObservations()
        obs.report()['map_report_counts']['ramsgate'] = 55
        self.assertFalse(obs.report()['ramsgate_self_report_seen'])


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.proc = Mock()
        self.proc.poll.return_value = None
        self.now = 0
    def sleep(self, delta):
        self.now += delta
    def run_watch(self, measure):
        return watch(self.proc, 30, measure=measure, clock=lambda: self.now, sleep=self.sleep, cap_mib=10)
    def test_time_limit(self):
        self.assertEqual(self.run_watch(lambda _: 1024)['termination'], 'time_limit')
        self.assertEqual(self.now, 30)
    def test_memory_limit(self):
        self.assertEqual(self.run_watch(lambda _: 10*1024*1024)['termination'], 'memory_limit')
    def test_query_failure(self):
        self.assertEqual(self.run_watch(Mock(side_effect=OSError('secret')))['termination'], 'memory_query_failed')
    def test_negative_or_noninteger_measurement(self):
        for value in (-1, True, '100'):
            self.assertEqual(self.run_watch(lambda _: value)['termination'], 'memory_query_failed')
    def test_exit(self):
        self.proc.poll.return_value = 0
        measure = Mock()
        self.assertEqual(self.run_watch(measure)['termination'], 'client_exited')
        measure.assert_not_called()
    def test_invalid_time(self):
        for seconds in (True, 0, 29, 181, 1.0):
            with self.assertRaises(ValueError):
                watch(self.proc, seconds)
    def test_stop_only_owned(self):
        self.proc.poll.side_effect = [None, 0]
        stop_owned(self.proc)
        self.proc.terminate.assert_called_once()
        self.proc.wait.assert_called_once_with(timeout=8)
        self.proc.kill.assert_not_called()
    def test_already_exited_is_not_terminated(self):
        self.proc.poll.return_value = 0
        stop_owned(self.proc)
        self.proc.terminate.assert_not_called()
    def test_forced_stop_after_timeout(self):
        import subprocess
        self.proc.poll.side_effect = [None, 0]
        self.proc.wait.side_effect = [subprocess.TimeoutExpired('owned',8), 0]
        stop_owned(self.proc)
        self.proc.kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
