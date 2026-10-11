"""Trace modes reuse the existing journal/Windows-runner fixture."""
import io
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import test_map_preview_integration as integration
from tools import ramsgate_map_preview as preview
from tools.local_tls import generate

class ClientTraceRunnerTests(unittest.TestCase):
    def setUp(self):
        # Generate real test TLS before the Windows fixture substitutes a fake
        # SystemRoot; OpenSSL may load the OS entropy provider on first use.
        self.tls_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tls_tmp.cleanup)
        self.tls_template = generate(Path(self.tls_tmp.name) / 'tls')
        self.fixture = integration.RunnerTests(methodName='test_decline_makes_no_state')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.fixture.stack.enter_context(patch.object(
            preview, 'generate', side_effect=self.copy_test_tls))

    def copy_test_tls(self, destination):
        shutil.copytree(self.tls_template, destination)
        return Path(destination)

    def test_trace_normal_login_keeps_rollback_and_filters_client_output(self):
        f = self.fixture
        f.proc.stdout = io.BytesIO(b'LogOnline: LoginOperation Failed - Error = PRIVATE\n')
        preview.run_preview(f.game, f.home, 30, normal_login=True, trace_client=True)
        report = f.report()
        f.assertTrue(report['restored'])
        f.assertEqual(report['client_trace']['marker_counts'], {'login_operation_failed': 1})
        f.assertNotIn('PRIVATE', json.dumps(report))
        args, kwargs = f.launch.call_args
        f.assertIn('-stdout', args[0])
        f.assertEqual(kwargs['stdout'], preview.subprocess.PIPE)
        f.assertEqual((f.config/'Engine.ini').read_text(), 'original')

    def test_external_trace_marks_backend_not_collected(self):
        f = self.fixture
        self.copy_test_tls(f.user/'DauntlessReawakenedServer/tls')
        f.connection.return_value.getresponse.return_value.read.return_value = json.dumps({
            'experimental_login_port': True, 'post_login_revision': preview.REVISION}).encode()
        f.proc.stdout = io.BytesIO(b'LogJson: Json Value of type String used as Object PRIVATE\n')
        preview.run_preview(f.game, f.home, 30, normal_login=True,
                            external_server=True, trace_client=True)
        report = f.report()
        f.assertTrue(report['restored'])
        f.assertIsNone(report['backend_stage_counts'])
        f.assertEqual(report['backend_observation'], 'not_collected_external_server')
        f.assertEqual(report['client_trace']['marker_counts'], {'json_type_mismatch': 1})
        f.servers.assert_not_called()
        f.assertFalse((f.home/'normal-login.sqlite3').exists())

