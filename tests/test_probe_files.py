import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.probe_files import prepare, restore, hosts_addition, MARKER
from tools.login_probe import inspect_client, EXE_RELATIVE


class ProbeFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ca, self.hosts, self.config = [self.root / name for name in ('cacert.pem', 'hosts', 'WindowsClient')]
        self.ca.write_bytes(b'original-ca-bundle\n')
        self.hosts.write_bytes(b'# original hosts\r\n127.0.0.1 localhost\r\n')
        self.config.mkdir()
        (self.config / 'Engine.ini').write_bytes(b'original Revived settings')
        self.state = self.root / 'state'
        self.names = ['auth-prod.steelyard.ca', 'login-queue-prod.steelyard.ca']
        self.pem = b'-----BEGIN CERTIFICATE-----\ntest-only-not-real\n-----END CERTIFICATE-----\n'
        self.original_ca = self.ca.read_bytes()
        self.original_hosts = self.hosts.read_bytes()

    def apply(self):
        return prepare(self.state, self.ca, self.hosts, self.config, self.pem, self.names)

    def test_round_trip_restores_exact_original_files_and_config(self):
        journal = self.apply()
        self.assertNotIn(b'original Revived settings', b''.join(p.read_bytes() for p in self.config.iterdir()))
        self.assertTrue((self.config / MARKER).exists())
        self.assertIn(b'auth-prod.steelyard.ca', self.hosts.read_bytes())
        restore(journal)
        self.assertEqual(self.ca.read_bytes(), self.original_ca)
        self.assertEqual(self.hosts.read_bytes(), self.original_hosts)
        self.assertEqual((self.config / 'Engine.ini').read_bytes(), b'original Revived settings')
        self.assertTrue(json.loads(journal.read_text())['restored'])

    def test_missing_ca_is_temporary_and_removed_on_restore(self):
        self.ca.unlink()
        journal = self.apply()
        self.assertTrue(self.ca.is_file())
        self.assertIn(b'BEGIN CERTIFICATE', self.ca.read_bytes())
        self.assertFalse(json.loads(journal.read_text())['ca_existed'])
        restore(journal)
        self.assertFalse(self.ca.exists())
        self.assertEqual(self.hosts.read_bytes(), self.original_hosts)
        self.assertEqual((self.config / 'Engine.ini').read_bytes(), b'original Revived settings')

    def test_missing_ca_refuses_deleting_unrelated_content(self):
        self.ca.unlink()
        journal = self.apply()
        with self.ca.open('ab') as stream:
            stream.write(b'unrelated')
        with self.assertRaises(ValueError):
            restore(journal)
        self.assertTrue(self.ca.exists())
        self.assertFalse(json.loads(journal.read_text())['restored'])

    def test_second_restore_is_idempotent(self):
        journal = self.apply()
        restore(journal)
        restore(journal)
        self.assertEqual(self.ca.read_bytes(), self.original_ca)

    def test_unrelated_later_hosts_edits_are_preserved(self):
        journal = self.apply()
        with self.hosts.open('ab') as f:
            f.write(b'\n127.0.0.1 unrelated.local\n')
        restore(journal)
        self.assertEqual(self.hosts.read_bytes(), self.original_hosts + b'\n127.0.0.1 unrelated.local\n')

    def test_unrelated_later_ca_edits_are_preserved(self):
        journal = self.apply()
        with self.ca.open('ab') as f:
            f.write(b'other-added-certificate\n')
        restore(journal)
        self.assertEqual(self.ca.read_bytes(), self.original_ca + b'other-added-certificate\n')

    def test_conflicting_existing_host_mapping_refused_before_edits(self):
        self.hosts.write_bytes(b'10.1.2.3 auth-prod.steelyard.ca\n')
        with self.assertRaises(ValueError):
            self.apply()
        self.assertFalse(self.state.exists())
        self.assertEqual(self.ca.read_bytes(), self.original_ca)

    def test_even_existing_loopback_mapping_is_not_replaced(self):
        self.hosts.write_bytes(b'127.0.0.1 auth-prod.steelyard.ca\n')
        with self.assertRaises(ValueError):
            self.apply()

    def test_commented_mapping_is_not_a_conflict(self):
        self.hosts.write_bytes(b'# 10.1.2.3 auth-prod.steelyard.ca\n')
        original = self.hosts.read_bytes()
        journal = self.apply()
        restore(journal)
        self.assertEqual(self.hosts.read_bytes(), original)

    def test_missing_original_ca_is_supported(self):
        self.ca.unlink()
        journal = self.apply()
        self.assertTrue(self.ca.is_file())
        restore(journal)
        self.assertFalse(self.ca.exists())
        self.assertTrue(json.loads(journal.read_text())['restored'])

    def test_existing_state_is_not_overwritten(self):
        self.state.mkdir()
        with self.assertRaises(FileExistsError):
            self.apply()

    def test_unknown_hosts_encoding_refused(self):
        self.hosts.write_bytes('localhost'.encode('utf-16'))
        with self.assertRaises(ValueError):
            self.apply()

    def test_foreign_changes_to_own_ca_block_do_not_overwrite(self):
        journal = self.apply()
        self.ca.write_bytes(b'replaced by another application')
        current_hosts = self.hosts.read_bytes()
        with self.assertRaises(ValueError):
            restore(journal)
        self.assertEqual(self.hosts.read_bytes(), current_hosts)
        self.assertTrue((self.state / 'ca.original').exists())

    def test_no_original_config_restores_to_absence(self):
        (self.config / 'Engine.ini').unlink()
        self.config.rmdir()
        journal = self.apply()
        restore(journal)
        self.assertFalse(self.config.exists())

    def test_hosts_without_trailing_newline_roundtrip(self):
        self.hosts.write_bytes(b'127.0.0.1 localhost')
        journal = self.apply()
        restore(journal)
        self.assertEqual(self.hosts.read_bytes(), b'127.0.0.1 localhost')

    def test_failed_hosts_write_rolls_back_ca_and_config(self):
        original_write = Path.write_bytes
        failed = False
        def failing_write(path, value):
            nonlocal failed
            if path == self.hosts and not failed:
                failed = True
                raise OSError('simulated failure')
            return original_write(path, value)
        with patch.object(Path, 'write_bytes', failing_write):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(self.ca.read_bytes(), self.original_ca)
        self.assertEqual(self.hosts.read_bytes(), self.original_hosts)
        self.assertEqual((self.config / 'Engine.ini').read_bytes(), b'original Revived settings')

    def test_host_addition_contains_no_epic_domains(self):
        block = hosts_addition(self.original_hosts, self.names, 'test')
        self.assertNotIn(b'epicgames.com', block)
        self.assertIn(b'::1 auth-prod.steelyard.ca', block)

    def test_invalid_pem_has_no_side_effects(self):
        self.pem = b'not a certificate'
        with self.assertRaises(ValueError):
            self.apply()
        self.assertFalse(self.state.exists())


class ClientInspectionTests(unittest.TestCase):
    def test_read_only_pe_inspection_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe = root / EXE_RELATIVE
            exe.parent.mkdir(parents=True)
            ca = root / 'Engine/Content/Certificates/cacert.pem'
            ca.parent.mkdir(parents=True)
            ca.write_text('test bundle')
            data = bytearray(512)
            data[:2] = b'MZ'
            data[0x3c:0x40] = struct.pack('<I', 128)
            data[128:134] = b'PE\0\0\x64\x86'
            exe.write_bytes(data)
            with patch('tools.login_probe.EXPECTED_SIZE', 512):
                metadata = inspect_client(root)
            self.assertEqual(len(metadata['sha256']), 64)
            self.assertFalse(metadata['build_verified_by_hash'])
            self.assertEqual(exe.read_bytes(), data)
            self.assertEqual(ca.read_text(), 'test bundle')

    def test_missing_client_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                inspect_client(Path(tmp))
