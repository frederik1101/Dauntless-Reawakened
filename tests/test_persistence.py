import json
import tempfile
import unittest
from pathlib import Path
from backend.persistence import JsonCharacterRepository


class PersistenceTests(unittest.TestCase):
    def test_create_save_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "characters.json"
            db = JsonCharacterRepository(path)
            record = db.create("test-account", "Dragonkiller")
            db.save("test-account", record["id"], json.dumps({"level": 3}), 1)
            reopened = JsonCharacterRepository(path)
            self.assertEqual(reopened.get("test-account")[0]["updateVersion"], 1)
            self.assertEqual(json.loads(reopened.get("test-account")[0]["data"])["level"], 3)

    def test_account_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = JsonCharacterRepository(Path(tmp) / "characters.json")
            db.create("account-a", "Slayer")
            self.assertEqual(db.get("account-b"), [])

    def test_reject_stale_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = JsonCharacterRepository(Path(tmp) / "characters.json")
            record = db.create("account-a", "Slayer")
            db.save("account-a", record["id"], "{}", 1)
            with self.assertRaises(ValueError):
                db.save("account-a", record["id"], "{}", 1)


if __name__ == "__main__":
    unittest.main()
