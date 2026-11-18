"""Toy deterministic harness: baseline one-shot vs fallback engine.
Not evidence of real-world model superiority.
"""
from __future__ import annotations
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from vcse.core import Tool, Plan, Engine, SkillStore, exact_result


def run():
    cases = [
        {'key':'broken_export','primary':False,'alternate':True},
        {'key':'working_export','primary':True,'alternate':True},
        {'key':'both_broken','primary':False,'alternate':False},
        {'key':'alternate_broken','primary':True,'alternate':False},
        {'key':'fallback_only','primary':False,'alternate':True},
    ]
    baseline = 0
    vcse = 0
    records = []
    with TemporaryDirectory() as d:
        engstore = SkillStore(Path(d)/'skills.json')
        for idx,case in enumerate(cases):
            expected={'ok':True}
            tools=[Tool('a_primary', '', case['key'], lambda _, ok=case['primary']:{'ok':ok}),Tool('b_fallback','',case['key'],lambda _,ok=case['alternate']:{'ok':ok})]
            baseline_result = exact_result(tools[0].run({}),expected)
            rep=Engine(tools,{case['key']:exact_result},engstore).execute(Plan(case['key'],case['key'],{},expected))
            baseline += int(baseline_result)
            vcse += int(rep.verified)
            records.append({'case':case['key'],'baseline_success':baseline_result,'vcse_success':rep.verified,'attempts':len(rep.attempts)})
    print(json.dumps({'notice':'Synthetic demonstration only, no empirical model benchmarks','cases':len(cases),'baseline_success':baseline,'vcse_success':vcse,'details':records},indent=2))

if __name__=='__main__':
    run()
