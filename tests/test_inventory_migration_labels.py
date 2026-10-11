"""No real identifiers are used; HTTP method changes inventory slot meanings."""
import unittest
from backend.request_diagnostics import describe_request


class InventoryLabelTests(unittest.TestCase):
    def test_post_has_character_build_template(self):
        label = describe_request('dauntless-prod', '/inventory/private-id/private-build', 'POST')
        self.assertEqual(label.endpoint, '/inventory/{character}/{build}')
        self.assertNotIn('private', repr(label))

    def test_get_keeps_account_character_template(self):
        label = describe_request('dauntless-prod', '/inventory/private-account/private-id', 'GET')
        self.assertEqual(label.endpoint, '/inventory/{account}/{character}')

    def test_no_method_does_not_invent_slot_meanings(self):
        label = describe_request('dauntless-prod', '/inventory/private/private')
        self.assertEqual(label.endpoint, '/inventory/{first}/{second}')

    def test_empty_character_is_redacted(self):
        label = describe_request('dauntless-prod', '/inventory//private-build', 'POST')
        self.assertEqual(label.endpoint, '/inventory/{character}/{build}')

    def test_query_and_encoding_are_not_exposed(self):
        label = describe_request('dauntless-prod',
                                 '/inventory/private%40mail/secret%3Abuild?token=TOPSECRET', 'POST')
        self.assertEqual(label.endpoint, '/inventory/{character}/{build}')
        self.assertNotIn('TOPSECRET', repr(label))
        self.assertNotIn('mail', repr(label))

    def test_other_services_not_reclassified(self):
        label = describe_request('tracking-prod', '/inventory/private/private', 'POST')
        self.assertEqual(label.endpoint, '<redacted>')

    def test_controls_still_invalid(self):
        self.assertEqual(describe_request('dauntless-prod', '/inventory/secret\n/build', 'POST').endpoint,
                         '<invalid>')


if __name__ == '__main__':
    unittest.main()
