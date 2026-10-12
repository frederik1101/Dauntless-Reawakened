"""Synthetic typed identity tests. No real Epic token, account or game involved."""
import base64
import http.client
import io
import json
import logging
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from backend.application import Application
from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.post_login_contracts import mapping_response, public_account_response, REVISION
from backend.protocol_trace import response_details
from backend.research_identity import ResearchIdentity, parse_research_identity, same_identity
from backend.server import make_server, tls_context
from tools.client_trace import ClientTrace, classify_line
from tools.local_tls import generate

PUID = 'a1' * 16
EPIC = 'b2' * 16
OTHER = 'c3' * 16


def token(claims):
    raw = claims if isinstance(claims, bytes) else json.dumps(claims).encode()
    return 'e30.' + base64.urlsafe_b64encode(raw).decode().rstrip('=') + '.c3ludGhldGlj'


def connect():
    return token({'sub': PUID, 'act': {'eat': 'epicgames', 'eaid': EPIC}})


class IdentityParserTests(unittest.TestCase):
    def test_connect_actor_is_separate_from_stable_subject(self):
        result = parse_research_identity(connect())
        self.assertEqual((result.subject, result.epic_id), (PUID, EPIC))
        self.assertEqual(result.kind, 'connect_epic_actor')
        self.assertFalse(result.summary()['verified'])
        self.assertTrue(result.summary()['epic_differs_from_subject'])

    def test_no_actor_preserves_legacy_fallback_explicitly_unclassified(self):
        result = parse_research_identity(token({'sub': 'OldSubject'}))
        self.assertEqual((result.subject, result.epic_id, result.kind),
                         ('OldSubject', 'OldSubject', 'legacy_subject'))

    def test_auth_shape_does_not_mean_signature_verified(self):
        result = parse_research_identity(token({'sub': EPIC, 'iss': 'https://api.epicgames.dev/epic/id/v1'}))
        self.assertEqual(result.kind, 'auth_subject')
        self.assertFalse(result.summary()['verified'])

    def test_host_suffix_or_userinfo_is_not_auth_shape(self):
        for issuer in ('https://api.epicgames.dev.evil/epic/id/v1',
                       'https://api.epicgames.dev@evil/epic/id/v1'):
            self.assertEqual(parse_research_identity(token({'sub': EPIC, 'iss':issuer})).kind,'legacy_subject')

    def test_non_epic_actor_never_maps_puid_as_epic(self):
        result = parse_research_identity(token({'sub':PUID,'act':{'eat':'steam','eaid':EPIC}}))
        self.assertIsNone(result.epic_id)
        self.assertEqual(result.kind, 'connect_other_actor')

    def test_unusable_actor_never_falls_back(self):
        for actor in (None, [], 'private', {'eat':'epicgames'},
                      {'eat':'epicgames','eaid':None}, {'eat':'epicgames','eaid':'a b'}):
            with self.subTest(type=type(actor).__name__):
                self.assertIsNone(parse_research_identity(token({'sub':PUID,'act':actor})).epic_id)

    def test_unknown_claim_is_not_used_as_binding(self):
        result = parse_research_identity(token({'sub':PUID,'epic_account_id':OTHER,'eaid':OTHER}))
        self.assertEqual(result.epic_id,PUID)

    def test_repr_and_summary_never_disclose_ids(self):
        result=parse_research_identity(connect())
        for rendered in (repr(result),json.dumps(result.summary())):
            self.assertNotIn(PUID,rendered);self.assertNotIn(EPIC,rendered)

    def test_duplicate_claims_are_rejected(self):
        for raw in (b'{"sub":"a","sub":"b"}',
                    b'{"sub":"a","act":{"eat":"epicgames","eaid":"a","eaid":"b"}}'):
            with self.assertRaises(ValueError):parse_research_identity(token(raw))

    def test_invalid_and_oversized_inputs_rejected_without_echo(self):
        inputs=[None, True, 3, 'PRIVATE-SECRET', 'a'*20000,
                token([]),token({'sub':None}),token({'sub':'a b'}),
                token(b'{"sub":"a","value":NaN}'),token(b'{'*2000)]
        for value in inputs:
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(ValueError) as caught:parse_research_identity(value)
                self.assertNotIn('PRIVATE',str(caught.exception))

    def test_opaque_case_sensitive_hex_case_insensitive(self):
        self.assertTrue(same_identity(EPIC,EPIC.upper()))
        self.assertFalse(same_identity('AbcIdentity','abcidentity'))
        self.assertFalse(same_identity(EPIC,' '+EPIC))
        self.assertFalse(same_identity(EPIC,PUID))


class IdentityHandlerTests(unittest.TestCase):
    def setUp(self):
        self.db=Database(':memory:');self.addCleanup(self.db.close)
        self.app=PostLoginApplication(self.db,allow_unverified_eos_sub=True)

    def exchange(self, value=None, **kwargs):
        return self.app.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
            {'Authorization':'Bearer '+(connect() if value is None else value)},secure=kwargs.get('secure',True))

    def login(self):
        result=self.exchange();self.assertEqual(result.status,200)
        return self.app.sessions.resolve(result.payload['payload']['sessiontoken'])

    def test_old_database_key_and_character_survive_binding_correction(self):
        original=self.db.account('eos-research:'+PUID)['accountId']
        char=self.db.create(original,'Synthetic','{}')
        self.db.save(original,char['id'],'{"RecentPlayers":"{}"}',6)
        session=self.login()
        self.assertEqual(session.account_id,original)
        self.assertEqual(session.linked_epic_id,EPIC)
        self.assertEqual(self.db.get(original)[0]['updateVersion'],6)
        self.assertEqual(len(self.db.get(original)),1)

    def test_case_variant_maps_only_requested_own_id(self):
        session=self.login()
        request=json.dumps({'srcAccountType':'epic','ids':[EPIC.upper(),OTHER]}).encode()
        reply=self.app.handle('POST','auth-prod.steelyard.ca','/account/mapping',
              {'Authorization':'Bearer '+session.session_token},request,secure=True)
        self.assertEqual(reply.status,200)
        self.assertEqual(reply.payload['accountMappings'],
                         {EPIC.upper():{'accountId':session.account_id,'accountType':'phoenix'}})

    def test_puid_does_not_alias_epic_and_reverse_is_consistent(self):
        session=self.login()
        self.assertEqual(mapping_response(json.dumps({'srcAccountType':'epic','ids':[PUID]}).encode(),
                                         session.account_id,session.linked_epic_id)['accountMappings'],{})
        backward=mapping_response(json.dumps({'srcAccountType':'phoenix','ids':[session.account_id]}).encode(),session.account_id,session.linked_epic_id)
        self.assertEqual(backward['accountMappings'][session.account_id]['accountId'],EPIC)
        info=public_account_response(json.dumps({'accountId':session.account_id}).encode(),session.account_id,session.linked_epic_id)
        self.assertEqual(info['linkedAccounts'][0]['accountId'],EPIC)

    def test_mapping_cannot_create_or_change_binding(self):
        session=self.login();before=self.db._db.total_changes
        for asked in (OTHER,PUID):
            mapping_response(json.dumps({'srcAccountType':'epic','ids':[asked]}).encode(),session.account_id,session.linked_epic_id)
        self.assertEqual(self.db._db.total_changes,before)
        self.assertEqual(session.linked_epic_id,EPIC)

    def test_session_response_keeps_local_secrets_separate(self):
        result=self.exchange();p=result.payload['payload']
        self.assertIsNone(p['error_code'])
        self.assertEqual(p['sessiontoken'],p['sessionToken'])
        self.assertNotEqual(p['sessiontoken'],connect())
        self.assertNotEqual(p['sessionid'],p['sessiontoken'])

    def test_disabled_and_plaintext_exchange_stay_closed(self):
        self.assertEqual(self.exchange(secure=False).status,503)
        self.app.allow_unverified_eos_sub=False
        self.assertEqual(self.exchange().status,503)

    def test_browser_rejected_before_exchange(self):
        result=self.app.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
            {'Authorization':'Bearer '+connect(),'Origin':'null'},secure=True)
        self.assertEqual(result.status,403)

    def test_missing_or_bad_token_has_no_db_write(self):
        before=self.db._db.total_changes
        self.assertEqual(self.exchange('not.a.token').status,400)
        self.assertEqual(self.db._db.total_changes,before)

    def test_token_rotation_keeps_binding_and_account(self):
        first=self.login();second=self.login()
        self.assertNotEqual(first.session_token,second.session_token)
        self.assertEqual(first.account_id,second.account_id)
        self.assertEqual(first.research_identity,second.research_identity)

    def test_metadata_classifies_mismatch_without_values(self):
        session=self.login();body=json.dumps({'srcAccountType':'epic','ids':[PUID]}).encode()
        payload=mapping_response(body,session.account_id,session.linked_epic_id)
        d=response_details('post-login-account-mapping',payload,body,session=session)['mapping']
        self.assertEqual(d['source'],'epic')
        self.assertEqual(d['matches_epic_binding'],0)
        self.assertEqual(d['matches_exchange_subject'],1)
        for value in (PUID,EPIC,session.account_id,session.session_token):
            self.assertNotIn(value,json.dumps(d))

    def test_revocation_blocks_mapping(self):
        session=self.login();self.app.sessions.revoke(session.session_token)
        r=self.app.handle('POST','auth-prod.steelyard.ca','/account/mapping',
            {'Authorization':'Bearer '+session.session_token},b'{}',secure=True)
        self.assertEqual(r.status,401)

    def test_base_application_has_not_adopted_new_contract(self):
        base=Application(self.db,allow_unverified_eos_sub=True)
        result=base.handle('PUT','gamesession-prod.steelyard.ca','/gamesession/epiceos',
            {'Authorization':'Bearer '+connect()},secure=True)
        self.assertNotIn('sessionToken',result.payload['payload'])


class NewClientMarkerTests(unittest.TestCase):
    def test_mapping_miss_is_not_hidden_by_generic_login_marker(self):
        line=b'LogOnline: FOnlineUserPhoenix::QueryExternalIdMappings - No Valid mappings came back PRIVATE_ID'
        self.assertEqual(classify_line(line),('identity_mapping_empty',))

    def test_cancellation_requires_explicit_error_reason(self):
        self.assertIn('login_cancelled_explicit',classify_line(b'LogOnline: LoginOperation Failed - Error = Canceled'))
        self.assertNotIn('login_cancelled_explicit',classify_line(b'LogOnline: LoginOperation Failed - Error = Other token=UserCanceled'))
        self.assertNotIn('login_cancelled_explicit',classify_line(b'LogOnline: LoginOperation Failed - Error = CanceledSECRET'))

    def test_logs_remain_private(self):
        trace=ClientTrace()
        trace.feed(b'LogOnline: FArchonAdditionalLoginSteps::CheckCharacterCompatibility: Unable to retrieve user account. PRIVATE\n')
        self.assertIn('login_user_account_unavailable',trace.report()['marker_counts'])
        self.assertNotIn('PRIVATE',json.dumps(trace.report()))


class IdentityTlsTests(unittest.TestCase):
    def test_two_sessions_actual_tls_with_persistent_database_and_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cert=generate(root/'tls')
            db=Database(root/'players.sqlite3')
            app=PostLoginApplication(db,allow_unverified_eos_sub=True)
            server=make_server(app,'127.0.0.1',0,tls_context(cert/'server.pem',cert/'server-key.pem'),diagnostic=True)
            worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01});worker.start()
            context=ssl.create_default_context(cafile=str(cert/'ca.pem'))
            logs=io.StringIO();handler=logging.StreamHandler(logs)
            logger=logging.getLogger('reawakened.requests');old=logger.level;logger.setLevel(logging.INFO);logger.addHandler(handler)
            def call(method,service,path,body=None,session=None):
                c=http.client.HTTPSConnection('127.0.0.1',server.server_port,context=context,timeout=5)
                headers={'Host':service+'.steelyard.ca'}
                if session:headers['Authorization']='Bearer '+session
                try:
                    c.request(method,path,body=None if body is None else json.dumps(body),headers=headers)
                    reply=c.getresponse();data=reply.read()
                    self.assertEqual(reply.status,200)
                    return json.loads(data)
                finally:c.close()
            try:
                account=db.account('eos-research:'+PUID)['accountId']
                character=db.create(account,'Synthetic','{}')
                for version in (1,2):
                    session=call('PUT','gamesession-prod','/gamesession/epiceos',session=connect())['payload']['sessiontoken']
                    mapped=call('POST','auth-prod','/account/mapping',{'srcAccountType':'epic','ids':[EPIC]},session)
                    self.assertEqual(mapped['accountMappings'][EPIC]['accountId'],account)
                    rows=call('GET','dauntless-prod','/character',session=session)
                    self.assertEqual(rows[0]['updateVersion'],version-1)
                    saved=call('POST','dauntless-prod','/character',{'characterId':character['id'],'updateVersion':version,'data':'{}'},session)
                    self.assertEqual(saved,{'data':'{}'})
            finally:
                server.shutdown();server.server_close();worker.join(5)
                logger.removeHandler(handler);logger.setLevel(old);handler.close();db.close()
            output=logs.getvalue()
            for secret in (PUID,EPIC,connect(),session,account,character['id']):self.assertNotIn(secret,output)
            self.assertIn('connect_epic_actor',output)
            self.assertIn('written_to_socket',output)
            db=Database(root/'players.sqlite3')
            try:self.assertEqual(db.get(account)[0]['updateVersion'],2)
            finally:db.close()

if __name__=='__main__':unittest.main()
