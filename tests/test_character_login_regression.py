"""Reproduce the observable empty-db character sequence from 2026-10-12.

This tests the repository's baseline Application, NOT the newer standalone
Windows launcher. Passing does not prove compatibility with the game client.
"""
import json
import unittest

from backend.application import Application
from backend.database import Database


class CharacterLoginRegressionTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.app = Application(self.db, lab_key="fixture-secret")
        issued = self.call("POST", "127.0.0.1", "/__lab/session",
                           {"subject": "solo-player"},
                           {"X-Reawakened-Lab-Key": "fixture-secret"})
        self.assertEqual(issued.status, 200)
        self.auth = {"Authorization": "BEARER " + issued.payload["payload"]["sessiontoken"]}

    def tearDown(self):
        self.db.close()

    def call(self, method, host, path, body=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        return self.app.handle(method, host, path, headers or {}, data, secure=True)

    def test_empty_create_read_sequence_and_seed(self):
        host = "dauntless-prod.steelyard.ca"
        before = self.call("GET", host, "/character", headers=self.auth)
        self.assertEqual(before.status, 200)
        self.assertEqual(before.payload, [])

        created = self.call("PUT", host, "/character", {"name": "SoloSlayer"}, self.auth)
        self.assertEqual(created.status, 200)
        self.assertEqual(set(created.payload), {"id", "name"})

        after = self.call("GET", host, "/character", headers=self.auth)
        self.assertEqual(after.status, 200)
        self.assertEqual(len(after.payload), 1)
        record = after.payload[0]
        self.assertEqual(record["id"], created.payload["id"])
        self.assertEqual(record["updateVersion"], 0)
        self.assertIsInstance(record["data"], str)
        seed = json.loads(record["data"])
        self.assertEqual(seed["PlayerAccountProgressStep"], "EnteredRamsgate")
        self.assertEqual(len(seed), 1)

    def test_first_create_request_does_not_supply_version_or_character_data(self):
        host = "dauntless-prod.steelyard.ca"
        created = self.call("PUT", host, "/character", {"name": "SoloSlayer"}, self.auth)
        self.assertEqual(created.status, 200)
        stored = self.call("GET", host, "/character", headers=self.auth).payload[0]
        self.assertEqual(stored["updateVersion"], 0)
        self.assertEqual(stored["id"], created.payload["id"])


if __name__ == "__main__":
    unittest.main()
