import unittest
from backend.sessions import DemoSessionManager


class DemoSessionTests(unittest.TestCase):
    def test_create_resolve_revoke(self):
        manager = DemoSessionManager()
        first = manager.create("local-account")
        self.assertNotEqual(first.session_id, first.session_token)
        self.assertEqual(manager.resolve(first.session_token).account_id, "local-account")
        self.assertTrue(manager.revoke(first.session_token))
        self.assertIsNone(manager.resolve(first.session_token))

    def test_tokens_are_unique(self):
        manager = DemoSessionManager()
        tokens = {manager.create("local-account").session_token for _ in range(50)}
        self.assertEqual(len(tokens), 50)

    def test_unknown_token(self):
        self.assertIsNone(DemoSessionManager().resolve("invalid"))


if __name__ == "__main__":
    unittest.main()
