"""Synthetic host offers are tests, never a production fallback destination."""
from dataclasses import replace
import concurrent.futures
import json
import unittest

from backend.ramsgate_matchmaker import (HostAssignment, PlayerBinding, RAMSGATE_MAP,
                                         RamsgateMatchmaker, UnavailableHost, parse_join)


class Clock:
    now = 100.0
    def __call__(self):
        return self.now


class SyntheticHost:
    def __init__(self, clock):
        self.clock = clock
        self.ready = False
        self.alive = True
        self.generation = 'synthetic-generation'
        self.reserve_calls = 0
        self.releases = []
        self.edit = lambda a: a
        self.error = False

    def reserve(self, player, candidate, request):
        self.reserve_calls += 1
        if self.error:
            raise RuntimeError('SECRET-exception')
        if not self.ready:
            return None
        return self.edit(HostAssignment('synthetic-instance', 'synthetic-game-session',
                         self.generation, request.build_id, RAMSGATE_MAP, 8777,
                         self.clock() + 10))

    def refresh(self, assignment, player, candidate):
        return self.edit(replace(assignment, expires_at=self.clock()+10,
                                generation=self.generation))

    def is_live(self, assignment, player, candidate):
        return self.alive

    def release(self, player, candidate):
        self.releases.append(candidate)


class MatchmakerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.host = SyntheticHost(self.clock)
        self.mm = RamsgateMatchmaker(self.host, clock=self.clock, wait_seconds=20)
        self.player = PlayerBinding('synthetic-account', 'synthetic-session', 'synthetic-character')
        self.body = {'buildId': '682875_2.1.1_shipping', 'gameMode': 'CITY',
                     'playerId': self.player.account_id}

    def join(self):
        return self.mm.join(self.player, self.body)

    def test_default_has_no_destination(self):
        mm = RamsgateMatchmaker(clock=self.clock)
        self.assertIsInstance(mm.hosts, UnavailableHost)
        result = mm.join(self.player, self.body)
        self.assertEqual(result['status'], 'MATCHING')
        self.assertNotIn('serverInfo', result)

    def test_waiting_then_synthetic_provider_offer(self):
        first = self.join()
        self.assertEqual(first['status'], 'MATCHING')
        self.host.ready = True
        ready = self.mm.status(self.player)
        self.assertEqual(ready['candidateId'], first['candidateId'])
        self.assertEqual(ready['status'], 'IN_PROGRESS')
        self.assertEqual(ready['gameMode'], 'CITY')
        self.assertIs(ready['isNewMatchmaker'], True)
        self.assertTrue(ready['playerStates'][self.player.account_id]['isReadyToLeaveLobby'])
        self.assertEqual(set(ready['serverInfo']),
                         {'gameSessionId', 'instanceId', 'host', 'port', 'gameArgs'})
        self.assertEqual(ready['serverInfo']['host'], '127.0.0.1')
        self.assertIs(type(ready['serverInfo']['port']), int)
        self.assertNotIn('ticket', ready['serverInfo'])

    def test_no_host_times_out_without_old_destination(self):
        self.join()
        self.clock.now += 20
        result = self.mm.status(self.player)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['statusReason'], 'NO_LOCAL_HOST_READY')
        self.assertNotIn('serverInfo', result)

    def test_repeated_join_is_idempotent(self):
        self.host.ready = True
        first = self.join()
        self.assertEqual(self.join(), first)
        self.assertEqual(self.host.reserve_calls, 1)

    def test_lease_refresh_retains_assignment(self):
        self.host.ready = True
        first = self.join()
        self.clock.now += 9
        self.assertEqual(self.mm.status(self.player)['serverInfo'], first['serverInfo'])
        self.clock.now += 9
        self.assertEqual(self.mm.status(self.player)['status'], 'IN_PROGRESS')

    def test_dead_host_removes_destination(self):
        self.host.ready = True
        self.join()
        self.host.alive = False
        result = self.mm.status(self.player)
        self.assertEqual(result['status'], 'FAILED')
        self.assertNotIn('serverInfo', result)
        self.assertEqual(len(self.host.releases), 1)

    def test_restarted_generation_requires_new_join(self):
        self.host.ready = True
        first = self.join()
        self.host.generation = 'replacement'
        failed = self.mm.status(self.player)
        self.assertEqual(failed['status'], 'FAILED')
        self.assertNotIn('serverInfo', failed)
        self.assertNotEqual(self.join()['candidateId'], first['candidateId'])

    def test_changed_destination_during_refresh_is_rejected(self):
        self.host.ready = True
        self.join()
        self.host.edit = lambda a: replace(a, port=8778)
        self.assertEqual(self.mm.status(self.player)['status'], 'FAILED')

    def test_stale_lease_never_advertised(self):
        self.host.ready = True
        self.host.edit = lambda a: replace(a, expires_at=self.clock())
        self.assertNotIn('serverInfo', self.join())

    def test_invalid_offers_are_never_advertised(self):
        for key, value in [('host','0.0.0.0'), ('host','192.0.2.1'), ('host','localhost'),
                           ('port','8777'), ('port',True), ('port',0), ('port',65536),
                           ('world','/Game/Maps/Other'), ('build_id','wrong'),
                           ('expires_at',float('nan')), ('expires_at',float('inf')),
                           ('expires_at',self.clock()+100), ('generation',''),
                           ('instance_id','name\nSECRET')]:
            with self.subTest(key=key,value=value):
                host = SyntheticHost(self.clock)
                host.ready = True
                host.edit = lambda a,k=key,v=value: replace(a, **{k:v})
                result = RamsgateMatchmaker(host, clock=self.clock).join(self.player,self.body)
                self.assertEqual(result['status'], 'FAILED')
                self.assertNotIn('serverInfo',result)

    def test_non_bool_liveness_is_not_truthy_readiness(self):
        self.host.ready = True
        self.host.alive = 'yes'
        self.assertEqual(self.join()['status'], 'FAILED')

    def test_cancel_is_idempotent_and_revokes_offer(self):
        self.host.ready = True
        self.join()
        self.mm.cancel(self.player)
        self.mm.cancel(self.player)
        result = self.mm.status(self.player)
        self.assertEqual(result['status'], 'CANCELED')
        self.assertNotIn('serverInfo', result)

    def test_cancel_unknown_is_noop(self):
        self.mm.cancel(self.player)
        with self.assertRaises(KeyError):
            self.mm.status(self.player)

    def test_candidate_binding_rejects_other_account_or_character(self):
        self.join()
        for player in (replace(self.player,account_id='other'),
                       replace(self.player,character_id='other')):
            with self.assertRaises(PermissionError):
                self.mm.status(player)
            with self.assertRaises(PermissionError):
                self.mm.cancel(player)

    def test_session_rotation_does_not_reuse_candidate(self):
        first = self.join()
        second = self.mm.join(replace(self.player,session_id='second-session'),self.body)
        self.assertNotEqual(first['candidateId'], second['candidateId'])

    def test_other_player_in_request_is_rejected(self):
        self.body['playerId'] = 'another-player'
        with self.assertRaises(PermissionError):
            self.join()
        self.assertEqual(self.host.reserve_calls, 0)

    def test_other_character_in_request_is_rejected(self):
        self.body['characterId'] = 'another-character'
        with self.assertRaises(PermissionError):
            self.join()

    def test_hunt_and_non_city_not_silently_routed(self):
        for edit in ({'gameMode':'ISLAND'}, {'hunts':['SomeHunt']}):
            with self.assertRaises(NotImplementedError):
                self.mm.join(self.player,{**self.body,**edit})

    def test_optional_privacy_flags_not_required(self):
        self.assertEqual(parse_join(self.body,self.player).game_mode,'CITY')
        for value in (None, 1, 'true', {}):
            with self.assertRaises(ValueError):
                parse_join({**self.body,'isPrivate':value},self.player)

    def test_unsafe_build_values_are_rejected(self):
        for value in ('', 'a/b', 'a\r\nSECRET', 'x'*129, None, 682875):
            with self.assertRaises(ValueError):
                parse_join({**self.body,'buildId':value},self.player)

    def test_provider_errors_are_fixed_labels(self):
        self.host.error = True
        result = self.join()
        self.assertEqual(result['status'], 'FAILED')
        self.assertNotIn('SECRET', json.dumps(result))

    def test_user_game_args_not_echoed_or_forwarded(self):
        self.body['gameArgs'] = 'SECRET?ticket=SECRET'
        self.body['loadout'] = {'secret':'PRIVATE'}
        self.host.ready = True
        result = self.join()
        self.assertEqual(result['serverInfo']['gameArgs'], '')
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertNotIn('PRIVATE',json.dumps(result))

    def test_capacity_and_retention_are_bounded(self):
        mm = RamsgateMatchmaker(clock=self.clock,limit=1,wait_seconds=2)
        mm.join(self.player,self.body)
        second = replace(self.player,session_id='second')
        with self.assertRaises(OverflowError):
            mm.join(second,self.body)
        self.clock.now += 32
        self.assertEqual(mm.join(second,self.body)['status'],'MATCHING')

    def test_invalid_configuration_rejected(self):
        for kwargs in ({'limit':True},{'limit':0},{'limit':1025},{'wait_seconds':0},
                       {'wait_seconds':float('nan')},{'wait_seconds':601}):
            with self.assertRaises(ValueError):
                RamsgateMatchmaker(**kwargs)

    def test_parallel_retries_create_one_reservation(self):
        self.host.ready = True
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _:self.join(),range(25)))
        self.assertEqual(len({r['candidateId'] for r in results}),1)
        self.assertEqual(self.host.reserve_calls,1)

    def test_private_bindings_not_in_default_repr(self):
        self.assertNotIn('synthetic-account',repr(self.player))
        self.host.ready = True
        self.join()
        self.assertNotIn('synthetic-game-session',repr(next(iter(self.mm._candidates.values()))))

if __name__ == '__main__':
    unittest.main()
