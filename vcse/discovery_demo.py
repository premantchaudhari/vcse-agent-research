"""Run Phase 3 controlled discovery. Offline heuristics by default; model only with explicit env vars."""
from dataclasses import asdict
from tempfile import TemporaryDirectory
from pathlib import Path
import json, os
from vcse.browser import BrowserSession
from vcse.fixture import HOME, RECEIPTS
from vcse.discovery import DiscoveryEngine, HeuristicPlanner, OpenAICompatiblePlanner

URL='https://vcse.fixture.test'
EXPECTED={'count':3,'invoice_ids':['INV-101','INV-102','INV-103'],'total':'400.00'}

def run_demo(planner=None, alternate=False, store_path=None):
    if alternate:
        home='''<h1>Billing</h1><button id="primary-export" disabled>Export invoices</button><a id="billing-link" href="/ledger">Billing receipts</a>'''
        receipts='''<h1>Ledger</h1><table id="ledger-data"><thead><tr><th>Invoice ID</th><th>Amount</th></tr></thead><tbody><tr><td>INV-101</td><td>120.50</td></tr><tr><td>INV-102</td><td>79.50</td></tr><tr><td>INV-103</td><td>200.00</td></tr></tbody></table>'''
        docs={URL:home,URL+'/ledger':receipts}
    else:docs={URL:HOME,URL+'/receipts':RECEIPTS}
    browser=BrowserSession({URL},fixture_documents=docs,timeout_ms=500)
    return asdict(DiscoveryEngine(browser,planner or HeuristicPlanner(),URL,EXPECTED,store_path=store_path).execute('Retrieve and verify all invoices'))

if __name__=='__main__':
    planner=None
    if os.environ.get('VCSE_MODEL_ENDPOINT'):
        planner=OpenAICompatiblePlanner(os.environ['VCSE_MODEL_ENDPOINT'],os.environ['VCSE_MODEL_ID'],os.environ['VCSE_MODEL_API_KEY'])
    print(json.dumps(run_demo(planner,store_path='artifacts/verified_skills.jsonl'),indent=2))
