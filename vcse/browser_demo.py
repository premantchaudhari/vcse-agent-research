"""Real Chromium failed export -> allowlisted receipt extraction -> verified result."""
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from vcse.browser import BrowserSession,Step,invoice_table_verifier
from vcse.core import Engine,Plan,SkillStore,Tool
from vcse.fixture import HOME, RECEIPTS
import json

def run_demo(store_path=None):
    if True:  # self-contained fixture; no external websites contacted
        url='https://vcse.fixture.test'
        browser=BrowserSession({url},fixture_documents={url:HOME,url+'/receipts':RECEIPTS})
        primary=lambda _:browser.run([Step('navigate',url),Step('click','#export')])
        workaround=lambda _:browser.run([Step('navigate',url),Step('click','#receipts-link'),Step('assert_visible','#receipts'),Step('extract_table','#receipts','invoices')])
        tools=[Tool('a_export_button','Export button','invoices',primary),Tool('b_receipts_table','Read receipts','invoices',workaround)]
        plan=Plan('Retrieve three receipts','invoices',{}, {'count':3,'invoice_ids':['INV-101','INV-102','INV-103'],'total':'400.00'})
        if store_path:
            return asdict(Engine(tools,{'invoices':invoice_table_verifier},SkillStore(store_path),2).execute(plan))
        with TemporaryDirectory() as d:
            return asdict(Engine(tools,{'invoices':invoice_table_verifier},SkillStore(Path(d)/'skills.json'),2).execute(plan))
if __name__=='__main__':print(json.dumps(run_demo(),indent=2))
