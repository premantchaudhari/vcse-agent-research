"""Phase 5: conservative, verified, fixture-scoped skill reuse.

Only read-only, observed-link clicks plus exact verified invoice table extraction.
Skills must pass a fresh replay before persistence and another before reuse.
This does not fine-tune an LLM and does not support real external accounts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import tempfile
import time
from urllib.parse import urljoin

from vcse.browser import BrowserSession, BrowserWorkflowError, Step, invoice_table_verifier
from vcse.discovery import DiscoveryEngine
from vcse.phase4 import Case, ORIGIN, RecordedPlanner, get_cases, make_planner


def goal_key(goal: str) -> str:
    return sha256(' '.join(goal.strip().lower().split()).encode('utf8')).hexdigest()


def case_fingerprint(case: Case) -> str:
    """Conservative fixture identity. Never use learned skills on different documents."""
    canonical = json.dumps({'origin': ORIGIN, 'documents': case.documents}, sort_keys=True, ensure_ascii=False)
    return sha256(canonical.encode('utf8')).hexdigest()


def valid_steps(actions: list[dict]) -> list[Step]:
    if not isinstance(actions, list) or not 1 <= len(actions) <= 10:
        raise ValueError('Invalid actions length')
    steps = [Step('navigate', ORIGIN)]
    for i, a in enumerate(actions):
        if not isinstance(a, dict) or a.get('action') not in ('click', 'extract_table'):
            raise ValueError('Unsupported skill action')
        selector = a.get('target')
        if not isinstance(selector, str) or not selector.startswith('#') or len(selector) > 150:
            raise ValueError('Invalid skill selector')
        if a['action'] == 'extract_table' and (i != len(actions)-1 or any(x['action']=='extract_table' for x in actions[:i])):
            raise ValueError('Extract must be last and unique')
        if a['action'] == 'click':
            steps.append(Step('click', selector))
        else:
            steps.append(Step('extract_table', selector, 'invoices'))
    if steps[-1].action != 'extract_table':
        raise ValueError('Skill requires extraction')
    return steps


def replay(case: Case, actions: list[dict]) -> bool:
    """Observe and check every step before invoking the browser runner."""
    steps = valid_steps(actions)
    browser = BrowserSession({ORIGIN}, timeout_ms=750, fixture_documents=case.documents)
    prefix = [steps[0]]
    try:
        for step in steps[1:]:
            obs = browser.run(prefix + [Step('inspect', '', 'observation')])['data']['observation']
            if step.action == 'click':
                matches = [link for link in obs['links'] if link.get('selector') == step.target]
                if len(matches) != 1:
                    return False
                url = urljoin(ORIGIN+'/', matches[0].get('href', ''))
                browser.require_url(url)
                if url not in case.documents:
                    return False
            elif step.action == 'extract_table':
                matches = [table for table in obs['tables'] if table.get('selector') == step.target]
                if len(matches) != 1 or matches[0].get('headers') != ['Invoice ID', 'Amount']:
                    return False
            prefix.append(step)
        result = browser.run(prefix)
        return invoice_table_verifier(result, case.expected)
    except (BrowserWorkflowError, ValueError, KeyError, TypeError):
        return False


@dataclass
class Skill:
    schema: int
    id: str
    goal_hash: str
    fixture_hash: str
    scope: str
    actions: list[dict]
    validated_at: str
    verification: str


class SkillLibrary:
    """JSON file with atomic writes, never executable code or authentication data."""
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding='utf8'))
        if not isinstance(data, list):
            raise ValueError('Invalid skill library format')
        return data

    def candidates(self, case: Case) -> list[dict]:
        matching = []
        for item in self._load():
            if (isinstance(item, dict) and item.get('schema') == 1
                and item.get('scope') == 'in_memory_fixture_only'
                and item.get('goal_hash') == goal_key(case.goal)
                and item.get('fixture_hash') == case_fingerprint(case)
                and item.get('verification') == 'fresh_browser_replay_passed'):
                matching.append(item)
        return matching[:10]

    def save_verified(self, case: Case, actions: list[dict]) -> Skill:
        if not replay(case, actions):
            raise ValueError('Cannot persist an unverified skill')
        safe_actions = [{'action': x['action'], 'target': x['target']} for x in actions]
        ident = sha256(json.dumps({'goal':goal_key(case.goal),'fixture':case_fingerprint(case),'actions':safe_actions},sort_keys=True).encode()).hexdigest()[:20]
        skill=Skill(1,ident,goal_key(case.goal),case_fingerprint(case),'in_memory_fixture_only',safe_actions,datetime.now(timezone.utc).isoformat(),'fresh_browser_replay_passed')
        existing=self._load()
        existing=[x for x in existing if x.get('id') != skill.id]
        existing.append(asdict(skill))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.vcse-skill-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf8') as out:
                json.dump(existing,out,indent=2)
                out.flush();os.fsync(out.fileno())
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return skill


def evaluate_with_skills(case: Case, library: SkillLibrary, mode='heuristic', planner=None) -> dict:
    t0=time.monotonic()
    reuse_attempted=False
    rejection_reason=None
    for skill in library.candidates(case):
        reuse_attempted=True
        try:
            if replay(case,skill['actions']):
                return {'id':case.case_id, 'completed':True,'status':'reused_verified',
                        'planner_calls':0,'skill_id':skill['id'],'skill_reused':True,
                        'reuse_attempted':True,'reuse_failure':None,
                        'elapsed_seconds':round(time.monotonic()-t0,3)}
            rejection_reason='stored_skill_no_longer_valid'
        except (ValueError, KeyError, TypeError, BrowserWorkflowError):
            rejection_reason='stored_skill_invalid'

    model=RecordedPlanner(planner if planner is not None else make_planner(mode))
    browser=BrowserSession({ORIGIN},timeout_ms=750,fixture_documents=case.documents)
    result=DiscoveryEngine(browser,model,ORIGIN,case.expected,max_attempts=7).execute(case.goal)
    saved=False
    saved_id=None
    if result.status=='completed' and result.verified:
        # Do not include unsuccessful actions in learned procedure.
        actions=[{'action':a['action'],'target':a['target']} for a in result.attempts
                 if a.get('state') in ('executed','verified')]
        if actions and actions[-1]['action']=='extract_table':
            try:
                saved_skill=library.save_verified(case,actions)
                saved=True; saved_id=saved_skill.id
            except (ValueError, BrowserWorkflowError):
                pass
    return {'id':case.case_id,'completed':result.status=='completed' and result.verified,
            'status':result.status,'gap':result.gap,'planner_calls':model.calls,
            'skill_saved':saved,'skill_id':saved_id,'skill_reused':False,
            'reuse_attempted':reuse_attempted,'reuse_failure':rejection_reason,
            'elapsed_seconds':round(time.monotonic()-t0,3)}


def run_suite(mode='heuristic',split='heldout',library_path='artifacts/phase5-skills.json',repeat=False,output=None):
    if split not in ('development','heldout','all'):
        raise ValueError('Invalid split')
    cases=[c for c in get_cases() if split=='all' or c.split==split]
    library=SkillLibrary(library_path)
    first=[evaluate_with_skills(c,library,mode) for c in cases]
    second=[evaluate_with_skills(c,library,mode) for c in cases] if repeat else []
    summary={'version':'0.5','scope':'synthetic_browser_fixture_only','mode':mode,'split':split,
             'first_pass':first,'replay_pass':second,
             'first_pass_successes':sum(x['completed'] for x in first),
             'first_pass_planner_calls':sum(x['planner_calls'] for x in first),
             'replay_successes':sum(x['completed'] for x in second),
             'replay_planner_calls':sum(x['planner_calls'] for x in second),
             'reused_skills':sum(x.get('skill_reused',False) for x in second)}
    if output:
        p=Path(output);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(summary,indent=2),encoding='utf8')
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--planner',choices=['heuristic','model'],default='heuristic')
    ap.add_argument('--split',choices=['development','heldout','all'],default='heldout')
    ap.add_argument('--library',default='artifacts/phase5-skills.json')
    ap.add_argument('--output',default='artifacts/phase5-results.json')
    ap.add_argument('--repeat',action='store_true')
    args=ap.parse_args()
    result=run_suite(args.planner,args.split,args.library,args.repeat,args.output)
    print(json.dumps({k:v for k,v in result.items() if not isinstance(v,list)},indent=2))
    for r in result['first_pass']:
        print('TRAIN',r['id'],r['status'],'calls=',r['planner_calls'],'saved=',r['skill_saved'])
    for r in result['replay_pass']:
        print('REUSE',r['id'],r['status'],'calls=',r['planner_calls'])
    print('Report:',args.output)

if __name__=='__main__':main()
