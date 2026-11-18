import sys, tempfile, json, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'tools'))
from compare_agents import origin, safe_url, done, key, Gemini
from gemini_proxy import Meter, REMOTE

class BenchmarkTests(unittest.TestCase):
    def test_https_only(self):
        with self.assertRaises(ValueError):origin('http://example.com')
        with self.assertRaises(ValueError):origin('https://user:pass@example.com')
    def test_origin_approved(self):
        self.assertTrue(safe_url('https://www.python.org/doc/',{'https://www.python.org'}))
        self.assertFalse(safe_url('https://evil.python.org/doc/',{'https://www.python.org'}))
    def test_private_actions_blocked(self):
        for path in ('/vault','/account','/login','/logout','/checkout'):
            self.assertFalse(safe_url('https://www.python.org'+path,{'https://www.python.org'}))
    def test_verifier_is_independent(self):
        task={'url_contains':['docs.python.org']}
        self.assertTrue(done({'url':'https://docs.python.org/3/','title':'','heading':''},task))
        self.assertFalse(done({'url':'https://www.python.org/','title':'Documentation','heading':''},task))
    def test_key_order_independent(self):
        t={'id':'test'}
        a={'url':'https://example.org/','links':[{'text':'A','href':'https://example.org/a'},{'text':'B','href':'https://example.org/b'}]}
        b={**a,'links':list(reversed(a['links']))}
        self.assertEqual(key(t,a),key(t,b))
    def test_meter_requires_all_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            meter=Meter(str(Path(tmp)/'meter.jsonl'))
            meter.append({'status':200,'usage':{'prompt_tokens':10,'completion_tokens':3}})
            self.assertEqual(meter.snapshot()['input_tokens'],10)
            meter.append({'status':429,'usage':None})
            self.assertIsNone(meter.snapshot()['input_tokens'])
            self.assertEqual(meter.snapshot()['model_calls'],2)
    def test_upstream_is_google(self):
        self.assertEqual(REMOTE,'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
    def test_client_requires_no_extra_packages(self):
        client=Gemini('http://127.0.0.1:9999/v1','gemini-2.5-flash',10)
        self.assertEqual(client.model,'gemini-2.5-flash')

if __name__=='__main__':unittest.main()

class TrialTests(unittest.TestCase):
    def test_planner_metrics_contract_without_network(self):
        import compare_agents
        class Site:
            actions=0
            def __init__(self):self.index=0
            def observe(self):
                return {'url':'https://www.python.org/' if not self.index else 'https://docs.python.org/3/', 'title':'Python','heading':'',
                        'links':[{'text':'Docs','href':'https://docs.python.org/3/'}]}
            def follow(self,index,obs):
                self.actions+=1;self.index+=1;return self.observe()
        class Planner:
            def decide(self,goal,obs):return {'action':'follow','index':0},{'input_tokens':0,'output_tokens':0}
        task={'id':'test','goal':'documentation','url_contains':['docs.python.org']}
        result=compare_agents.vcse_trial(Site(),task,Planner(),limit=2)
        self.assertTrue(result['success'])
        self.assertEqual(result['model_calls'],1)
    def test_memory_stores_only_success(self):
        import compare_agents
        class Site:
            actions=0
            def observe(self):return {'url':'https://example.com/','title':'Home','heading':'',
                                       'links':[{'text':'Other','href':'https://example.com/other'}]}
            def follow(self,index,obs):self.actions+=1;return self.observe()
        class Planner:
            def decide(self,goal,obs):return {'action':'follow','index':0},{'input_tokens':0,'output_tokens':0}
        mem={}; task={'id':'test','goal':'never','url_contains':['not-present']}
        r=compare_agents.vcse_trial(Site(),task,Planner(),library=mem,limit=1)
        self.assertFalse(r['success'])
        self.assertFalse(mem)
