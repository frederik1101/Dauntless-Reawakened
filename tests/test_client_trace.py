"""Real subprocess pipe tests with synthetic log lines, never a game process."""
import io
import json
import subprocess
import sys
import unittest

from tools.client_trace import ClientTrace, classify_line, TRACE_FLAGS, MAX_LINE_BYTES


class ClientTraceTests(unittest.TestCase):
    def test_exact_native_character_marker_has_no_values(self):
        raw = b'LogPhoenix: Error: [PRIVATE] OnSetHttpRequestComplete Failed To Parse, Missing Data Field token=SECRET\n'
        self.assertEqual(classify_line(raw), ('character_save_data_missing',))

    def test_non_log_text_is_not_classified(self):
        self.assertEqual(classify_line(b'LoginOperation Failed - Error = PRIVATE'), ())

    def test_utf16_ascii_line_supported(self):
        raw = 'LogOnline: Warning: LoginOperation Failed - Error = PRIVATE'.encode('utf-16le')
        self.assertEqual(classify_line(raw), ('login_operation_failed',))

    def test_timestamp_prefix_supported(self):
        raw = b'[2026.10.11-18.50.00:000][123]LogOnline: LoginOperation Failed - Error = PRIVATE'
        self.assertIn('login_operation_failed', classify_line(raw))

    def test_split_marker_is_reassembled(self):
        trace = ClientTrace()
        trace.feed(b'LogOnline: LoginOper')
        self.assertEqual(trace.report()['marker_counts'], {})
        trace.feed(b'ation Failed - Error = SECRET\n')
        self.assertEqual(trace.report()['marker_counts'], {'login_operation_failed': 1})
        self.assertNotIn('SECRET', json.dumps(trace.report()))

    def test_oversized_line_discarded_until_its_end(self):
        trace = ClientTrace()
        trace.feed(b'A' * (MAX_LINE_BYTES + 100))
        trace.feed(b'LogOnline: LoginOperation Failed - Error = FAKE\n')
        self.assertEqual(trace.report()['marker_counts'], {})
        self.assertEqual(trace.report()['oversized_lines_discarded'], 1)
        self.assertLessEqual(len(trace._pending), MAX_LINE_BYTES)
        trace.feed(b'LogOnline: LoginOperation Failed - Error = REAL\n')
        self.assertEqual(trace.report()['marker_counts'], {'login_operation_failed': 1})

    def test_no_newline_final_marker(self):
        trace = ClientTrace()
        trace.feed(b'LogJson: Json Value of type String used as Object SECRET')
        trace.eof()
        self.assertEqual(trace.report()['marker_counts'], {'json_type_mismatch': 1})
        self.assertEqual(trace.report()['stream_status'], 'eof')

    def test_reports_are_copies(self):
        trace = ClientTrace()
        trace.feed(b'LogOnline: LoginOperation Failed - Error = PRIVATE\n')
        report = trace.report()
        report['marker_counts']['login_operation_failed'] = 999
        report['recent_markers'][0]['label'] = 'changed'
        self.assertEqual(trace.report()['marker_counts']['login_operation_failed'], 1)
        self.assertEqual(trace.report()['recent_markers'][0]['label'], 'login_operation_failed')

    def test_event_history_bounded(self):
        trace = ClientTrace()
        trace.feed(b'LogOnline: LoginOperation Failed - Error = PRIVATE\n' * 100)
        self.assertEqual(len(trace.report()['recent_markers']), 64)
        self.assertEqual(trace.report()['marker_counts']['login_operation_failed'], 100)

    def test_empty_output_is_inconclusive(self):
        trace = ClientTrace()
        trace.start(io.BytesIO())
        report = trace.finish()
        self.assertEqual(report['stream_status'], 'eof')
        self.assertEqual(report['bytes_observed'], 0)
        self.assertIn('inconclusive', report['meaning'])

    def test_error_text_not_retained(self):
        class BadPipe(io.BytesIO):
            def read1(self, _):
                raise OSError('PRIVATE-PATH-and-TOKEN')
        trace = ClientTrace()
        trace.start(BadPipe())
        report = trace.finish()
        self.assertEqual(report['stream_status'], 'pipe_read_error')
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_only_logging_flags_no_auth_or_gameplay_override(self):
        self.assertEqual(TRACE_FLAGS, ('-stdout', '-FullStdOutLogOutput', '-FORCELOGFLUSH', '-UTF8Output'))

    def test_real_subprocess_is_drained_and_filtered(self):
        script = "import sys; sys.stdout.write('LogOnline: LoginOperation Failed - Error = SECRET\\n'); sys.stdout.flush()"
        proc = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        trace = ClientTrace()
        trace.start(proc.stdout)
        try:
            self.assertEqual(proc.wait(timeout=10), 0)
            report = trace.finish(timeout=5)
            self.assertEqual(report['stream_status'], 'eof')
            self.assertEqual(report['marker_counts'], {'login_operation_failed': 1})
            self.assertNotIn('SECRET', json.dumps(report))
        finally:
            if proc.poll() is None:
                proc.kill(); proc.wait()

if __name__ == '__main__':
    unittest.main()
