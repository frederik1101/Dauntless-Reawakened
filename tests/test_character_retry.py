"""Same update version AND same bytes: idempotent local acknowledgement."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.application import Application
from backend.database import Database
from backend.post_login import PostLoginApplication

class CharacterRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name)/'players.sqlite3')
        self.app = PostLoginApplication(self.db)
        self.account = self.db.account('synthetic-character')['accountId']
        self.session = self.app.sessions.create(self.account)
        self.character = self.db.create(self.account, 'Slayer', '{"state":"unchanged"}')
        self.headers = {'Authorization':'Bearer '+self.session.session_token}
        self.payload = {'characterId':self.character['id'], 'updateVersion':1,
                        'data':'{"state":"unchanged","LoginTime":"synthetic"}'}

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def write(self, body=None, headers=None):
        return self.app.handle('POST','dauntless-prod.steelyard.ca','/character',
                    self.headers if headers is None else headers,
                    json.dumps(self.payload if body is None else body).encode(),secure=True)

    def test_identical_retry_acknowledged_without_write(self):
        self.assertEqual(self.write().status, 200)
        before = self.db._db.total_changes
        original = self.db.get(self.account)
        self.assertEqual(self.write().payload, {'data':self.payload['data']})
        self.assertEqual(self.db._db.total_changes, before)
        self.assertEqual(self.db.get(self.account), original)

    def test_same_version_different_data_conflicts(self):
        self.assertEqual(self.write().status,200)
        self.assertEqual(self.write({**self.payload,'data':'{}'}).status,409)
        self.assertEqual(self.db.get(self.account)[0]['data'],self.payload['data'])

    def test_older_version_conflicts_even_if_identical(self):
        self.write()
        self.write({**self.payload,'updateVersion':2})
        self.assertEqual(self.write().status,409)

    def test_parallel_retries_write_once(self):
        before = self.db._db.total_changes
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda _: self.write(),range(12)))
        self.assertTrue(all(reply.status==200 for reply in replies))
        self.assertEqual(self.db._db.total_changes-before,1)
        self.assertEqual(self.db.get(self.account)[0]['updateVersion'],1)

    def test_authentication_remains_required(self):
        self.assertEqual(self.write(headers={}).status,401)

    def test_other_accounts_cannot_retry(self):
        self.write()
        other = self.app.sessions.create(self.db.account('other')['accountId'])
        self.assertEqual(self.write(headers={'Authorization':'Bearer '+other.session_token}).status,400)

    def test_missing_required_field_is_not_accepted(self):
        self.assertEqual(self.write({'data':'{}'}).status,400)

    def test_no_full_data_merge_or_progress_jump(self):
        self.write()
        replacement = {'characterId':self.character['id'],'updateVersion':2,'data':'{"only":"replacement"}'}
        self.assertEqual(self.write(replacement).status,200)
        self.assertEqual(self.db.get(self.account)[0]['data'],replacement['data'])

    def test_baseline_conflict_semantics_unchanged(self):
        self.write()
        baseline = Application(self.db,sessions=self.app.sessions)
        response = baseline.handle('POST','dauntless-prod.steelyard.ca','/character',self.headers,
                                   json.dumps(self.payload).encode(),secure=True)
        self.assertEqual(response.status,409)
