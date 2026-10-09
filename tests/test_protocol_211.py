import json
import unittest
from backend.protocol_211 import features, account_info, character_seed, game_session_response


class Protocol211Tests(unittest.TestCase):
    def test_features_are_flat_and_wrapped(self):
        result = features()
        self.assertTrue(result["crossplay"])
        self.assertTrue(result["payload"]["crossprogression"])

    def test_account_info_is_flat(self):
        self.assertEqual(account_info("account-1", "Slayer"),
                         {"username": "Slayer", "accountId": "account-1"})

    def test_character_seed_contains_only_string_values(self):
        seed = json.loads(character_seed())
        self.assertEqual(seed["PlayerAccountProgressStep"], "EnteredRamsgate")
        self.assertNotIn("HasFinishedTutorial", seed)
        self.assertTrue(all(isinstance(v, str) for v in seed.values()))

    def test_game_session_is_wrapped(self):
        payload = game_session_response("session-1", "test-token")
        self.assertEqual(payload["payload"]["sessionid"], "session-1")
        self.assertEqual(payload["code"], "OK")


if __name__ == "__main__":
    unittest.main()
