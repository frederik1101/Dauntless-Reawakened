"""Document Revived 1.4.4 contract differences without changing 2.1.1 behavior."""
import json
import unittest
from backend.application import Application
from backend.database import Database


class UE4ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.app = Application(self.db, lab_key="fixture")
        r = self.app.handle("POST", "127.0.0.1", "/__lab/session",
                            {"X-Reawakened-Lab-Key": "fixture"},
                            json.dumps({"subject": "test"}).encode(), secure=True)
        self.assertEqual(r.status, 200)
        self.auth = {"Authorization": "BEARER " + r.payload["payload"]["sessiontoken"]}

    def tearDown(self):
        self.db.close()

    def request(self, method, body=None):
        return self.app.handle(method, "dauntless-prod.steelyard.ca", "/character",
                               self.auth, json.dumps(body).encode() if body is not None else b"",
                               secure=True)

    def test_new_account_flow_differs_from_revived_auto_create(self):
        first = self.request("GET")
        self.assertEqual(first.status, 200)
        self.assertEqual(first.payload, [])
        # Revived 1.4.4 auto-creates at this stage; Reawakened deliberately does not.
        created = self.request("PUT", {"name": "Slayer"})
        self.assertEqual(created.status, 200)
        self.assertEqual(set(created.payload), {"id", "name"})
        after = self.request("GET")
        self.assertEqual(after.status, 200)
        self.assertEqual(len(after.payload), 1)
        self.assertEqual(set(after.payload[0]), {"id", "name", "updateVersion", "data"})
        self.assertEqual(after.payload[0]["updateVersion"], 0)
        self.assertNotEqual(json.loads(after.payload[0]["data"]), {})


if __name__ == "__main__":
    unittest.main()
