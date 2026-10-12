"""Standalone server tests; no proprietary game files."""
import io
import tempfile
import threading
import unittest
from pathlib import Path

from tools.standalone_server import self_test, serve, monitor_launcher_control


class StandaloneServerTests(unittest.TestCase):
    def test_self_test_does_not_claim_gameplay(self):
        result = self_test()
        self.assertEqual(result['api'], 'passed')
        self.assertEqual(result['gameplay_host'], 'not_implemented')
        self.assertEqual(result['epic_auth'], 'not_implemented')

    def test_parent_stop_message_and_eof_request_graceful_shutdown(self):
        for content in (b'STOP\n', b'STOP\r\n', b'', b'BAD\nSTOP\n'):
            with self.subTest(content=content):
                stop = threading.Event()
                monitor_launcher_control(io.BytesIO(content), stop)
                self.assertTrue(stop.is_set())

    def test_parent_pipe_read_failure_stops_server(self):
        class Broken:
            def readline(self, count):
                raise OSError('disconnected')
        stop = threading.Event()
        monitor_launcher_control(Broken(), stop)
        self.assertTrue(stop.is_set())

    def test_profile_variant_requires_snapshot_and_valid_allowlist_before_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)/'untouched'
            for variant, enabled in [('without-appearance', False), ('bad-name', True)]:
                with self.subTest(variant=variant, enabled=enabled):
                    with self.assertRaises(ValueError):
                        serve(home, 8765, mystic_profile=enabled, profile_variant=variant)
                    self.assertFalse(home.exists())

    def test_rejects_privileged_and_invalid_ports_before_editing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'untouched'
            for port in (0, 80, 443, 65536, True, '8765'):
                with self.subTest(port=port):
                    with self.assertRaises(ValueError):
                        serve(home, port)
                    self.assertFalse(home.exists())


if __name__ == '__main__':
    unittest.main()
