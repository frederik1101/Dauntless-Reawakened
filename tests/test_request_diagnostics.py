"""Privacy and candidate-route tests; no real credentials or game data."""
import unittest
from unittest.mock import patch

from backend.login_routes import is_eos_account_link
from backend.request_diagnostics import describe_request


class RequestLabelTests(unittest.TestCase):
    def test_account_id_is_redacted_even_when_equal_to_a_route_literal(self):
        for value in ('private-player-123', 'login', 'heartbeat', 'epiceos'):
            with self.subTest(value=value):
                label = describe_request('gamesession-prod', '/account/link/epiceos/' + value)
                self.assertEqual(label.endpoint, '/account/link/epiceos/{id}')
                self.assertEqual(label.route_key, '-')

    def test_old_provider_is_distinguishable(self):
        self.assertEqual(describe_request('gamesession-prod', '/account/link/epic/secret').endpoint,
                         '/account/link/epic/{id}')

    def test_unknown_provider_is_never_disclosed(self):
        label = describe_request('gamesession-prod', '/account/link/private-provider/private-id')
        self.assertEqual(label.endpoint, '/account/link/{provider}/{id}')

    def test_queries_fragments_and_encoded_ids_are_not_disclosed(self):
        label = describe_request('gamesession-prod',
                                 '/account/link/epiceos/secret%40mail.invalid?token=SECRET#fragment')
        self.assertEqual(label.endpoint, '/account/link/epiceos/{id}')
        self.assertNotIn('SECRET', repr(label))
        self.assertNotIn('mail', repr(label))

    def test_telemetry_is_identified_without_claiming_a_successful_response(self):
        label = describe_request('tracking-prod', '/heartbeat?accountId=SECRET')
        self.assertEqual((label.service, label.endpoint), ('tracking-prod', '/heartbeat'))

    def test_trailing_slash_is_preserved_in_diagnostics(self):
        self.assertEqual(describe_request('login-queue-prod', '/login/').endpoint, '/login/')

    def test_unrecognised_paths_have_no_raw_segments(self):
        label = describe_request('auth-prod', '/private-user/private-password')
        self.assertEqual(label.endpoint, '<redacted>')
        self.assertRegex(label.route_key, r'^[0-9a-f]{16}$')
        self.assertNotIn('private', repr(label))

    def test_unknown_fingerprint_groups_path_without_query_values(self):
        a = describe_request('auth-prod', '/unknown/secret?one=FIRST')
        b = describe_request('auth-prod', '/unknown/secret?two=SECOND')
        c = describe_request('auth-prod', '/other/secret')
        self.assertEqual(a.route_key, b.route_key)
        self.assertNotEqual(a.route_key, c.route_key)

    def test_unknown_fingerprint_changes_when_process_key_changes(self):
        with patch('backend.request_diagnostics._PROCESS_KEY', b'a' * 32):
            a = describe_request('auth-prod', '/private')
        with patch('backend.request_diagnostics._PROCESS_KEY', b'b' * 32):
            b = describe_request('auth-prod', '/private')
        self.assertNotEqual(a.route_key, b.route_key)

    def test_invalid_inputs_do_not_escape_into_log(self):
        for path in ('/login\r\nSECRET', 'https://secret.invalid', '//secret.invalid',
                     '/\\secret', '/' + 'x' * 8193):
            with self.subTest(path_length=len(path)):
                self.assertEqual(describe_request('auth-prod', path).endpoint, '<invalid>')
        label = describe_request('secret.example.invalid', '/login')
        self.assertEqual(label.service, 'unrecognised')
        self.assertNotIn('secret', repr(label))

    def test_arbitrary_short_names_remain_private(self):
        for path in ('/bob', '/alice', '/abc123', '/login/SECRET', '/tags/SECRET'):
            self.assertEqual(describe_request('auth-prod', path).endpoint, '<redacted>')

    def test_service_distinguishes_same_path(self):
        self.assertEqual(describe_request('login-queue-prod', '/login').endpoint, '/login')
        self.assertEqual(describe_request('tracking-prod', '/login').endpoint, '<redacted>')

    def test_dynamic_loadout_and_progression_fields_are_redacted(self):
        for service, path, expected in (
            ('loadout-prod', '/loadout/private-account/private-character/all', '/loadout/{account}/{character}/all'),
            ('progression-prod', '/game_tuning/private-blob', '/game_tuning/{blob}'),
            ('mm2-prod', '/candidate/join/private-candidate', '/candidate/join/{candidate}'),
            ('presence-prod', '/ws/private-account', '/ws/{account}'),
        ):
            with self.subTest(service=service):
                self.assertEqual(describe_request(service, path).endpoint, expected)


class CandidateRouteTests(unittest.TestCase):
    def test_eos_account_link_has_narrow_match(self):
        self.assertTrue(is_eos_account_link('/account/link/epiceos/test-id_123'))

    def test_no_other_providers_missing_ids_or_extra_segments(self):
        for path in ('/account/link/epic/test', '/account/link/steam/test',
                     '/account/link/epiceos/', '/account/link/epiceos/a/b',
                     '/account/link/epiceos/a/', '/account/link/epiceos/%2f',
                     '/account/link/epiceos/' + 'x' * 257):
            with self.subTest(path=path):
                self.assertFalse(is_eos_account_link(path))


if __name__ == '__main__':
    unittest.main()
