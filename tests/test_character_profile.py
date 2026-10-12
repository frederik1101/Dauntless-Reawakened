# SPDX-License-Identifier: AGPL-3.0-only
import hashlib
import http.client
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from backend.character_profile import FIELDS, ProfileDatabase, normalize_profile
from backend.database import Database, VersionConflict
from backend.post_login import PostLoginApplication
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.profile_database import profile_snapshot

NOW = datetime(2026, 10, 12, 15, 30, 0, tzinfo=timezone.utc)
SEED = json.dumps({'PlayerAccountProgressStep': 'EnteredRamsgate',
                   'RecentPlayers': '{"RecentPlayers":[],"Version":0}'})


class ProfileNormalizationTests(unittest.TestCase):
    def test_observed_two_key_seed_becomes_nine_strings(self):
        output, added = normalize_profile(SEED, now=NOW)
        data = json.loads(output)
        self.assertEqual(len(data), 9)
        self.assertEqual(len(added), 7)
        self.assertTrue(all(type(v) is str for v in data.values()))
        self.assertEqual(data['PlayerAccountProgressStep'], 'EnteredRamsgate')
        self.assertEqual(data['LastChangelist'], '682875')

    def test_empty_flags_not_tutorial_completion(self):
        data = json.loads(normalize_profile(SEED, now=NOW)[0])
        for name in ('CharacterFlagData', 'LoginFlagData'):
            self.assertEqual(json.loads(data[name]), {'Flags': []})
        self.assertEqual(json.loads(data['PlayerDataRepair']), {'Data': []})
        self.assertNotIn('HasFinishedTutorial', data)
        self.assertNotIn('WatchedNewRamsgateCinematic', str(data))
        self.assertFalse(any(k.startswith('SERIE_') for k in data))

    def test_appearance_uses_structure_not_old_cosmetics(self):
        appearance = json.loads(json.loads(normalize_profile(SEED, now=NOW)[0])['AppearanceData'])
        self.assertEqual(appearance['CreationState'], 'EArchonCharacterCreationState::FaceComplete')
        self.assertEqual(appearance['StringData'], [])
        self.assertEqual(appearance['AssetReferences'], [])
        self.assertEqual(appearance['Data'], [{'SkeletalMeshComponentName': 'Head Slot', 'MorphData': []}])
        self.assertNotIn('Hair12', str(appearance))

    def test_new_state_is_not_advanced(self):
        for state in ('New', 'UnknownFutureState'):
            data = json.loads(normalize_profile(json.dumps({'PlayerAccountProgressStep': state}), now=NOW)[0])
            self.assertEqual(data['PlayerAccountProgressStep'], state)
            self.assertEqual(json.loads(data['AppearanceData'])['CreationState'],
                             'EArchonCharacterCreationState::NewCharacter')

    def test_missing_progress_is_not_invented(self):
        data = json.loads(normalize_profile('{}', now=NOW)[0])
        self.assertNotIn('PlayerAccountProgressStep', data)

    def test_preserves_existing_appearance_including_creation_state(self):
        raw = {'AppearanceData': '{"CreationState":"custom","StringData":[{"Key":"private","Data":"secret"}]}'}
        result = json.loads(normalize_profile(json.dumps(raw), now=NOW)[0])
        self.assertEqual(result['AppearanceData'], raw['AppearanceData'])

    def test_preserves_dates_and_old_changelist_not_overwrite_to_current(self):
        raw = {'LoginTime': 'old', 'LastLoginTime': 'older', 'LastChangelist': '392819'}
        result = json.loads(normalize_profile(json.dumps(raw), now=NOW)[0])
        for k, v in raw.items():
            self.assertEqual(result[k], v)

    def test_empty_existing_string_is_not_treated_as_missing(self):
        result = json.loads(normalize_profile('{"AppearanceData":"","LastChangelist":""}', now=NOW)[0])
        self.assertEqual(result['AppearanceData'], '')
        self.assertEqual(result['LastChangelist'], '')

    def test_unknown_fields_preserved(self):
        result = json.loads(normalize_profile('{"opaque-private-name":"private-value"}', now=NOW)[0])
        self.assertEqual(result['opaque-private-name'], 'private-value')

    def test_repeat_has_identical_bytes(self):
        first, _ = normalize_profile(SEED, now=NOW)
        second, added = normalize_profile(first, now=NOW.replace(year=2027))
        self.assertEqual(first, second)
        self.assertEqual(added, ())

    def test_retry_reuses_stored_dates(self):
        first, _ = normalize_profile(SEED, now=NOW)
        second, _ = normalize_profile(SEED, previous=first, now=NOW.replace(year=2027))
        self.assertEqual(first, second)

    def test_utc_date_format(self):
        data = json.loads(normalize_profile('{}', now=NOW)[0])
        self.assertEqual(data['LoginTime'], '2026.10.12-15.30.00')
        self.assertEqual(data['LastLoginTime'], data['LoginTime'])

    def test_invalid_data_not_silently_replaced(self):
        for text in ('', '[]', 'null', '{"x":true}', '{"x":{}}', '{"x":"1","x":"2"}', 12, '{}'*150000):
            with self.subTest(text=str(text)[:30]), self.assertRaises((ValueError, TypeError)):
                normalize_profile(text, now=NOW)

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            normalize_profile('{}', now=NOW.replace(tzinfo=None))


class ProfileDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        original = Database(self.home/'players.sqlite3')
        self.account = original.account('eos-research:synthetic')['accountId']
        self.char = original.create(self.account, 'Synthetic', SEED)['id']
        original.save(self.account, self.char, SEED, 7)
        original.close()
        self.original_hash = hashlib.sha256((self.home/'players.sqlite3').read_bytes()).hexdigest()
        self.copy_path = profile_snapshot(self.home)
        self.db = ProfileDatabase(self.copy_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_original_unchanged_copy_has_same_identity_and_version(self):
        self.assertEqual(hashlib.sha256((self.home/'players.sqlite3').read_bytes()).hexdigest(), self.original_hash)
        row = self.db.get(self.account)[0]
        self.assertEqual(row['id'], self.char)
        self.assertEqual(row['updateVersion'], 7)
        self.assertEqual(len(json.loads(row['data'])), 9)
        original = Database(self.home/'players.sqlite3')
        try:
            self.assertEqual(original.get(self.account)[0]['data'], SEED)
        finally:
            original.close()

    def test_original_path_cannot_enable_profile_database(self):
        with self.assertRaises(ValueError):
            ProfileDatabase(self.home/'players.sqlite3')
        self.assertEqual(hashlib.sha256((self.home/'players.sqlite3').read_bytes()).hexdigest(),self.original_hash)

    def test_fresh_copy_each_invocation_never_reuses_test_state(self):
        other = profile_snapshot(self.home)
        self.assertNotEqual(self.copy_path, other)
        raw = Database(other)
        try:
            self.assertEqual(raw.get(self.account)[0]['data'], SEED)
        finally:
            raw.close()

    def test_save_omitted_defaults_returns_normalized_data_and_version(self):
        old = self.db.get(self.account)[0]['data']
        saved = self.db.save(self.account, self.char, SEED, 8, allow_identical_retry=True)
        self.assertEqual(saved['data'], old)
        self.assertEqual(self.db.get(self.account)[0]['updateVersion'], 8)
        self.assertEqual(self.db.save(self.account, self.char, SEED, 8, allow_identical_retry=True), saved)

    def test_stale_and_changed_same_version_not_accepted(self):
        changed = json.dumps({'PlayerAccountProgressStep': 'New'})
        with self.assertRaises(VersionConflict):
            self.db.save(self.account, self.char, changed, 7, allow_identical_retry=True)
        with self.assertRaises(VersionConflict):
            self.db.save(self.account, self.char, SEED, 6, allow_identical_retry=True)

    def test_new_character_initialized_with_all_strings(self):
        char = self.db.create(self.account, 'Other', '{"PlayerAccountProgressStep":"New"}')['id']
        row = next(c for c in self.db.get(self.account) if c['id']==char)
        self.assertEqual(row['updateVersion'], 0)
        self.assertEqual(json.loads(row['data'])['PlayerAccountProgressStep'], 'New')

    def test_cross_account_save_stays_rejected(self):
        other = self.db.account('different')['accountId']
        with self.assertRaises(KeyError):
            self.db.save(other, self.char, SEED, 8)
        self.assertEqual(self.db.get(other), [])

    def test_parallel_identical_retries_write_once(self):
        def save(_):
            return self.db.save(self.account, self.char, SEED, 8, allow_identical_retry=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(save, range(24)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(self.db.get(self.account)[0]['updateVersion'], 8)

    def test_get_is_read_only_and_profile_reopen_is_idempotent(self):
        before = self.db._db.total_changes
        original = self.db.get(self.account)
        self.db.get(self.account)
        self.assertEqual(before, self.db._db.total_changes)
        self.db.close()
        self.db = ProfileDatabase(self.copy_path)
        self.assertEqual(self.db.get(self.account), original)
        self.assertEqual(self.db.profile_summary['characters_changed'], 0)

    def test_http_authentication_not_relaxed_and_health_honest(self):
        app = PostLoginApplication(self.db)
        self.assertEqual(app.handle('GET','dauntless-prod.steelyard.ca','/character',{},secure=True).status,401)
        health = app.handle('GET','localhost','/health',{},secure=True)
        self.assertFalse(health.payload['game_compatible'])
        self.assertFalse(health.payload['post_login_client_verified'])
        self.assertEqual(health.payload['character_profile_experiment']['fields_added'],7)

    def test_http_profile_save_returns_updated_not_raw_two_key_blob(self):
        app = PostLoginApplication(self.db)
        session = app.sessions.create(self.account)
        headers = {'Authorization':'Bearer '+session.session_token}
        body = json.dumps({'characterId':self.char,'data':SEED,'updateVersion':8}).encode()
        reply = app.handle('POST','dauntless-prod.steelyard.ca','/character',headers,body,secure=True)
        self.assertEqual(reply.status,200)
        self.assertIsInstance(reply.payload['data'],str)
        self.assertEqual(len(json.loads(reply.payload['data'])),9)
        app.sessions.revoke(session.session_token)
        self.assertEqual(app.handle('POST','dauntless-prod.steelyard.ca','/character',headers,body,secure=True).status,401)

    def test_no_inventory_currency_quest_grants(self):
        self.assertEqual(self.db.local_balances(self.account),{})
        self.assertEqual(self.db._db.execute('SELECT COUNT(*) FROM inventory_instances').fetchone()[0],0)
        self.assertFalse(any(k.startswith('SERIE_') for k in json.loads(self.db.get(self.account)[0]['data'])))

    def test_real_verified_tls_profile_flow(self):
        tls = generate(self.home/'test-tls')
        app = PostLoginApplication(self.db)
        server = make_server(app,'127.0.0.1',0,tls_context(tls/'server.pem',tls/'server-key.pem'))
        thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
        thread.start()
        conn = http.client.HTTPSConnection('127.0.0.1',server.server_address[1],
            context=ssl.create_default_context(cafile=str(tls/'ca.pem')),timeout=3)
        try:
            for n in (8,9):
                session = app.sessions.create(self.account)
                headers = {'Authorization':'Bearer '+session.session_token,'Host':'dauntless-prod.steelyard.ca'}
                conn.request('GET','/character',headers=headers)
                response=conn.getresponse(); data=json.loads(response.read())
                self.assertEqual(response.status,200)
                self.assertEqual(data[0]['updateVersion'],n-1)
                body=json.dumps({'characterId':self.char,'data':data[0]['data'],'updateVersion':n}).encode()
                conn.request('POST','/character',body,headers)
                response=conn.getresponse();saved=json.loads(response.read())
                self.assertEqual(response.status,200)
                self.assertEqual(saved['data'],data[0]['data'])
        finally:
            conn.close();server.shutdown();server.server_close();thread.join(3)
        self.assertEqual(hashlib.sha256((self.home/'players.sqlite3').read_bytes()).hexdigest(),self.original_hash)


class ProfileSnapshotTests(unittest.TestCase):
    def test_absent_source_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            new=profile_snapshot(home)
            self.assertTrue(new.is_file())
            self.assertFalse((home/'players.sqlite3').exists())

    def test_corrupt_source_is_not_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder); source=home/'players.sqlite3';source.write_bytes(b'not a database')
            with self.assertRaises(Exception):profile_snapshot(home)
            self.assertEqual(source.read_bytes(),b'not a database')

    def test_path_validation_precedes_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('tools.profile_database._plain_path',side_effect=ValueError('unsafe')):
                with self.assertRaises(ValueError):profile_snapshot(Path(folder))
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_original_snapshot_failed_copy_is_never_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);(home/'profile-tests').mkdir()
            old=home/'profile-tests'/'mystic-profile-old.sqlite3';old.write_bytes(b'incomplete')
            new=profile_snapshot(home)
            self.assertNotEqual(new,old);self.assertEqual(old.read_bytes(),b'incomplete')


class ProfileClientMarkerTests(unittest.TestCase):
    def test_specific_migration_failures_are_retained_without_raw_content(self):
        from tools.client_trace import ClientTrace
        trace = ClientTrace()
        trace.feed(b"LogOnline: Error: Player Data Migration Failed with invalid response PRIVATE_VALUE\n")
        report = trace.report()
        self.assertEqual(report['marker_counts']['migration_response_invalid'],1)
        self.assertNotIn('PRIVATE_VALUE',str(report))

    def test_missing_previous_build_is_not_login_failure(self):
        from tools.client_trace import classify_line
        labels = classify_line(b"LogOnline: Character's last active session was on an unknown CL.")
        self.assertIn('character_previous_build_missing',labels)
        self.assertNotIn('login_operation_failed',labels)


if __name__=='__main__': unittest.main()
