import unittest
from unittest.mock import patch
from vcse.discovery import OllamaNativePlanner
from vcse.phase4 import evaluate_case, get_cases

class RepairTests(unittest.TestCase):
    def test_missing_action_gets_one_repair(self):
        class Planner:
            repairs=0
            def propose(self, goal, observation, failed, home):
                if observation.get('tables'):
                    return {'action':'extract_table','selector':observation['tables'][0]['selector'],'reason':'Extract'}
                return {'reason':'uncertain'}
            def repair(self,*args):
                self.repairs+=1
                return {'action':'click','selector':'#see-receipts','reason':'Open receipts'}
        planner=Planner()
        result=evaluate_case(get_cases()[0],mode='mock',planner=planner,max_attempts=2)
        self.assertEqual(planner.repairs,1)
        self.assertEqual(result['planner_calls'],3)
        self.assertEqual(result['actions'][0]['state'],'executed')

    def test_unsafe_action_never_repaired(self):
        class Planner:
            repairs=0
            def propose(self,*args):return {'action':'run_shell','selector':'#x'}
            def repair(self,*args):self.repairs+=1;return {'action':'stop','selector':''}
        p=Planner(); r=evaluate_case(get_cases()[0],mode='mock',planner=p)
        self.assertEqual(p.repairs,0)
        self.assertEqual(r['status'],'blocked')

    def test_none_after_repair_is_blocked(self):
        class Planner:
            def propose(self,*args):return {'action':None}
            def repair(self,*args):return {'action':None}
        r=evaluate_case(get_cases()[0],mode='mock',planner=Planner())
        self.assertIn('unsupported_action: None',r['gap'])

    def test_native_schema_and_repair(self):
        import json
        from io import BytesIO
        class Reply:
            def __init__(self,v):self.data=json.dumps({'message':{'content':json.dumps(v)}}).encode()
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,*args):return self.data
        planner=OllamaNativePlanner('http://127.0.0.1:11434','qwen3:4b')
        requests=[]
        def fake_urlopen(req,timeout):
            payload=json.loads(req.data);requests.append(payload)
            return Reply({'action':'stop','selector':'','reason':'not found'})
        with patch('vcse.discovery.urlopen',side_effect=fake_urlopen):
            proposal=planner.repair('goal',{'links':[]},[],'https://vcse.fixture.test',{'reason':'bad'})
        self.assertEqual(proposal['action'],'stop')
        self.assertEqual(requests[0]['think'],False)
        self.assertEqual(requests[0]['format']['required'],['action','selector','reason'])
        self.assertIsNotNone(requests[0]['messages'][1]['content'].find('correction'))

if __name__=='__main__':unittest.main()
