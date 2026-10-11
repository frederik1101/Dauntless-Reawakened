import unittest
from unittest.mock import Mock
from tools.map_preview_support import login_test_duration, watch


class TimingTests(unittest.TestCase):
    def test_mode_specific_defaults(self):
        self.assertEqual(login_test_duration(None,True),600)
        self.assertEqual(login_test_duration(None,False),120)
    def test_direct_preview_cannot_take_long_budget(self):
        with self.assertRaises(ValueError):login_test_duration(600,False)
    def test_budget_validation(self):
        for v in (True,29,601,'600'):
            with self.subTest(value=v),self.assertRaises(ValueError):login_test_duration(v,True)
    def test_normal_login_not_terminated_at_old_180_limit(self):
        now=[0.0];process=Mock();process.poll.return_value=None
        r=watch(process,600,max_seconds=600,clock=lambda:now[0],
            sleep=lambda d:now.__setitem__(0,now[0]+d),measure=lambda _:1024)
        self.assertEqual(r['termination'],'time_limit');self.assertEqual(r['elapsed_seconds'],600)
    def test_longer_time_does_not_raise_memory_budget(self):
        p=Mock();p.poll.return_value=None
        r=watch(p,600,max_seconds=600,measure=lambda _:5000*1024*1024)
        self.assertEqual(r['termination'],'memory_limit')


