import tempfile
import unittest
from pathlib import Path
from vcse.core import Engine, Plan, SkillStore, Tool, exact_result, numeric_total

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SkillStore(Path(self.temp.name) / 'skills.json')

    def tearDown(self):
        self.temp.cleanup()

    def test_failure_recovers_with_verified_workaround(self):
        tools = [Tool('a_bad', '', 'fetch', lambda _: {'ok': False}), Tool('b_good', '', 'fetch', lambda _: {'ok': True})]
        report = Engine(tools, {'fetch': exact_result}, self.store).execute(Plan('fetch', 'fetch', {}, {'ok': True}))
        self.assertEqual(report.status, 'completed')
        self.assertEqual(report.selected_tool, 'b_good')
        self.assertEqual([a['state'] for a in report.attempts], ['verification_failed','verified'])
        self.assertEqual(self.store.get('fetch','b_good').times_verified, 1)

    def test_missing_verifier_blocks(self):
        result = Engine([], {}, self.store).execute(Plan('x', 'x', {}, {}))
        self.assertEqual(result.gap, 'no_verifier')

    def test_approval_is_enforced(self):
        tool = Tool('send', '', 'send', lambda _: {'ok': True}, requires_approval=True)
        eng = Engine([tool], {'send': exact_result}, self.store)
        plan = Plan('send email', 'send', {}, {'ok': True})
        self.assertEqual(eng.execute(plan).gap, 'approval_required')
        self.assertTrue(eng.execute(plan, approved_tools={'send'}).verified)

    def test_does_not_claim_success_on_bad_output(self):
        tool = Tool('fake', '', 'invoices', lambda _: {'success': True, 'amounts': [200]})
        result = Engine([tool], {'invoices': numeric_total}, self.store).execute(Plan('invoice', 'invoices', {}, {'count': 2, 'total': 400}))
        self.assertFalse(result.verified)
        self.assertEqual(result.status, 'failed')

    def test_stored_skill_prioritized(self):
        self.store.record('x', 'z', True)
        tools = [Tool('a', '', 'x', lambda _: {'ok': True}), Tool('z', '', 'x', lambda _: {'ok': True})]
        rep = Engine(tools, {'x': exact_result}, self.store).execute(Plan('x','x',{}, {'ok': True}))
        self.assertEqual(rep.selected_tool,'z')

    def test_missing_capability_blocks(self):
        result = Engine([], {'x':exact_result}, self.store).execute(Plan('x','x',{},{}))
        self.assertEqual(result.gap,'missing_capability')

if __name__ == '__main__':
    unittest.main()
