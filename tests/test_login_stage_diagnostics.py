# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic logs only; no game files, tokens, or real account identifiers."""
import json
import unittest
from tools.login_stage_diagnostics import summarize, compare


def trace(request_id, method, route, status=200, *, response=None, extra=None, delivered=True):
    record = {'request_id': f'{request_id:016x}', 'phase': 'prepared',
              'method': method, 'route': route, 'status': status}
    record.update(extra or {})
    if response is not None:
        record['character_response'] = response
    line = '2026-10-12T16:59:58Z INFO PROTOCOL_TRACE '+json.dumps(record)+'\n'
    if delivered:
        line += ('2026-10-12T16:59:58Z INFO PROTOCOL_TRACE_END '
                 f'request_id={request_id:016x} delivery=written_to_socket\n')
    return line


class LoginStageDiagnosticsTests(unittest.TestCase):
    def test_real_sequence_empty_create_populated_is_not_gameplay(self):
        log = (trace(1, 'PUT', 'epiceos-session-research') +
               trace(2, 'GET', 'character', response={'character_count': 0, 'characters': []}) +
               trace(3, 'PUT', 'character', response={'shape': 'object[id:string,name:string]'}) +
               trace(4, 'GET', 'character', response={'character_count': 1, 'characters': [{
                   'data': {'field_count': 9, 'known_field_types': {'AppearanceData': 'string'},
                            'progress_state': 'EnteredRamsgate'}}]}))
        out = summarize(log)
        self.assertEqual(out['stage'], 'character_loaded')
        self.assertEqual(out['character_get_empty_200_written'], 1)
        self.assertEqual(out['character_put_create_200_written'], 1)
        self.assertEqual(out['character_get_populated_200_written'], 1)
        self.assertEqual(out['post_character_200_written'], 0)
        self.assertEqual(out['observed_field_counts'], [9])
        self.assertTrue(out['appearance_field_observed'])
        self.assertEqual(out['city_join_200_written'], 0)

    def test_unsent_200_never_counts_as_delivered(self):
        log = (trace(1, 'PUT', 'epiceos-session-research', delivered=False) +
               trace(2, 'GET', 'character', response={'character_count': 2}, delivered=False))
        out = summarize(log)
        self.assertEqual(out['stage'], 'no_exchange')
        self.assertEqual(out['prepared_without_socket_write_confirmation'], 2)

    def test_account_audit_does_not_emit_secret_fields(self):
        audit = {'local_account_at_exchange': {'preexisting': False, 'owned_characters': 0,
                                                'identity': 'SECRET-USER-ID'},
                 'profile_selection': {'variant': 'without-appearance', 'path': 'SECRET-PATH'},
                 'token': 'SECRET-TOKEN', 'session_alias': 'SECRET-ALIAS'}
        log = trace(1, 'PUT', 'epiceos-session-research', extra=audit)
        safe = json.dumps(summarize(log))
        self.assertNotIn('SECRET', safe)
        self.assertIn('without-appearance', safe)
        self.assertIn('"preexisting": false', safe)

    def test_status_404_ignored_for_progress_and_compare_is_descriptive(self):
        before = summarize(trace(1, 'PUT', 'epiceos-session-research') +
                           trace(2, 'GET', 'character', response={'character_count':1}) +
                           trace(3, 'GET', 'post-login-tuning-island-content'))
        after = summarize(trace(1, 'PUT', 'epiceos-session-research') +
                          trace(2, 'GET', 'character', response={'character_count':1}) +
                          trace(3, 'POST', 'unknown', status=404))
        difference = compare(before, after)
        self.assertTrue(difference['stage_regressed'])
        self.assertEqual(after['unimplemented_404_written'], 1)
        self.assertEqual(after['stage'], 'character_loaded')
        self.assertIn('not causal', difference['interpretation'])

    def test_post_character_before_character_is_not_progress(self):
        log = (trace(1, 'PUT', 'epiceos-session-research') +
               trace(2, 'GET', 'post-login-tuning-island-content') +
               trace(3, 'GET', 'character', response={'character_count': 1}))
        report = summarize(log)
        self.assertEqual(report['stage'], 'character_loaded')
        self.assertEqual(report['post_character_200_written'], 0)

    def test_malformed_and_unbounded_input_fail_closed(self):
        self.assertEqual(summarize('INFO PROTOCOL_TRACE {bad\n')['stage'], 'no_exchange')
        with self.assertRaises(ValueError):
            summarize('x'*(2*1024*1024+1))


if __name__ == '__main__':
    unittest.main()
