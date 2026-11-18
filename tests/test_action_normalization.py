import unittest
from vcse.discovery import canonicalize_proposal
from vcse.phase4 import evaluate_case, get_cases

class ActionNormalizationTests(unittest.TestCase):
    def test_safe_aliases(self):
        self.assertEqual(canonicalize_proposal({'action':'Click Link','selector':'#x'})['action'], 'click')
        self.assertEqual(canonicalize_proposal({'action':'read_table','selector':'#t'})['action'], 'extract_table')
        self.assertEqual(canonicalize_proposal({'action':'finish'})['action'], 'stop')

    def test_unknown_is_not_accepted(self):
        self.assertEqual(canonicalize_proposal({'action':'run_shell','selector':'#x'})['action'], 'run_shell')
        self.assertEqual(canonicalize_proposal({'action':'navigate','selector':'#x'})['action'], 'navigate')

    def test_no_unobserved_selector(self):
        class Model:
            def propose(self, *args): return {'action':'Click Link','selector':'#invented'}
        result = evaluate_case(get_cases()[0], mode='mock', planner=Model())
        self.assertEqual(result['gap'], 'selector_not_observed')
        self.assertEqual(result['attempts'], 0)

    def test_unknown_action_diagnostic(self):
        class Model:
            def propose(self,*args): return {'action':'navigate','selector':'#x'}
        result = evaluate_case(get_cases()[0], mode='mock', planner=Model())
        self.assertEqual(result['gap'], 'unsupported_action: navigate')

if __name__ == '__main__': unittest.main()
