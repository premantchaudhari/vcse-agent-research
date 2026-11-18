import json
import unittest
from unittest.mock import patch
from io import BytesIO

from vcse.discovery import OllamaNativePlanner

class FakeResponse:
    def __init__(self, value):
        self.value = BytesIO(json.dumps(value).encode())
    def __enter__(self): return self.value
    def __exit__(self, *_): return False

class OllamaNativeTests(unittest.TestCase):
    def test_reject_non_local(self):
        with self.assertRaises(ValueError):
            OllamaNativePlanner('https://public.example/api/chat', 'qwen3:4b')

    def test_non_thinking_structured_request(self):
        def fake_open(req, timeout):
            self.assertEqual(req.full_url, 'http://127.0.0.1:11434/api/chat')
            body = json.loads(req.data)
            self.assertIs(body['think'], False)
            self.assertEqual(body['format']['properties']['action']['enum'], ['click', 'extract_table', 'stop'])
            self.assertEqual(body['options']['num_predict'], 160)
            self.assertEqual(body['stream'], False)
            self.assertEqual(body['keep_alive'], '10m')
            self.assertEqual(timeout, 180)
            return FakeResponse({'message': {'content': '{"action":"click","selector":"#records","reason":"Relevant link"}'}})
        with patch('vcse.discovery.urlopen', side_effect=fake_open):
            p = OllamaNativePlanner('http://127.0.0.1:11434/v1/chat/completions','qwen3:4b')
            result=p.propose('Get invoices',{'links':[{'selector':'#records','text':'Records','href':'/records'}]},[], 'https://vcse.fixture.test')
        self.assertEqual(result['selector'], '#records')

    def test_no_content_is_error(self):
        with patch('vcse.discovery.urlopen', return_value=FakeResponse({'message': {'content':''}})):
            with self.assertRaises(ValueError):
                OllamaNativePlanner('http://localhost:11434','qwen3:4b').propose('a',{},[], 'https://vcse.fixture.test')

if __name__=='__main__': unittest.main()
