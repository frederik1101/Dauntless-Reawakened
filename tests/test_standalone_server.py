"""Standalone server tests; no proprietary game files."""
import tempfile
import threading
import unittest
from pathlib import Path

from tools.standalone_server import self_test, serve


class StandaloneServerTests(unittest.TestCase):
    def test_self_test_does_not_claim_gameplay(self):
        result = self_test()
        self.assertEqual(result['api'], 'passed')
        self.assertEqual(result['gameplay_host'], 'not_implemented')
        self.assertEqual(result['epic_auth'], 'not_implemented')

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
