"""Exercise HTTP routes without launching Dauntless or contacting Epic."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from backend import server
from backend.persistence import JsonCharacterRepository


class HttpContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.store = JsonCharacterRepository(Path(cls.temp.name) / "characters.json")
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self, path, method="GET", data=None):
        payload = None if data is None else json.dumps(data).encode()
        request = Request(self.url + path, data=payload, method=method,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_features_and_account(self):
        self.assertTrue(self.request("/gamesession-prod/features/platform/win")["crossplay"])
        self.assertEqual(self.request("/auth-prod/accountinfo")["accountId"], server.DEMO_ACCOUNT)

    def test_linked_account_accepts_dynamic_id(self):
        self.assertTrue(self.request("/gamesession-prod/account/link/epic/example-id")["payload"]["isLinked"])

    def test_unknown_route_has_no_body(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/unknown-route")
        self.assertEqual(caught.exception.code, 404)
        self.assertEqual(caught.exception.read(), b"")

    def test_login_queue(self):
        self.assertEqual(self.request("/login-queue-prod/login", "POST")["state"], "OPEN")

    def test_character_creation_persists(self):
        created = self.request("/dauntless-prod/character", "PUT", {"name": "Slayer"})
        entries = self.request("/dauntless-prod/character")
        match = next(x for x in entries if x["id"] == created["id"])
        self.assertEqual(json.loads(match["data"])["PlayerAccountProgressStep"], "EnteredRamsgate")
        reopened = JsonCharacterRepository(server.store.path)
        self.assertTrue(any(x["id"] == created["id"] for x in reopened.get(server.DEMO_ACCOUNT)))


if __name__ == "__main__":
    unittest.main()
