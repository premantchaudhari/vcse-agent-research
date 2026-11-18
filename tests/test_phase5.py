import json
import tempfile
import unittest
from pathlib import Path

from vcse.phase4 import get_cases, make_case
from vcse.phase5 import SkillLibrary, evaluate_with_skills, replay, case_fingerprint


class SuccessPlanner:
    def __init__(self): self.calls=0
    def propose(self, goal, observation, failed, home):
        self.calls+=1
        tables=observation['tables']
        if tables: return {'action':'extract_table','selector':tables[0]['selector']}
        links=observation['links']
        if links: return {'action':'click','selector':links[0]['selector']}
        return {'action':'stop'}


class SkillLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.lib=SkillLibrary(Path(self.tmp.name)/'library.json')
        self.case=get_cases()[0]
        self.actions=[{'action':'click','target':'#see-receipts'},
                      {'action':'extract_table','target':'#invoice-list'}]
    def tearDown(self): self.tmp.cleanup()

    def test_verified_replay(self):
        self.assertTrue(replay(self.case,self.actions))

    def test_reject_unverified_and_unsafe_skills(self):
        for actions in [[], [{'action':'execute_js','target':'#see-receipts'}],
                        [{'action':'click','target':'#missing'},self.actions[-1]],
                        [{'action':'click','target':'#export-primary'},self.actions[-1]]]:
            with self.assertRaises(ValueError):self.lib.save_verified(self.case,actions)
        self.assertFalse(self.lib.path.exists())

    def test_first_run_learns_second_run_skips_model(self):
        planner=SuccessPlanner()
        result=evaluate_with_skills(self.case,self.lib,planner=planner)
        self.assertTrue(result['completed'])
        self.assertTrue(result['skill_saved'])
        self.assertEqual(result['planner_calls'],2)
        result2=evaluate_with_skills(self.case,self.lib,planner=SuccessPlanner())
        self.assertTrue(result2['completed'])
        self.assertTrue(result2['skill_reused'])
        self.assertEqual(result2['planner_calls'],0)

    def test_no_cross_fixture_skill_reuse(self):
        self.lib.save_verified(self.case,self.actions)
        other=get_cases()[1]
        self.assertNotEqual(case_fingerprint(self.case),case_fingerprint(other))
        self.assertEqual(self.lib.candidates(other),[])

    def test_changed_fixture_triggers_new_discovery(self):
        self.lib.save_verified(self.case,self.actions)
        revised=make_case('changed','development','Payments',
                          [('new-records','/new','Receipts')],'/new','new-table')
        result=evaluate_with_skills(revised,self.lib,planner=SuccessPlanner())
        self.assertTrue(result['completed'])
        self.assertFalse(result['skill_reused'])
        self.assertGreater(result['planner_calls'],0)

    def test_tampered_or_stale_skill_is_rejected_and_fallback_runs(self):
        self.lib.save_verified(self.case,self.actions)
        raw=json.loads(self.lib.path.read_text())
        raw[0]['actions'][0]['target']='#missing'
        self.lib.path.write_text(json.dumps(raw))
        result=evaluate_with_skills(self.case,self.lib,planner=SuccessPlanner())
        self.assertTrue(result['completed'])
        self.assertTrue(result['reuse_attempted'])
        self.assertFalse(result['skill_reused'])
        self.assertEqual(result['reuse_failure'],'stored_skill_no_longer_valid')
        self.assertGreater(result['planner_calls'],0)

    def test_deduplicate_storage_and_without_private_contents(self):
        first=self.lib.save_verified(self.case,self.actions)
        second=self.lib.save_verified(self.case,self.actions)
        self.assertEqual(first.id,second.id)
        raw=json.loads(self.lib.path.read_text())
        self.assertEqual(len(raw),1)
        self.assertNotIn('INV-101',self.lib.path.read_text())
        self.assertNotIn('120.50',self.lib.path.read_text())


if __name__=='__main__': unittest.main()
