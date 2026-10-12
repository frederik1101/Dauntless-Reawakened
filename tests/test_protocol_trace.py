"""Detailed metadata and verified-TLS transport traces with synthetic identities."""
import http.client
import json
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.post_login_contracts import tuning_response, TUNING, REVISION
from backend.protocol_trace import authentication, character_summary, data_summary, identity_alias, response_details
from backend.server import make_server, tls_context
from tools.local_tls import generate
from tools.map_preview_support import REVISION as LAUNCH_REVISION


class ProtocolTraceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(':memory:'); self.addCleanup(self.db.close)
        self.app = PostLoginApplication(self.db)
        self.account = self.db.account('private-subject')['accountId']
        self.session = self.app.sessions.create(self.account, linked_epic_id='PRIVATE-EPIC')
        self.headers = {'Authorization': 'Bearer ' + self.session.session_token}

    def test_public_endpoint_does_not_claim_invalid_session(self):
        self.assertEqual(authentication(self.app, {}, 'health')['input'], 'public_no_local_session_required')

    def test_exchange_is_not_checked_as_local_token(self):
        self.assertEqual(authentication(self.app, {'Authorization':'Bearer PRIVATE-EXTERNAL'},
                                        'epiceos-session-research')['input'],
                         'external_exchange_not_a_local_token')

    def test_missing_vs_unrecognised_vs_valid(self):
        self.assertEqual(authentication(self.app, {}, 'character')['input'], 'missing_bearer')
        self.assertEqual(authentication(self.app, {'Authorization':'invalid'}, 'character')['input'], 'malformed_bearer')
        self.assertEqual(authentication(self.app, {'Authorization':'Bearer unknown'}, 'character')['input'], 'unrecognised_local_bearer')
        a = authentication(self.app, self.headers, 'character')
        self.assertEqual(a['input'], 'valid_local_session')
        self.assertNotIn(self.session.session_token, str(a))
        self.assertNotIn(self.account, str(a))
        self.assertNotIn('PRIVATE-EPIC', str(a))

    def test_rotated_sessions_have_same_account_alias(self):
        second = self.app.sessions.create(self.account)
        one = authentication(self.app, self.headers, 'character')
        two = authentication(self.app, {'Authorization':'Bearer '+second.session_token}, 'character')
        self.assertEqual(one['account_alias'], two['account_alias'])
        self.assertNotEqual(one['session_alias'], two['session_alias'])

    def test_character_summary_records_fields_and_version_not_values(self):
        payload = [{'id':'PRIVATE-CHARACTER','name':'PRIVATE-NAME','updateVersion':7,
                    'data': json.dumps({'PlayerAccountProgressStep':'EnteredRamsgate',
                                        'PRIVATE-FIELD':'PRIVATE-VALUE',
                                        'AppearanceData':'{"PRIVATE-ASSET":"PRIVATE-PATH"}'})}]
        result = character_summary(payload)
        row = result['characters'][0]
        self.assertEqual(row['version'], 7)
        self.assertEqual(row['data']['progress_state'], 'EnteredRamsgate')
        self.assertIs(row['data']['all_values_strings'], True)
        self.assertEqual(row['data']['unknown_field_count'], 1)
        self.assertEqual(row['data']['nested_data']['AppearanceData']['decoded_type'], 'object')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_non_string_inner_value_is_identified(self):
        result = data_summary('{"PlayerAccountProgressStep": true}')
        self.assertIs(result['all_values_strings'], False)
        self.assertEqual(result['progress_state'], 'unrecognised_or_missing')

    def test_data_wrong_top_type_and_invalid_json(self):
        self.assertEqual(data_summary('[]')['decode'], 'not_object')
        self.assertEqual(data_summary('x')['decode'], 'invalid_json')
        self.assertEqual(data_summary({})['wire_type'], 'object')

    def test_unknown_progress_is_not_copied(self):
        self.assertNotIn('PRIVATE', str(data_summary('{"PlayerAccountProgressStep":"PRIVATE"}')))

    def test_tutorial_presence_detected_without_changing_data(self):
        data = '{"HasFinishedTutorial":"false"}'
        self.assertIs(data_summary(data)['legacy_tutorial_key_present'], True)
        self.assertEqual(data, '{"HasFinishedTutorial":"false"}')

    def test_character_samples_are_bounded(self):
        result = character_summary([{'id':'x','updateVersion':0,'data':'{}'}]*100)
        self.assertEqual(result['character_count'],100)
        self.assertEqual(len(result['characters']),8)

    def test_mapping_failure_is_visible_not_disclosed(self):
        payload = {'accountMappings':{}}
        request = b'{"srcAccountType":"epic","ids":["PRIVATE-ID"]}'
        result = response_details('post-login-account-mapping',payload,request)
        self.assertEqual(result['mapping'], {'requested_count':1,'returned_count':0,'all_requested_ids_mapped':False,'source':'epic'})
        self.assertNotIn('PRIVATE',str(result))

    def test_character_save_echo_check_and_versions(self):
        request = {'characterId':'PRIVATE','updateVersion':9,'data':'{"PRIVATE":"SECRET"}'}
        response = {'data':request['data']}
        result = response_details('character',response,json.dumps(request).encode())
        self.assertIs(result['saved_data_matches_request'],True)
        self.assertEqual(result['character_request']['version'],9)
        self.assertNotIn('PRIVATE',str(result));self.assertNotIn('SECRET',str(result))

    def test_register_empty_ack_is_explicit(self):
        self.assertEqual(response_details('ramsgate-register',{},b'{}')['register_reply'], 'empty_object_ack')

    def test_tuning_string_code_with_object_payload(self):
        for blob in TUNING:
            result = tuning_response(blob)
            self.assertEqual(result['code'], 'OK')
            self.assertIsInstance(result['payload'],dict)
            self.assertEqual(result['payload'], TUNING[blob])
        self.assertEqual(REVISION, LAUNCH_REVISION)


class ProtocolTraceTlsTests(unittest.TestCase):
    def test_prepared_and_written_events_share_request_id_and_keep_auth_private(self):
        db=Database(':memory:')
        app=PostLoginApplication(db)
        account=db.account('PRIVATE-SUBJECT')['accountId']
        session=app.sessions.create(account)
        char=db.create(account,'PRIVATE-NAME','{"PlayerAccountProgressStep":"EnteredRamsgate"}')
        with tempfile.TemporaryDirectory() as tmp:
            tls=generate(Path(tmp)/'tls')
            server=make_server(app,'127.0.0.1',0,tls_context(tls/'server.pem',tls/'server-key.pem'),diagnostic=True)
            worker=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.01},daemon=True)
            worker.start()
            try:
                with self.assertLogs('reawakened.requests',level='INFO') as captured:
                    client=http.client.HTTPSConnection('127.0.0.1',server.server_port,timeout=5,
                        context=ssl.create_default_context(cafile=str(tls/'ca.pem')))
                    client.request('GET','/character',headers={'Host':'dauntless-prod.steelyard.ca',
                        'Authorization':'Bearer '+session.session_token})
                    response=client.getresponse()
                    self.assertEqual(response.status,200)
                    self.assertEqual(json.loads(response.read())[0]['id'],char['id'])
                    client.close()
                    server.shutdown();server.server_close();worker.join(5)
                text='\n'.join(captured.output)
                prepared=[line.split('PROTOCOL_TRACE ',1)[1] for line in captured.output if 'PROTOCOL_TRACE {' in line]
                self.assertEqual(len(prepared),1)
                record=json.loads(prepared[0])
                self.assertIn('request_id='+record['request_id']+' delivery=written_to_socket',text)
                self.assertEqual(record['authentication']['input'],'valid_local_session')
                for private in ('PRIVATE-SUBJECT','PRIVATE-NAME',account,char['id'],session.session_token):
                    self.assertNotIn(private,text)
            finally:
                if worker.is_alive():server.shutdown()
                server.server_close();worker.join(5);db.close()

if __name__ == '__main__':unittest.main()
