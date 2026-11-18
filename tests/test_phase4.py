import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from vcse.phase4 import get_cases, run_suite, evaluate_case, ORIGIN
from vcse.discovery import OpenAICompatiblePlanner

class FakePlanner:
    """Test double: deterministic selection over observed selectors; NOT model inference."""
    def propose(self, goal, observation, failed, home):
        failed_targets={x.get('target') for x in failed}
        for t in observation.get('tables',[]):
            if t.get('selector') not in failed_targets:
                return {'action':'extract_table','selector':t['selector'],'reason':'Extract observed table'}
        links=[x for x in observation.get('links',[]) if x.get('selector') not in failed_targets]
        if links:return {'action':'click','selector':links[0]['selector'],'reason':'Follow observed link'}
        return {'action':'stop','reason':'No more actions'}

class Phase4Tests(unittest.TestCase):
    def test_splits_are_distinct(self):
        c=get_cases()
        self.assertEqual(len(c),6)
        self.assertEqual(len({x.case_id for x in c}),6)
        self.assertEqual(sum(x.split=='heldout' for x in c),4)
    def test_heldout_mock_planner_end_to_end(self):
        # End-to-end Playwright + proposed actions, no external LLM request.
        r=run_suite('mock','heldout',max_attempts=5,planner=FakePlanner())
        self.assertEqual(r['total'],4)
        self.assertEqual(r['verified_successes'],4)
        self.assertFalse(r['actual_language_model_tested'])
    def test_invalid_plan_blocks(self):
        class Bad:
            def propose(self,*args):return {'action':'run_shell','selector':'#anything'}
        r=evaluate_case(get_cases()[0],mode='mock',planner=Bad())
        self.assertEqual(r['status'],'blocked')
        self.assertFalse(r['completed'])
    def test_wrong_table_is_not_verified(self):
        from vcse.phase4 import make_case
        c=make_case('decoy','heldout','Portal', [('preview','/preview','Preview')], '/ledger','true-table',decoy=True)
        r=evaluate_case(c,'mock',planner=FakePlanner(),max_attempts=5)
        self.assertFalse(r['completed'])
        self.assertGreaterEqual(r['failed_actions'],1)
    def test_model_endpoint_requires_https_or_loopback(self):
        with self.assertRaises(ValueError):OpenAICompatiblePlanner('http://example.org/v1/chat/completions','x','key')
    def test_model_response_parser(self):
        p=OpenAICompatiblePlanner('https://models.example/v1/chat/completions','example','test-key')
        response={'choices':[{'message':{'content':'{"action":"click","selector":"#go","reason":"Observed"}'}}]}
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,*args):return BytesIO(__import__('json').dumps(response).encode()).read()
        with patch('vcse.discovery.urlopen',return_value=Reply()) as urlopen:
            proposal=p.propose('read table',{'links':[{'selector':'#go','text':'Records'}]},[],ORIGIN)
            self.assertEqual(proposal['selector'],'#go')
            request=urlopen.call_args.args[0]
            self.assertTrue(request.get_header('Authorization').startswith('Bearer '))

if __name__=='__main__': unittest.main()
