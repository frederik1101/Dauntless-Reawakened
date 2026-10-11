"""Post-login handlers over actual loopback TLS; synthetic identities, no game."""
import base64
import http.client
import json
import ssl
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.application import Application
from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.post_login_contracts import REVISION, TUNING
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.map_preview_support import login_test_duration, watch


def encoded(value):
    return json.dumps(value).encode()


def jwt(subject):
    # Deliberately synthetic and unsigned; the explicit research option is tested.
    payload=base64.urlsafe_b64encode(encoded({'sub':subject})).decode().rstrip('=')
    return 'e30.'+payload+'.c2ln'


class PostLoginTests(unittest.TestCase):
    def setUp(self):
        self.db=Database(':memory:'); self.addCleanup(self.db.close)
        self.app=PostLoginApplication(self.db,allow_unverified_eos_sub=True)
        self.epic='a'*32
        issued=self.app.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
                              {'Authorization':'Bearer '+jwt(self.epic)},secure=True)
        self.assertEqual(issued.status,200)
        self.token=issued.payload['payload']['sessiontoken']
        self.session=self.app.sessions.resolve(self.token)
        self.account=self.session.account_id
        self.headers={'Authorization':'Bearer '+self.token}
        self.char=self.db.create(self.account,'Slayer','{}')

    def call(self, method, service, path, payload=None, headers=None, secure=True):
        return self.app.handle(method,service+'.steelyard.ca',path,
            self.headers if headers is None else headers,
            b'' if payload is None else encoded(payload),secure=secure)

    def test_two_login_exchanges_preserve_character_and_version(self):
        """Reproduce two consecutive research logins without inventing Epic auth."""
        original = self.db.get(self.account)
        self.assertEqual(len(original), 1)
        first = self.call('GET', 'dauntless-prod', '/character')
        self.assertEqual(first.status, 200)
        self.assertEqual(first.payload, original)
        # A second login may rotate the local token, but must not create a
        # different account or silently reset the character.
        issued = self.app.handle(
            'PUT', 'gamesession-prod.steelyard.ca', '/gamesession/epiceos',
            {'Authorization': 'Bearer ' + jwt(self.epic)}, secure=True)
        self.assertEqual(issued.status, 200)
        token2 = issued.payload['payload']['sessiontoken']
        self.assertNotEqual(token2, self.token)
        session2 = self.app.sessions.resolve(token2)
        self.assertEqual(session2.account_id, self.account)
        self.assertEqual(session2.linked_epic_id, self.epic)
        second_headers = {'Authorization': 'Bearer ' + token2}
        second = self.call('GET', 'dauntless-prod', '/character',
                           headers=second_headers)
        self.assertEqual(second.status, 200)
        self.assertEqual(second.payload, original)
        self.assertEqual(self.db.get(self.account), original)

    def test_real_exchange_records_distinct_ids(self):
        self.assertNotEqual(self.account,self.epic)
        self.assertEqual(self.session.linked_epic_id,self.epic)
        self.assertNotEqual(self.token,jwt(self.epic))

    def test_self_mapping_and_public_link_are_consistent(self):
        r=self.call('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':[self.epic]})
        self.assertEqual(r.status,200)
        self.assertEqual(r.payload['accountMappings'][self.epic]['accountId'],self.account)
        r=self.call('POST','auth-prod','/accountinfo/public',{'accountId':self.account})
        self.assertEqual(r.payload['linkedAccounts'][0]['accountId'],self.epic)

    def test_foreign_mapping_is_omitted(self):
        r=self.call('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':['b'*32]})
        self.assertEqual((r.status,r.payload['accountMappings']),(200,{}))

    def test_foreign_public_account_rejected(self):
        self.assertEqual(self.call('POST','auth-prod','/accountinfo/public',{'accountId':'other'}).status,401)

    def test_no_session_cannot_use_any_new_route(self):
        for m,s,p in [('POST','auth-prod','/account/mapping'),('POST','store-prod','/reconcile'),
                      ('GET','store-prod','/creator'),('GET','store-prod','/balance')]+[
                      ('GET','progression-prod','/game_tuning/'+b) for b in TUNING]:
            with self.subTest(p=p):self.assertEqual(self.call(m,s,p,{},headers={}).status,401)

    def test_plaintext_rejected(self):
        self.assertEqual(self.call('GET','store-prod','/creator',secure=False).status,503)

    def test_browser_origin_rejected(self):
        r=self.call('GET','store-prod','/creator',headers={**self.headers,'Origin':'null'})
        self.assertEqual(r.status,403)

    def test_revoked_token_cannot_map(self):
        self.app.sessions.revoke(self.token)
        self.assertEqual(self.call('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':[]}).status,401)

    def test_reconcile_reads_sql_without_mutation(self):
        self.db._db.execute('INSERT INTO local_store_balances VALUES (?,?,?)',(self.account,'CURRENCY_NOTES',13))
        self.db._db.commit(); before=self.db._db.total_changes; characters=self.db.get(self.account)
        for _ in range(3):
            r=self.call('POST','store-prod','/reconcile',{'authorization':'private-placeholder'})
            self.assertEqual(r.status,200)
            self.assertEqual(r.payload['balances']['CURRENCY_NOTES'],13)
            self.assertIs(r.payload['refreshInventory'],False)
        self.assertEqual(before,self.db._db.total_changes)
        self.assertEqual(characters,self.db.get(self.account))

    def test_receipts_are_not_acknowledged(self):
        self.assertEqual(self.call('POST','store-prod','/reconcile',{'receipt':'x'}).status,422)

    def test_creator_negative_state(self):
        r=self.call('GET','store-prod','/creator')
        self.assertEqual(r.status,200);self.assertIs(r.payload['success'],False)
        self.assertEqual(r.payload['slug'],'')

    def test_all_known_tunings_serve_objects(self):
        for b,payload in TUNING.items():
            with self.subTest(blob=b):
                r=self.call('GET','progression-prod','/game_tuning/'+b)
                self.assertEqual(r.status,200);self.assertEqual(r.payload['payload'],payload)

    def test_unknown_tuning_does_not_echo_or_succeed(self):
        r=self.call('GET','progression-prod','/game_tuning/private-unrecognised-blob')
        self.assertEqual((r.status,r.body()),(404,b''))
        self.assertEqual(r.route,'post-login-tuning-unimplemented')

    def test_wrong_services_methods_and_purchases_untouched(self):
        for m,s,p in [('POST','store-prod','/account/mapping'),('GET','auth-prod','/account/mapping'),
                      ('POST','progression-prod','/game_tuning/seasonal_event_schedule'),
                      ('POST','store-prod','/creator'),('POST','store-prod','/notification/platinum')]:
            with self.subTest(path=p):self.assertEqual(self.call(m,s,p,{}).status,404)
        self.assertEqual(self.call('POST','dauntless-prod','/inventory',{}).status,503)

    def test_original_baseline_stays_unchanged(self):
        base=Application(self.db,sessions=self.app.sessions)
        r=base.handle('POST','auth-prod.steelyard.ca','/account/mapping',self.headers,b'{}',secure=True)
        self.assertEqual(r.status,404)

    def test_empty_or_invalid_mapping_not_faked(self):
        self.assertEqual(self.call('POST','auth-prod','/account/mapping',{}).status,422)
        self.assertEqual(self.call('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':None}).status,400)

    def test_health_is_revisioned_but_not_gameplay_ready(self):
        r=self.app.handle('GET','localhost','/health',{})
        self.assertEqual(r.payload['post_login_revision'],REVISION)
        self.assertIs(r.payload['post_login_client_verified'],False)
        self.assertIs(r.payload['game_compatible'],False)

    def test_city_still_requires_host_and_known_character(self):
        r=self.call('POST','mm2-prod','/candidate/join',{
            'playerId':self.account,'gameMode':'CITY','buildId':'682875_2.1.1_shipping'})
        self.assertEqual((r.status,r.payload['status']),(200,'MATCHING'))
        self.assertNotIn('serverInfo',r.payload)

    def test_account_identity_persists_but_old_session_does_not(self):
        old=self.account
        fresh=PostLoginApplication(self.db,allow_unverified_eos_sub=True)
        self.assertEqual(fresh.handle('GET','dauntless-prod.steelyard.ca','/character',self.headers,secure=True).status,401)
        r=fresh.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
                       {'Authorization':'Bearer '+jwt(self.epic)},secure=True)
        s=fresh.sessions.resolve(r.payload['payload']['sessiontoken'])
        self.assertEqual(s.account_id,old);self.assertEqual(s.linked_epic_id,self.epic)
        self.assertEqual(self.db.get(old)[0]['id'],self.char['id'])

    def test_research_exchange_stays_off_without_opt_in(self):
        app=PostLoginApplication(self.db)
        r=app.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
                     {'Authorization':'Bearer '+jwt(self.epic)},secure=True)
        self.assertEqual(r.status,503)


class RealTlsSequenceTests(unittest.TestCase):
    def test_exchange_mapping_tuning_and_register_over_tls(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'players.sqlite3');app=PostLoginApplication(db,allow_unverified_eos_sub=True)
            tls=generate(Path(tmp)/'tls')
            server=make_server(app,'127.0.0.1',0,tls_context(tls/'server.pem',tls/'server-key.pem'))
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
            context=ssl.create_default_context(cafile=str(tls/'ca.pem'))
            def request(m,service,path,payload=None,token=None):
                conn=http.client.HTTPSConnection('127.0.0.1',server.server_port,context=context,timeout=5)
                try:
                    headers={'Host':service+'.steelyard.ca'}
                    if token:headers['Authorization']='Bearer '+token
                    conn.request(m,path,body=b'' if payload is None else encoded(payload),headers=headers)
                    r=conn.getresponse();data=r.read()
                    return r.status,json.loads(data) if data else None
                finally:conn.close()
            try:
                epic='c'*32
                with self.assertLogs('reawakened.requests',level='INFO') as logs:
                    status,data=request('PUT','gamesession-prod','/gamesession/epiceos',token=jwt(epic))
                    self.assertEqual(status,200);token=data['payload']['sessiontoken']
                    status,account=request('GET','auth-prod','/accountinfo',token=token);self.assertEqual(status,200)
                    aid=account['accountId']
                    status,character=request('PUT','dauntless-prod','/character',{'name':'SyntheticSlayer'},token)
                    self.assertEqual(status,200)
                    status,_=request('POST','dauntless-prod','/inventory/'+character['id']+'/682875',{},token)
                    self.assertEqual(status,200)
                    self.assertEqual(request('POST','store-prod','/reconcile',{'authorization':'private-body-secret'},token)[0],200)
                    self.assertEqual(request('GET','store-prod','/creator',token=token)[0],200)
                    status,info=request('POST','auth-prod','/accountinfo/public',{'accountId':aid},token)
                    self.assertEqual(info['linkedAccounts'][0]['accountId'],epic)
                    status,mapped=request('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':[epic]},token)
                    self.assertEqual(status,200);self.assertEqual(mapped['accountMappings'][epic]['accountId'],aid)
                    for blob in TUNING:self.assertEqual(request('GET','progression-prod','/game_tuning/'+blob,token=token)[0],200)
                    self.assertEqual(request('POST','mm2-prod','/candidate/player/register',{},token)[0],200)
                    status,city=request('POST','mm2-prod','/candidate/join',{
                        'playerId':aid,'gameMode':'CITY','buildId':'682875_2.1.1_shipping'},token)
                    self.assertEqual((status,city['status']),(200,'MATCHING'));self.assertNotIn('serverInfo',city)
                    self.assertEqual(request('GET','progression-prod','/game_tuning/private-blob-secret',token=token)[0],404)
                output='\n'.join(logs.output)
                for secret in (token,epic,aid,character['id'],'private-body-secret','private-blob-secret'):
                    self.assertNotIn(secret,output)
            finally:
                server.shutdown();server.server_close();thread.join(6);db.close()
