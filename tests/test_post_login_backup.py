import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from backend.database import Database
from tools.post_login_backup import backup_before_post_login


class BackupTests(unittest.TestCase):
    def test_new_database_needs_no_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3'
            self.assertIsNone(backup_before_post_login(p));self.assertFalse(p.exists())
    def test_old_schema_backed_up_before_additive_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3';db=Database(p)
            a=db.account('existing')['accountId'];c=db.create(a,'Slayer','{}')
            db._db.execute('DROP TABLE local_store_balances');db._db.commit();db.close()
            before=p.read_bytes();backup=backup_before_post_login(p)
            self.assertTrue(backup.is_file());self.assertEqual(p.read_bytes(),before)
            conn=sqlite3.connect(str(backup))
            try:
                self.assertEqual(conn.execute('SELECT id FROM characters').fetchone()[0],c['id'])
                self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='local_store_balances'").fetchone())
            finally:conn.close()
            db=Database(p);db.close()
            self.assertIsNone(backup_before_post_login(p));self.assertTrue(backup.exists())
    def test_updated_database_is_not_backed_up_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3';db=Database(p);db.close()
            self.assertIsNone(backup_before_post_login(p))
            self.assertEqual(list(Path(tmp).iterdir()),[p])
    def test_collision_does_not_remove_existing_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3';db=Database(p)
            db._db.execute('DROP TABLE local_store_balances');db._db.commit();db.close()
            backup=Path(tmp)/'players.before-post-login-123.sqlite3';backup.write_bytes(b'keep')
            with patch('tools.post_login_backup.time.time_ns',return_value=123):
                with self.assertRaises(FileExistsError):backup_before_post_login(p)
            self.assertEqual(backup.read_bytes(),b'keep')
