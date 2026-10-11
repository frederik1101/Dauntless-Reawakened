"""Pure post-login contracts and real local SQLite/session tests. No game."""
import json
import tempfile
import unittest
from pathlib import Path
from backend.post_login_contracts import (
    TUNING, UnsupportedRequest, creator_response, mapping_response,
    public_account_response, read_object, reconcile_request, reconcile_response, tuning_response,
)
from backend.database import Database
from backend.session_store import SessionStore


def body(value):
    return json.dumps(value).encode()


class MappingTests(unittest.TestCase):
    def test_epic_maps_to_distinct_local_id(self):
        r = mapping_response(body({'srcAccountType':'epic','ids':['epic-a','epic-b']}), 'local-a','epic-a')
        self.assertEqual(r['accountMappings'], {'epic-a':{'accountId':'local-a','accountType':'phoenix'}})
        self.assertEqual(r['payload']['accountMappings'], r['accountMappings'])
    def test_reverse_mapping(self):
        r = mapping_response(body({'srcAccountType':'PHOENIX','ids':['local-a']}), 'local-a','epic-a')
        self.assertEqual(r['accountMappings']['local-a'], {'accountId':'epic-a','accountType':'epic'})
    def test_unasked_identity_not_disclosed(self):
        r = mapping_response(body({'srcAccountType':'epic','ids':['stranger']}),'local-a','epic-a')
        self.assertEqual(r['accountMappings'], {})
        self.assertNotIn('epic-a', str(r))
    def test_no_epic_link_for_lab(self):
        self.assertEqual(mapping_response(body({'srcAccountType':'epic','ids':['lab']}),'lab',None)['accountMappings'],{})
    def test_empty_ids(self):
        self.assertEqual(mapping_response(body({'srcAccountType':'epic','ids':[]}),'a','e')['accountMappings'],{})
    def test_duplicate_ids_deduplicated(self):
        r=mapping_response(body({'srcAccountType':'epic','ids':['e','e']}),'a','e')
        self.assertEqual(len(r['accountMappings']),1)
    def test_invalid_ids(self):
        for ids in ('e', [None], [{}], ['a\nb'], ['a'*257], ['a']*101):
            with self.subTest(ids=type(ids)), self.assertRaises(ValueError):
                mapping_response(body({'srcAccountType':'epic','ids':ids}),'a','e')
    def test_unknown_account_type(self):
        with self.assertRaises(UnsupportedRequest):
            mapping_response(body({'srcAccountType':'other','ids':[]}),'a','e')
    def test_extra_keys_rejected(self):
        with self.assertRaises(UnsupportedRequest):
            mapping_response(body({'srcAccountType':'epic','ids':[],'grant':True}),'a','e')
    def test_wrapped_map_is_independent(self):
        r=mapping_response(body({'srcAccountType':'epic','ids':['e']}),'a','e')
        r['accountMappings']['e']['accountId']='changed'
        self.assertEqual(r['payload']['accountMappings']['e']['accountId'],'a')
    def test_public_account_uses_actual_link_not_local_hash(self):
        r=public_account_response(body({'accountId':'local'}),'local','epic')
        self.assertEqual(r['linkedAccounts'],[{'accountId':'epic','accountType':'epic'}])
        self.assertEqual(r['accountId'],'local')
    def test_public_other_rejected(self):
        with self.assertRaises(PermissionError):
            public_account_response(body({'accountId':'other'}),'local','epic')
    def test_public_lab_has_no_fabricated_link(self):
        self.assertEqual(public_account_response(body({'accountId':'local'}),'local',None)['linkedAccounts'],[])
    def test_public_unknown_shape_rejected(self):
        with self.assertRaises(UnsupportedRequest):
            public_account_response(body({'displayname':'name'}),'local','epic')


class ParsingTests(unittest.TestCase):
    def test_duplicate_keys(self):
        with self.assertRaises(ValueError):read_object(b'{"x":1,"x":2}')
    def test_invalid_json_and_types(self):
        for b in (b'[]',b'null',b'{',b'{"x":NaN}',b'\xff',None,'{}'):
            with self.subTest(b=b),self.assertRaises(ValueError):read_object(b)
    def test_bound(self):
        with self.assertRaises(ValueError):read_object(b' '*65537)
    def test_empty_body_is_explicit(self):
        self.assertEqual(read_object(b'',empty=True),{})
        with self.assertRaises(ValueError):read_object(b'')


class TuningAndStoreTests(unittest.TestCase):
    def test_three_known_tunings(self):
        self.assertEqual(set(TUNING),{'seasonal_event_schedule','huntpass_xp_config','island_content_config'})
        for name in TUNING:
            self.assertEqual(tuning_response(name)['payload'],TUNING[name])
    def test_tuning_types(self):
        p=tuning_response('huntpass_xp_config')['payload']
        self.assertEqual(p['EventConfigs'],[])
        self.assertIs(type(p['GlobalConfig']['DifficultyBias']),float)
        self.assertIs(type(p['GlobalConfig']['MaxXPAwarded']),int)
    def test_tuning_is_fresh(self):
        tuning_response('seasonal_event_schedule')['payload']['ScheduledItems'].append('changed')
        self.assertEqual(tuning_response('seasonal_event_schedule')['payload']['ScheduledItems'],[])
    def test_unknown_tuning_fails(self):
        for name in ('bounty_game_data','../secret','seasonal_event_schedule/','private-account'):
            with self.subTest(name=name),self.assertRaises(KeyError):tuning_response(name)
    def test_reconcile_known_body(self):
        for b in (b'',b'{}',body({'authorization':'private-token'})):
            self.assertIsNone(reconcile_request(b))
    def test_reconcile_unknown_mutation_rejected(self):
        with self.assertRaises(UnsupportedRequest):reconcile_request(body({'receipt':'secret'}))
    def test_reconcile_authorization_type_and_bound(self):
        for val in ([],{},42,'x'*16385):
            with self.subTest(kind=type(val)),self.assertRaises(ValueError):reconcile_request(body({'authorization':val}))
    def test_snapshot_has_real_balances_and_no_refresh(self):
        r=reconcile_response({'CURRENCY_NOTES':7})
        self.assertEqual(r['balances']['CURRENCY_NOTES'],7)
        self.assertEqual(r['balances']['id_currency_notes'],7)
        self.assertEqual(r['balances']['CURRENCY_PLATINUM'],0)
        self.assertIs(r['refreshInventory'],False)
    def test_bad_balance_not_silently_zeroed(self):
        for b in ({'CURRENCY_NOTES':-1},{'CURRENCY_NOTES':True},{'SECRET':1},{'CURRENCY_NOTES':2**31}):
            with self.subTest(b=b),self.assertRaises(ValueError):reconcile_response(b)
    def test_creator_does_not_invent_affiliation(self):
        self.assertEqual(creator_response()['slug'],'')
        self.assertIs(creator_response()['success'],False)


class StorageTests(unittest.TestCase):
    def test_session_holds_binding_privately(self):
        store=SessionStore()
        s=store.create('account',linked_epic_id='private-epic')
        self.assertEqual(store.resolve(s.session_token).linked_epic_id,'private-epic')
        self.assertNotIn('private-epic',repr(s))
        self.assertNotIn(s.session_token,repr(s))
    def test_expired_and_revoked_link_unavailable(self):
        now=[0]
        store=SessionStore(ttl=5,clock=lambda:now[0])
        a=store.create('a',linked_epic_id='e')
        now[0]=6
        self.assertIsNone(store.resolve(a.session_token))
        b=store.create('b',linked_epic_id='f')
        store.revoke(b.session_token)
        self.assertIsNone(store.resolve(b.session_token))
    def test_invalid_link_rejected(self):
        for value in ('',True,[], 'x\ny','x'*257):
            with self.subTest(value=type(value)),self.assertRaises(ValueError):
                SessionStore().create('a',linked_epic_id=value)
    def test_no_link_by_default(self):
        self.assertIsNone(SessionStore().create('a').linked_epic_id)
    def test_sql_balances_persist_and_reads_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3'; db=Database(p)
            a=db.account('one')['accountId']; b=db.account('two')['accountId']
            c=db.create(a,'Slayer','{}')
            self.assertEqual(db.local_balances(a),{})
            db._db.execute('INSERT INTO local_store_balances VALUES (?,?,?)',(a,'CURRENCY_NOTES',9));db._db.commit()
            before=db._db.total_changes
            self.assertEqual(db.local_balances(a),{'CURRENCY_NOTES':9})
            self.assertEqual(db.local_balances(b),{})
            self.assertEqual(before,db._db.total_changes)
            db.close();db=Database(p)
            try:
                self.assertEqual(db.local_balances(a),{'CURRENCY_NOTES':9})
                self.assertEqual(db.get(a)[0]['id'],c['id'])
                self.assertEqual(db.get(a)[0]['updateVersion'],0)
            finally:db.close()
    def test_sql_schema_upgrade_keeps_existing_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'players.sqlite3'; db=Database(p)
            a=db.account('old')['accountId']; c=db.create(a,'OldSlayer','{}')
            db._db.execute('DROP TABLE local_store_balances');db._db.commit();db.close()
            db=Database(p)
            try:
                self.assertEqual(db.get(a)[0]['id'],c['id'])
                self.assertEqual(db.local_balances(a),{})
            finally:db.close()
