import unittest
from vcse.browser import BrowserSession,BrowserPolicyError,invoice_table_verifier,Step
from vcse.browser_demo import run_demo
from vcse.fixture import HOME, RECEIPTS
class BrowserTests(unittest.TestCase):
    def test_origin_policy(self):
        b=BrowserSession({'http://127.0.0.1:7777'})
        with self.assertRaises(BrowserPolicyError):b.require_url('https://example.org/')
        with self.assertRaises(BrowserPolicyError):b.require_url('http://127.0.0.1:7778/')
    def test_reject_duplicate_and_wrong_total(self):
        out={'data':{'invoices':{'headers':['Invoice ID','Amount'],'rows':[['A','100'],['A','300']]}}}
        exp={'count':2,'invoice_ids':['A','B'],'total':'400'}
        self.assertFalse(invoice_table_verifier(out,exp))
        out['data']['invoices']['rows'][1]=['B','301']
        self.assertFalse(invoice_table_verifier(out,exp))
    def test_real_chromium_workaround(self):
        r=run_demo()
        self.assertEqual(r['status'],'completed',str(r))
        self.assertEqual(r['selected_tool'],'b_receipts_table')
        self.assertEqual([x['state'] for x in r['attempts']],['tool_error','verified'])
    def test_direct_navigation(self):
        url='https://vcse.fixture.test'
        b=BrowserSession({url},fixture_documents={url:HOME,url+'/receipts':RECEIPTS})
        out=b.run([Step('navigate',url+'/receipts'),Step('extract_table','#receipts','invoices')])
        self.assertEqual(len(out['data']['invoices']['rows']),3)
