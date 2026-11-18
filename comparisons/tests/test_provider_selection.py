import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gemini_proxy import provider_config
class ProviderTests(unittest.TestCase):
    def test_frozen_hosts(self):
        for key in ('gemini','openai','groq','openrouter'):
            endpoint,secret=provider_config(key)
            self.assertTrue(endpoint.startswith('https://'))
            self.assertTrue(secret.endswith('_API_KEY'))
    def test_unlisted_rejected(self):
        with self.assertRaises(ValueError):provider_config('http://localhost/internal')
if __name__=='__main__':unittest.main()
