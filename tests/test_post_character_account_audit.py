# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic regression for the 12 Oct empty -> create -> version-0 trace."""
import base64
import http.client
import json
import ssl
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.character_profile import PROFILE_VARIANTS, ProfileDatabase
from backend.database import Database
from backend.post_login import PostLoginApplication
from backend.server import make_server, tls_context
from tools.local_tls import generate

SUBJECT = 'PRIVATE-SYNTHETIC-SUBJECT'
EPIC_ID = 'PRIVATE-SYNTHETIC-EPIC-ID'


def exchange(app):
    payload = json.dumps({'sub': SUBJECT, 'act': {'eat': 'epicgames', 'eaid': EPIC_ID}}).encode()
    jwt = 'e30.' + base64.urlsafe_b64encode(payload).decode().rstrip('=') + '.c3ludGhldGlj'
    reply = app.handle('PUT', 'gamesession-prod.steelyard.ca', '/gamesession/epiceos',
        {'Authorization': 'Bearer ' + jwt}, secure=True)
    return reply, {'Authorization': 'Bearer ' + reply.payload['payload']['sessiontoken']}, jwt


def character(app, method, auth, payload=None):
    body = b'' if payload is None else json.dumps(payload).encode()
    return app.handle(method, 'dauntless-prod.steelyard.ca', '/character', auth, body, secure=True)


class PostCharacterAuditTests(unittest.TestCase):
    def test_all_variants_empty_create_read_then_second_exchange(self):
        for variant, fields in PROFILE_VARIANTS.items():
            with self.subTest(variant=variant):
                db = ProfileDatabase(':memory:', variant=variant)
                try:
                    app = PostLoginApplication(db, allow_unverified_eos_sub=True)
                    first, auth, jwt = exchange(app)
                    self.assertEqual(first.internal_diagnostics, {
                        'account_preexisting': False, 'owned_characters_before_exchange': 0})
                    self.assertEqual(character(app, 'GET', auth).payload, [])
                    created = character(app, 'PUT', auth, {'name': 'Synthetic'})
                    self.assertEqual(created.status, 200)
                    record = character(app, 'GET', auth).payload[0]
                    self.assertEqual(record['updateVersion'], 0)
                    self.assertEqual(record['id'], created.payload['id'])
                    self.assertEqual(set(json.loads(record['data'])),
                                     {'PlayerAccountProgressStep'} | fields)
                    self.assertNotIn('account_preexisting', first.body().decode())
                    self.assertNotIn(jwt, first.body().decode())
                    second, _, _ = exchange(app)
                    self.assertEqual(second.internal_diagnostics, {
                        'account_preexisting': True, 'owned_characters_before_exchange': 1})
                finally:
                    db.close()

    def test_standard_database_keeps_one_field_seed(self):
        db = Database(':memory:')
        try:
            app = PostLoginApplication(db, allow_unverified_eos_sub=True)
            first, auth, _ = exchange(app)
            self.assertFalse(first.internal_diagnostics['account_preexisting'])
            character(app, 'PUT', auth, {'name': 'Synthetic'})
            record = character(app, 'GET', auth).payload[0]
            self.assertEqual(record['updateVersion'], 0)
            self.assertEqual(json.loads(record['data']),
                             {'PlayerAccountProgressStep': 'EnteredRamsgate'})
            second, _, _ = exchange(app)
            self.assertEqual(second.internal_diagnostics['owned_characters_before_exchange'], 1)
        finally:
            db.close()

    def test_verified_tls_log_reports_counts_and_variant_without_identity(self):
        db = ProfileDatabase(':memory:', variant='without-appearance')
        with tempfile.TemporaryDirectory() as home:
            tls = generate(Path(home) / 'tls')
            app = PostLoginApplication(db, allow_unverified_eos_sub=True)
            srv = make_server(app, '127.0.0.1', 0,
                tls_context(tls/'server.pem', tls/'server-key.pem'), diagnostic=True)
            worker = threading.Thread(target=srv.serve_forever,
                                      kwargs={'poll_interval': .01}, daemon=True)
            worker.start()
            try:
                with self.assertLogs('reawakened.requests', level='INFO') as logs:
                    payload = json.dumps({'sub': SUBJECT,
                        'act': {'eat': 'epicgames', 'eaid': EPIC_ID}}).encode()
                    jwt = 'e30.' + base64.urlsafe_b64encode(payload).decode().rstrip('=') + '.c3ludGhldGlj'
                    client = http.client.HTTPSConnection('127.0.0.1', srv.server_port, timeout=5,
                        context=ssl.create_default_context(cafile=str(tls/'ca.pem')))
                    client.request('PUT', '/gamesession/epiceos', headers={
                        'Host':'gamesession-prod.steelyard.ca', 'Authorization':'Bearer '+jwt})
                    answer = client.getresponse()
                    self.assertEqual(answer.status, 200)
                    wire = json.loads(answer.read())
                    client.close()
                traces = [json.loads(line.split('PROTOCOL_TRACE ', 1)[1])
                          for line in logs.output if 'PROTOCOL_TRACE {' in line]
                self.assertEqual(len(traces), 1)
                self.assertEqual(traces[0]['local_account_at_exchange'],
                    {'preexisting': False, 'owned_characters': 0})
                self.assertEqual(traces[0]['profile_selection'],
                    {'mode': 'isolated_profile', 'variant': 'without-appearance'})
                self.assertNotIn('local_account_at_exchange', json.dumps(wire))
                for secret in (SUBJECT, EPIC_ID, jwt, wire['payload']['sessiontoken']):
                    self.assertNotIn(secret, '\n'.join(logs.output))
            finally:
                srv.shutdown(); srv.server_close(); worker.join(5); db.close()

    def test_default_profile_stays_full_but_warning_is_unmistakable(self):
        from tools import standalone_server
        import contextlib
        import io
        calls = []
        with patch.object(standalone_server, 'serve', side_effect=lambda *a, **k: calls.append(k)), \
             patch.object(standalone_server, 'default_home', return_value=Path('/synthetic')):
            for args, variant, warned in (
                (['server','--mystic-profile'], 'full', True),
                (['server','--mystic-profile','--profile-variant','without-appearance'],
                 'without-appearance', False),
                (['server'], 'full', False)):
                with patch('sys.argv',args), io.StringIO() as out, contextlib.redirect_stdout(out):
                    self.assertEqual(standalone_server.main(), 0)
                    self.assertEqual('WITHOUT --profile-variant' in out.getvalue(), warned)
                self.assertEqual(calls[-1]['profile_variant'], variant)

if __name__ == '__main__':
    unittest.main()
