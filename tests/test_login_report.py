"""Read-only report regressions. Synthetic log fixtures, no credentials."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.login_report import collect_report, main, read_tail, summarize_client, summarize_probe


def event(method, route, status, service, endpoint):
    return f'INFO method={method} route={route} status={status} service={service} endpoint={endpoint} transport=https route_key=-\n'


class ProbeSummaryTests(unittest.TestCase):
    def test_pre_session_log_does_not_claim_login(self):
        text = event('GET', 'platform-features', 200, 'gamesession-prod', '/features/platform/{platform}')
        text += event('GET', 'unknown', 404, 'mailbox-prod', '<redacted>')
        result = summarize_probe(text)
        self.assertFalse(result['local_session_response_seen'])
        self.assertEqual(result['observed_successful_http_stage_sequence'], ['platform_features'])
        self.assertEqual(result['stage_failures'], [])

    def test_session_and_character_distinct_from_epic_ui(self):
        text = event('PUT', 'epiceos-session-research', 200, 'gamesession-prod', '/gamesession/epiceos')
        text += event('PUT', 'character', 200, 'dauntless-prod', '/character')
        result = summarize_probe(text)
        self.assertTrue(result['local_session_response_seen'])
        self.assertEqual(result['observed_successful_http_stage_sequence'], ['local_session_response', 'character_create'])

    def test_heartbeat_errors_are_not_login_stage_failures(self):
        result = summarize_probe(event('POST', 'unknown', 404, 'tracking-prod', '/heartbeat') * 20)
        self.assertEqual(result['stage_failures'], [])
        self.assertEqual(result['other_requests'][0]['count'], 20)

    def test_migration_http_error_reported_without_private_slots(self):
        result = summarize_probe(event('POST', 'inventory-migration-body-unsupported', 422,
                                       'dauntless-prod', '/inventory/{character}/{build}'))
        self.assertEqual(result['stage_failures'], [{'stage': 'inventory_migration', 'status': 422, 'count': 1}])

    def test_legacy_inventory_post_does_not_invent_slot_meanings(self):
        result = summarize_probe(event('POST', 'unknown', 404, 'dauntless-prod', '/inventory/{account}/{character}'))
        self.assertEqual(result['other_requests'][0]['kind'], 'legacy_inventory_post_unidentified')

    def test_sensitive_input_never_echoed(self):
        text = event('POST', 'unknown', 404, 'mailbox-prod', '/private-player?token=SECRET')
        text += event('GET', 'unknown', 404, 'secret-host', '/private-id')
        result = json.dumps(summarize_probe(text))
        for secret in ('SECRET', 'private-player', 'private-id', 'secret-host'):
            self.assertNotIn(secret, result)

    def test_session_flag_survives_sequence_limit(self):
        text = event('PUT', 'epiceos-session-research', 200, 'gamesession-prod', '/gamesession/epiceos')
        text += (event('GET', 'character', 200, 'dauntless-prod', '/character') +
                 event('PUT', 'character', 200, 'dauntless-prod', '/character')) * 40
        result = summarize_probe(text)
        self.assertTrue(result['local_session_response_seen'])
        self.assertEqual(len(result['observed_successful_http_stage_sequence']), 32)


class ClientMarkerTests(unittest.TestCase):
    def test_known_result_code_and_login_error_are_fixed_labels(self):
        result = summarize_client('[2026.10.11][12]LogEOSSDK: Error: ResultCode=EOS_InvalidAuth token=SECRET\n'
                                  'LogOnline: [LoginOpFailed] class=secret-user-name\n')
        self.assertEqual(result['recognised_marker_lines'], 2)
        self.assertIn('result_symbol:EOS_InvalidAuth', result['last_marker_lines'][0]['markers'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('secret-user-name', json.dumps(result))

    def test_unknown_result_and_urls_are_not_copied(self):
        result = summarize_client('LogEOSSDK: Error: ResultCode=EOS_SecretToken Password=secret@example.invalid\n')
        self.assertEqual(result['recognised_marker_lines'], 0)
        self.assertNotIn('SecretToken', json.dumps(result))

    def test_result_matching_requires_complete_token(self):
        result = summarize_client('LogEOSSDK: EOS_Success_private EOS_InvalidAuthentication\n')
        self.assertEqual(result['recognised_marker_lines'], 0)

    def test_non_log_body_not_classified(self):
        self.assertEqual(summarize_client('token=EOS_InvalidAuth\n')['recognised_marker_lines'], 0)

    def test_client_inventory_message_is_distinct(self):
        result = summarize_client("LogOnline: Failed to retrieve your character's inventory. account=SECRET\n")
        self.assertEqual(result['last_marker_lines'][0]['markers'], ['inventory_read_error'])

    def test_tls_error_does_not_expose_url(self):
        result = summarize_client('LogHttp: SSL certificate problem: https://private.invalid/token\n')
        self.assertEqual(result['last_marker_lines'][0]['markers'], ['tls_verification_error'])
        self.assertNotIn('private.invalid', json.dumps(result))

    def test_last_markers_are_bounded(self):
        result = summarize_client('LogOnline: [LoginOpFailed]\n' * 80)
        self.assertEqual(len(result['last_marker_lines']), 32)
        self.assertEqual(result['recognised_marker_lines'], 80)

    def test_oversized_lines_skipped(self):
        result = summarize_client('LogOnline: [LoginOpFailed] ' + 'a' * 17000)
        self.assertEqual(result['oversized_lines_skipped'], 1)
        self.assertEqual(result['recognised_marker_lines'], 0)


class ReadOnlyReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_missing_paths_create_nothing(self):
        result = collect_report(self.root / 'state', self.root / 'logs')
        self.assertEqual(result['probe_current']['read_status'], 'not_found')
        self.assertEqual(result['game_log_scan'], 'log_directory_not_found')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_files_unchanged_and_filename_private(self):
        logs = self.root / 'logs'
        logs.mkdir()
        path = logs / 'private-name.log'
        path.write_bytes(b'LogEOSSDK: EOS_Canceled username=SECRET\n')
        original = path.read_bytes()
        result = collect_report(self.root / 'state', logs)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(logs.iterdir()), [path])
        self.assertNotIn('private-name', json.dumps(result))
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertIn('not_established', result['client_log_correlation'])

    def test_selects_only_two_latest_logs(self):
        logs = self.root / 'logs'
        logs.mkdir()
        for i in range(4):
            path = logs / f'{i}.log'
            path.write_text('LogOnline: [LoginOpFailed]\n' * (i + 1))
            os.utime(path, (100 + i, 100 + i))
        (logs / 'credentials.json').write_text('SECRET')
        result = collect_report(self.root / 'state', logs)
        self.assertEqual([r['recognised_marker_lines'] for r in result['game_logs']], [4, 3])

    def test_scan_limit_is_reported_not_partial_selection(self):
        logs = self.root / 'logs'
        logs.mkdir()
        for i in range(4):
            (logs / f'{i}.log').write_text('test')
        with patch('tools.login_report.MAX_DIRECTORY_ENTRIES', 2):
            result = collect_report(self.root / 'state', logs)
        self.assertEqual(result['game_log_scan'], 'directory_limit_no_files_selected')
        self.assertEqual(result['game_logs'], [])

    def test_utf16_bom_supported(self):
        path = self.root / 'log.txt'
        path.write_bytes('LogEOSSDK: EOS_InvalidAuth\r\n'.encode('utf-16'))
        text, metadata = read_tail(path)
        self.assertEqual(summarize_client(text)['recognised_marker_lines'], 1)
        self.assertEqual(metadata['encoding'], 'utf-16-le')

    def test_tail_limit_discards_partial_first_line(self):
        path = self.root / 'log.txt'
        path.write_bytes(b'x' * 200 + b'\nLogOnline: [LoginOpFailed]\n')
        with patch('tools.login_report.MAX_BYTES', 100):
            text, metadata = read_tail(path)
        self.assertTrue(metadata['tail_only'])
        self.assertEqual(metadata['scanned_bytes'], 100)
        self.assertTrue(text.startswith('LogOnline:'))

    def test_final_newline_status_reported(self):
        path = self.root / 'log.txt'
        path.write_bytes(b'LogOnline: incomplete')
        _, metadata = read_tail(path)
        self.assertTrue(metadata['incomplete_final_line_possible'])

    def test_non_regular_input_refused(self):
        with self.assertRaises(ValueError):
            read_tail(self.root)

    def test_path_error_message_is_not_exposed(self):
        with patch('tools.login_report.read_tail', side_effect=PermissionError('private-user-secret')):
            result = collect_report(self.root, self.root / 'missing')
        self.assertNotIn('private-user-secret', json.dumps(result))

    def test_report_main_without_localappdata_has_no_side_effects(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'LOCALAPPDATA_not_available')

    def test_report_main_uses_only_expected_log_locations(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.root)}), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertTrue(json.loads(output.getvalue())['read_only'])


if __name__ == '__main__':
    unittest.main()
