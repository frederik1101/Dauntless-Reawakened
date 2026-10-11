import unittest
import time
from backend.safe_diagnostics import shape, diagnostic_record


class SafeDiagnosticTests(unittest.TestCase):
    def test_sensitive_values_and_dynamic_keys_never_logged(self):
        secret = 'SECRET_BEARER_TOKEN_DO_NOT_LOG'
        private_id = '0123456789abcdefPRIVATEACCOUNT'
        payload = {
            'accountMappings': {private_id: {'accountId': private_id}},
            'payload': {'data': secret},
            private_id: secret,
            'characters': [{'id': private_id}],
        }
        output = diagnostic_record('POST', 'post-login-account-mapping', 200,
                                   payload, 75, time.perf_counter_ns(),
                                   session_valid=True)
        self.assertNotIn(secret, output)
        self.assertNotIn(private_id, output)
        self.assertIn('accountMappings:object', output)
        self.assertIn('session', output)

    def test_unsupported_route_and_field_names_redacted(self):
        output = diagnostic_record('GET', 'secret/value?token=x', 404,
                                   {'sensitive-username': 'private'}, 0,
                                   time.perf_counter_ns(), session_valid=False)
        self.assertNotIn('sensitive-username', output)
        self.assertNotIn('secret/value', output)
        self.assertIn('unknown', output)

    def test_response_types_and_sizes(self):
        self.assertEqual(shape({'payload': [], 'updateVersion': 2}),
                         'object[payload:array,updateVersion:integer]')
        self.assertEqual(shape(None), 'null')


if __name__ == '__main__':
    unittest.main()
