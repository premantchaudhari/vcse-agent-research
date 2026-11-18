import unittest
from vcse.discovery_demo import run_demo, URL, EXPECTED
from vcse.browser import BrowserSession
from vcse.fixture import HOME,RECEIPTS
from vcse.discovery import DiscoveryEngine

class StaticPlanner:
    def __init__(self,result):self.result=result
    def propose(self,*args):return self.result

class DiscoveryTests(unittest.TestCase):
    def test_discover_broken_export_and_recover(self):
        r=run_demo()
        self.assertTrue(r['verified']);self.assertEqual(r['status'],'completed')
        self.assertIn('failed',[a['state'] for a in r['attempts']])
    def test_generalizes_to_unseen_selectors(self):
        r=run_demo(alternate=True)
        self.assertTrue(r['verified']);self.assertTrue(any(a['target']=='#ledger-data' for a in r['attempts']))
    def test_reject_unobserved_selector(self):
        r=self.run_for(StaticPlanner({'action':'click','selector':'#secret'}))
        self.assertEqual(r.status,'blocked');self.assertEqual(r.gap,'selector_not_observed')
    def test_reject_unknown_action(self):
        r=self.run_for(StaticPlanner({'action':'run_shell','selector':'#export'}))
        self.assertTrue(r.gap.startswith('unsupported_action:'))
    def test_refuse_enabled_button(self):
        doc='<button id="pay">Pay now</button>'
        b=BrowserSession({URL},fixture_documents={URL:doc})
        r=DiscoveryEngine(b,StaticPlanner({'action':'click','selector':'#pay'}),URL,EXPECTED).execute('Invoices')
        self.assertEqual(r.gap,'button_side_effect_not_authorized')
    def test_reject_outside_origin(self):
        doc='<a id="outside" href="https://other.test/data">Receipts</a>'
        b=BrowserSession({URL},fixture_documents={URL:doc})
        r=DiscoveryEngine(b,StaticPlanner({'action':'click','selector':'#outside'}),URL,EXPECTED).execute('Invoices')
        self.assertEqual(r.status,'blocked');self.assertEqual(r.gap,'outside_allowed_origin')
    def test_no_verification_cannot_claim_success(self):
        r=self.run_for(StaticPlanner({'action':'stop'}))
        self.assertFalse(r.verified);self.assertEqual(r.status,'failed')
    def run_for(self,planner):
        b=BrowserSession({URL},fixture_documents={URL:HOME,URL+'/receipts':RECEIPTS})
        return DiscoveryEngine(b,planner,URL,EXPECTED).execute('Invoices')

if __name__=='__main__':unittest.main()
