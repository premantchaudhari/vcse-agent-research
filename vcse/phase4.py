"""Phase 4: held-out fixture suites and evaluation with an actual model-backed planner.

The model endpoint is optional; no simulated planner outcome is represented as LLM performance.
Fixtures are in-memory documents and may not perform any external network requests.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import argparse
import json
import os
import time
from collections import Counter

from vcse.browser import BrowserSession
from vcse.discovery import DiscoveryEngine, HeuristicPlanner, OpenAICompatiblePlanner, OllamaNativePlanner

ORIGIN = 'https://vcse.fixture.test'

@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    goal: str
    documents: dict[str, str]
    expected: dict


def make_case(case_id: str, split: str, heading: str, navigation: list[tuple[str,str,str]],
              target_path: str, table_id: str, include_broken: bool = True, decoy: bool = False) -> Case:
    """Generate cases with distinct wording, paths and element names; truth comes from fixture specification."""
    entries = [('INV-101', '120.50'), ('INV-102', '79.50'), ('INV-103', '200.00')]
    nav = ''.join(f'<a id="{ident}" href="{href}">{label}</a>' for ident, href, label in navigation)
    disabled = '<button disabled id="export-primary">Export invoices</button>' if include_broken else ''
    homepage = f'<h1>{heading}</h1>{disabled}{nav}'
    table = f'''<table id="{table_id}"><thead><tr><th>Invoice ID</th><th>Amount</th></tr></thead><tbody>''' + ''.join(
        f'<tr><td>{inv}</td><td>{amt}</td></tr>' for inv, amt in entries
    ) + '</tbody></table>'
    docs = {ORIGIN: homepage, ORIGIN + target_path: '<h1>Document ledger</h1>' + table}
    if decoy:
        docs[ORIGIN + '/preview'] = '''<h1>Preview</h1><table id="sample-table"><thead><tr><th>Invoice ID</th><th>Amount</th></tr></thead><tbody><tr><td>INV-101</td><td>999.00</td></tr></tbody></table><a id="go-back" href="/">Home</a>'''
    return Case(case_id, split, 'Retrieve all invoices and verify every ID and total', docs,
                {'count':3,'invoice_ids':[x[0] for x in entries], 'total':str(sum((Decimal(a) for _,a in entries),Decimal('0.00')))})


def get_cases() -> list[Case]:
    # Heldout refers to cases withheld from this benchmark's reference examples.
    # These fixtures do not by themselves establish a true out-of-distribution evaluation.
    base = [
        make_case('dev-receipts','development','Payments', [('see-receipts','/receipts','Receipts')], '/receipts', 'invoice-list'),
        make_case('dev-billing','development','Account', [('billing-archive','/ledger','Billing archive')], '/ledger', 'ledger-items'),
        make_case('heldout-statements','heldout','Financial workspace', [('yearly-documents','/docs','Annual statements')], '/docs', 'statement-register'),
        make_case('heldout-records','heldout','Vendor back office', [('history-view','/history','Transaction history')], '/history', 'history-grid'),
        make_case('heldout-vault','heldout','Company workspace', [('vault-entry','/vault','Financial vault')], '/vault', 'vault-list'),
        make_case('heldout-reports','heldout','Operations hub', [('reports-center','/reports','Records center')], '/reports', 'report-grid'),
    ]
    return base


class RecordedPlanner:
    """Instrumentation wrapper. Doesn't change the planner's behavior."""
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0
    def propose(self, goal, observation, failed, home):
        self.calls += 1
        return self.delegate.propose(goal,observation,failed,home)
    def repair(self, goal, observation, failed, home, bad_proposal):
        repair=getattr(self.delegate,'repair',None)
        if not callable(repair):
            return bad_proposal
        self.calls += 1
        return repair(goal,observation,failed,home,bad_proposal)


def make_planner(mode: str):
    if mode=='heuristic': return HeuristicPlanner()
    if mode=='model' and os.environ.get('VCSE_MODEL_BACKEND','openai').lower() == 'ollama':
        return OllamaNativePlanner(
            os.environ.get('VCSE_MODEL_ENDPOINT','http://127.0.0.1:11434'),
            os.environ.get('VCSE_MODEL_ID','qwen3:4b'),
            timeout=float(os.environ.get('VCSE_MODEL_TIMEOUT','180')),
            num_predict=int(os.environ.get('VCSE_MODEL_MAX_TOKENS','160')))
    if mode=='model':
        return OpenAICompatiblePlanner(
            os.environ.get('VCSE_MODEL_ENDPOINT',''),
            os.environ.get('VCSE_MODEL_ID',''),
            os.environ.get('VCSE_MODEL_API_KEY',''),
            timeout=float(os.environ.get('VCSE_MODEL_TIMEOUT','30')))
    raise ValueError('Planner must be heuristic or model')


def evaluate_case(case: Case, mode: str='heuristic', max_attempts: int=7, planner=None) -> dict:
    planner=RecordedPlanner(planner if planner is not None else make_planner(mode))
    browser=BrowserSession({ORIGIN},timeout_ms=500,fixture_documents=case.documents)
    t0=time.monotonic()
    result=DiscoveryEngine(browser,planner,ORIGIN,case.expected,max_attempts=max_attempts).execute(case.goal)
    return {
        'id':case.case_id,'split':case.split,'mode':mode,'completed':result.status=='completed' and result.verified,
        'status':result.status,'gap':result.gap,'planner_calls':planner.calls,
        'failed_actions':sum(a['state'] in ('failed','verification_failed') for a in result.attempts),
        'attempts':len(result.attempts),'elapsed_seconds':round(time.monotonic()-t0,3),
        'actions':result.attempts,
    }


def run_suite(mode: str='heuristic', split: str='all', out: str | None=None, max_attempts: int=7, planner=None) -> dict:
    if split not in ('development','heldout','all'): raise ValueError('Invalid split')
    results=[evaluate_case(c,mode,max_attempts,planner) for c in get_cases() if split=='all' or c.split==split]
    passed=sum(r['completed'] for r in results)
    report={
        'version':'0.4.4','mode':mode,'split':split,'type':'synthetic_browser_fixture',
        'actual_language_model_tested':mode=='model',
        'total':len(results),'verified_successes':passed,
        'verified_success_rate':round(passed/len(results),3) if results else None,
        'total_planner_calls':sum(r['planner_calls'] for r in results),
        'total_failed_actions':sum(r['failed_actions'] for r in results),
        'total_elapsed_seconds':round(sum(r['elapsed_seconds'] for r in results),3),
        'results':results,
    }
    if out:
        p=Path(out);p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    ap=argparse.ArgumentParser(description='Phase 4 fixture evaluation; results cannot establish general web-agent quality')
    ap.add_argument('--planner',choices=['heuristic','model'],default='heuristic')
    ap.add_argument('--split',choices=['development','heldout','all'],default='all')
    ap.add_argument('--output',default='artifacts/phase4-results.json')
    ap.add_argument('--attempts',type=int,default=7)
    a=ap.parse_args()
    r=run_suite(a.planner,a.split,a.output,a.attempts)
    print(json.dumps({k:v for k,v in r.items() if k!='results'},indent=2))
    for x in r['results']:
        print(f"{x['id']}: {'PASS' if x['completed'] else 'FAIL'} ({x['gap'] or x['status']}; {x['planner_calls']} proposals)")
    print('Wrote:',a.output)

if __name__=='__main__': main()
