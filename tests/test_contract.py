"""Run with: python -m unittest discover -s tests -v"""
import json
import unittest
from backend.contract import CharacterStore, linked_account, login_queue


class ContractTests(unittest.TestCase):
    def test_login_queue_has_exact_fields(self):
        response = login_queue()
        self.assertEqual(set(response), {"state", "error_code", "title", "message", "timeout"})
        self.assertEqual(response["state"], "OPEN")

    def test_gamesession_response_is_wrapped(self):
        response = linked_account()
        self.assertEqual(response["code"], "OK")
        self.assertTrue(response["payload"]["isLinked"])

    def test_character_lifecycle(self):
        store = CharacterStore()
        created = store.create("Dragonkiller")
        self.assertEqual(len(store.list()), 1)
        self.assertEqual(store.list()[0]["data"], None)
        saved = store.save(created["id"], json.dumps({"level": 1}), 1)
        self.assertEqual(json.loads(saved["data"])["level"], 1)
        self.assertEqual(store.list()[0]["updateVersion"], 1)

    def test_version_is_not_double_incremented(self):
        store = CharacterStore()
        created = store.create("Slayer")
        store.save(created["id"], "{}", 5)
        self.assertEqual(store.list()[0]["updateVersion"], 5)
        with self.assertRaises(ValueError):
            store.save(created["id"], "{}", 5)


if __name__ == "__main__":
    unittest.main()
