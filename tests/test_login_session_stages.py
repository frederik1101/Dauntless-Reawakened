# SPDX-License-Identifier: AGPL-3.0-only
"""Only synthetic value-free traces are used."""
import json
import unittest
from tools.login_session_stages import summarize_sessions


def entry(session, method, route, status=200, character_response=None, secret=None):
    record={'method':method,'route':route,'status':status,
            'authentication':{'input':'valid_local_session','session_alias':session,
                              'account_alias': 'f'*16}}
    if character_response is not None:
        record['character_response']=character_response
    if secret:
        record['token']=secret
    return record


class SessionStagesTests(unittest.TestCase):
    def test_two_interleaved_sessions_do_not_count_each_others_post_character(self):
        one,two='1'*16,'2'*16
        records=[entry(one,'GET','character',character_response={'character_count':1}),
                 entry(two,'GET','character',character_response={'character_count':0}),
                 entry(one,'POST','ported-inventory-migration-none'),
                 entry(two,'PUT','character',character_response={'shape':'object[id:string,name:string]'}),
                 entry(one,'POST','ported-migration-trigger'),
                 entry(two,'GET','character',character_response={'character_count':1})]
        result=summarize_sessions(records)
        self.assertEqual(result['authenticated_session_count'],2)
        self.assertEqual([x['stage'] for x in result['session_results']],
                         ['post_character_request','character_loaded'])
        self.assertEqual(result['session_results'][0]['post_character_200_written'],2)
        self.assertEqual(result['session_results'][1]['post_character_200_written'],0)
        self.assertEqual(result['session_results'][0]['post_character_categories'],
                         ['inventory_migration','migration_trigger'])

    def test_unknown_404_after_loaded_is_not_progress_or_proof_of_failure(self):
        result=summarize_sessions([entry('1'*16,'GET','character',character_response={'character_count':1}),
                                  entry('1'*16,'POST','unknown',404)])
        self.assertEqual(result['session_results'][0]['stage'],'character_loaded')
        self.assertEqual(result['session_results'][0]['first_http_failure_after_loaded'],
                         {'status':404,'route_family':'other'})

    def test_session_alias_and_secret_are_not_returned(self):
        r=summarize_sessions([entry('a'*16,'GET','character',character_response={'character_count':1},
                                    secret='PRIVATE-TOKEN')])
        serialized=json.dumps(r)
        self.assertNotIn('aaaaaaaaaaaaaaaa',serialized)
        self.assertNotIn('PRIVATE-TOKEN',serialized)
        self.assertNotIn('ffffffffffffffff',serialized)

    def test_invalid_or_missing_alias_never_fabricates_group(self):
        bad={'method':'GET','route':'character','status':200,
             'authentication':{'input':'valid_local_session','session_alias':'PRIVATE'}}
        no=summarize_sessions([bad])
        self.assertEqual(no['authenticated_session_count'],0)
        self.assertEqual(no['character_records_without_session_alias'],1)

    def test_non_socket_confirmed_not_supplied_and_login_without_character(self):
        r=summarize_sessions([entry('0'*16,'GET','accountinfo')])
        self.assertEqual(r['session_results'][0]['stage'],'session_without_character')
        with self.assertRaises(ValueError):
            summarize_sessions([{}]*4097)

    def test_bounded_distinct_sessions_and_no_alias_leak(self):
        sessions=[entry(f'{i:016x}','GET','character',character_response={'character_count':1}) for i in range(18)]
        r=summarize_sessions(sessions)
        self.assertEqual(r['authenticated_session_count'],16)
        self.assertEqual(len(r['session_results']),16)
        self.assertTrue(r['truncated_session_count'])

    def test_character_failure_after_loaded_is_disclosed_as_fixed_family(self):
        r=summarize_sessions([entry('9'*16,'GET','character',character_response={'character_count':1}),
                              entry('9'*16,'POST','character',status=409)])
        self.assertEqual(r['session_results'][0]['first_http_failure_after_loaded'],
                         {'status':409,'route_family':'character'})
        self.assertEqual(r['session_results'][0]['stage'],'character_loaded')

if __name__=='__main__': unittest.main()
