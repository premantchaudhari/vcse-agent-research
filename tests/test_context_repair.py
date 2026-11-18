"""Phase 4.4: bounded corrective replanning after a premature extraction proposal."""
import unittest
from vcse.phase4 import evaluate_case, get_cases


class ContextRepairTests(unittest.TestCase):
    def test_premature_table_extraction_is_repaired_and_verified(self):
        class Premature:
            repairs = 0
            def propose(self, goal, observation, failed, home):
                if observation.get('tables'):
                    return {'action': 'extract_table', 'selector': observation['tables'][0]['selector'], 'reason':'Read invoices'}
                return {'action': 'extract_table', 'selector': '#made-up-table', 'reason': 'Too early'}
            def repair(self, goal, observation, failed, home, bad_proposal):
                self.repairs += 1
                assert bad_proposal['_vcse_error'] == 'table_not_observed'
                assert not observation['tables']
                return {'action': 'click', 'selector': observation['links'][0]['selector'], 'reason': 'Navigate first'}
        planner = Premature()
        res = evaluate_case(get_cases()[0], mode='mock', planner=planner, max_attempts=3)
        self.assertTrue(res['completed'], res)
        self.assertEqual(planner.repairs, 1)
        self.assertEqual(res['planner_calls'], 3)
        self.assertEqual([a['action'] for a in res['actions']], ['click', 'extract_table'])

    def test_one_repair_only_then_still_blocked(self):
        class Stubborn:
            repairs = 0
            def propose(self, *args): return {'action': 'extract_table', 'selector': '#invented'}
            def repair(self, *args):
                self.repairs += 1
                return {'action': 'extract_table', 'selector': '#still-invented'}
        p = Stubborn()
        res = evaluate_case(get_cases()[0], mode='mock', planner=p)
        self.assertEqual(res['gap'], 'table_not_observed')
        self.assertEqual(res['status'], 'blocked')
        self.assertEqual(res['planner_calls'], 2)
        self.assertEqual(p.repairs, 1)

    def test_unknown_action_never_repaired(self):
        class Bad:
            repairs = 0
            def propose(self, *args): return {'action': 'run_shell', 'selector': 'echo unsafe'}
            def repair(self, *args): self.repairs += 1; raise AssertionError('no repair allowed')
        p = Bad()
        res = evaluate_case(get_cases()[0], mode='mock', planner=p)
        self.assertEqual(res['status'], 'blocked')
        self.assertEqual(p.repairs, 0)

    def test_correction_instruction_in_native_payload(self):
        import json
        from unittest.mock import patch
        from vcse.discovery import OllamaNativePlanner
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, *a): return json.dumps({'message':{'content':'{"action":"click","selector":"#see-receipts","reason":"navigate"}'}}).encode()
        seen=[]
        def mocked(req,timeout):
            seen.append(json.loads(req.data))
            return Reply()
        p=OllamaNativePlanner('http://localhost:11434','qwen3:4b')
        observation={'links':[{'selector':'#see-receipts','text':'Receipts'}], 'buttons':[], 'tables':[]}
        with patch('vcse.discovery.urlopen',side_effect=mocked):
            result=p.repair('invoices',observation,[], 'https://vcse.fixture.test', {'action':'extract_table','selector':'#wrong','_vcse_error':'table_not_observed'})
        self.assertEqual(result['action'],'click')
        correction=json.loads(seen[0]['messages'][1]['content'])['correction']
        self.assertEqual(correction['problem'].split(' before ')[0], 'You proposed extract_table')
        self.assertEqual(correction['allowed_navigation_links'][0]['selector'], '#see-receipts')
        self.assertEqual(seen[0]['think'],False)

if __name__ == '__main__': unittest.main()
