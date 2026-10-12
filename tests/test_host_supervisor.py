"""Tests for process lifecycle without an Unreal or Dauntless binary."""
import sys
import unittest

from tools.host_supervisor import HostSupervisor


class HostSupervisorTests(unittest.TestCase):
    def test_missing_executable(self):
        manager = HostSupervisor("missing-ramsgate-host-123456789.exe")
        with self.assertRaises(FileNotFoundError):
            manager.start()

    def test_start_stop(self):
        manager = HostSupervisor(sys.executable)
        try:
            pid = manager.start(("-c", "import time; time.sleep(30)"))
            self.assertGreater(pid, 0)
            self.assertTrue(manager.is_running())
            self.assertFalse(manager.status()["gameplay_ready"])
            with self.assertRaises(RuntimeError):
                manager.start()
        finally:
            manager.stop()
        self.assertFalse(manager.is_running())
        self.assertIsNone(manager.status()["pid"])

    def test_invalid_argument(self):
        manager = HostSupervisor(sys.executable)
        with self.assertRaises(ValueError):
            manager.start(("bad\x00arg",))


if __name__ == "__main__":
    unittest.main()
