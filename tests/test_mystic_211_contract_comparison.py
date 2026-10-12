"""Mystic Paradox vs. 2.1.1 contract compatibility checks.

References:
https://github.com/pranav158/Mystic-Paradox/blob/main/ParadoxBackend/src/routes/login.ts
https://github.com/mixutin/dauntless-revived/blob/dauntless-revived/docs/findings/backend-contract.md

Synthetic checks only: no Epic authentication or real game connection.
"""
import json
import unittest

from backend.contract import login_queue, linked_account
from backend.protocol_211 import features, account_info, character_seed, game_session_response


class Mystic211ContractTests(unittest.TestCase):
    def test_queue_five_fields_and_open_state(self):
        data = login_queue()
        self.assertEqual(set(data), {"state", "error_code", "title", "message", "timeout"})
        self.assertEqual(data["state"], "OPEN")
        self.assertIs(type(data["timeout"]), int)

    def test_link_response_has_required_wrapper(self):
        data = linked_account()
        self.assertIsInstance(data["payload"], dict)
        self.assertIs(data["payload"]["isLinked"], True)

    def test_epiceos_session_uses_lowercase_keys(self):
        data = game_session_response("synthetic-id", "synthetic-token")
        self.assertEqual(data["payload"]["sessionid"], "synthetic-id")
        self.assertEqual(data["payload"]["sessiontoken"], "synthetic-token")
        self.assertNotIn("sessionToken", data["payload"])

    def test_features_have_211_compatibility_flags(self):
        data = features()
        self.assertIs(data["crossplay"], True)
        self.assertIs(data["crossprogression"], True)
        self.assertIs(data["payload"]["crossplay"], True)

    def test_account_identity_is_stable_in_shape(self):
        data = account_info("synthetic-account", "LocalSlayer")
        self.assertEqual(data["accountId"], "synthetic-account")
        self.assertEqual(data["username"], "LocalSlayer")

    def test_character_seed_is_json_string_with_only_string_values(self):
        seed = character_seed()
        self.assertIsInstance(seed, str)
        data = json.loads(seed)
        self.assertEqual(data["PlayerAccountProgressStep"], "EnteredRamsgate")
        self.assertTrue(all(isinstance(value, str) for value in data.values()))
        self.assertNotIn("HasFinishedTutorial", data)


if __name__ == "__main__":
    unittest.main()
