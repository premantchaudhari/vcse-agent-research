"""Loopback metering proxy to the Google Gemini OpenAI-compatible API.

Never records prompts, response bodies, or the API key. Restricts path and host.
Records call and usage records to a task-local JSONL audit file, including on failures.
"""
from __future__ import annotations
import json, os, threading, time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REMOTE = 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'  # legacy benchmark constant

# Exact fixed endpoints. Never accept arbitrary forwarding destinations from model or environment.
PROVIDERS = {
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'GEMINI_API_KEY'),
    'openai': ('https://api.openai.com/v1/chat/completions', 'OPENAI_API_KEY'),
    'groq': ('https://api.groq.com/openai/v1/chat/completions', 'GROQ_API_KEY'),
    'openrouter': ('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY'),
}

def provider_config(provider: str):
    if provider not in PROVIDERS:
        raise ValueError('Unsupported provider. Choose from: '+', '.join(PROVIDERS))
    return PROVIDERS[provider]


class Meter:
    def __init__(self, journal):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_complete = True
        self.journal = journal
        self._lock = threading.Lock()
    def append(self, entry):
        with self._lock:
            self.calls += 1
            usage = entry.get('usage')
            if isinstance(usage, dict) and isinstance(usage.get('prompt_tokens'), int) and isinstance(usage.get('completion_tokens'), int):
                self.input_tokens += usage['prompt_tokens']
                self.output_tokens += usage['completion_tokens']
            else:
                self.usage_complete = False
            if self.journal:
                with open(self.journal, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False)+'\n')
                    f.flush()
    def snapshot(self):
        with self._lock:
            return {'model_calls':self.calls,'input_tokens':self.input_tokens if self.usage_complete else None,
                    'output_tokens':self.output_tokens if self.usage_complete else None,
                    'token_counts_available':self.usage_complete, 'usage_coverage':'complete' if self.usage_complete else 'incomplete'}

@contextmanager
def metered_gemini(api_key, model, call_timeout=25, max_output_tokens=256, journal=None, provider="gemini"):
    if not api_key: raise ValueError('GEMINI_API_KEY is required')
    upstream, _ = provider_config(provider)
    meter = Meter(journal)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            if self.path != '/v1/chat/completions':
                self.send_error(404); return
            size = int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 250_000:
                self.send_error(413); return
            started = time.monotonic()
            usage = None
            http_code = 502
            error = None
            try:
                body = json.loads(self.rfile.read(size))
                if body.get('model') != model:
                    raise ValueError('Request model does not match benchmark model')
                # Both arms receive exactly the same reasoning/output constraints.
                # Disable thinking only where the selected model supports it.
                body.pop('reasoning_effort', None)
                if provider == 'gemini' and model.startswith('gemini-2.5'):
                    body['reasoning_effort'] = 'none'
                body['max_tokens'] = max_output_tokens
                # Temperature may be unsupported for some reasoning models; keep
                # it only for Gemini 2.5 and standard non-reasoning models.
                if provider == 'gemini' and not model.startswith('gemini-2.5'):
                    body.pop('temperature', None)
                streaming = bool(body.get('stream'))
                if streaming:
                    body['stream_options'] = {'include_usage': True}
                else:
                    body.pop('stream_options', None)
                req = Request(upstream, data=json.dumps(body).encode('utf-8'), headers={
                    'Authorization':'Bearer '+api_key, 'Content-Type':'application/json'})
                print('[API] call started', flush=True)
                try:
                    with urlopen(req, timeout=call_timeout) as res:
                        http_code = res.status
                        if streaming and http_code == 200:
                            self.send_response(http_code)
                            self.send_header('Content-Type','text/event-stream')
                            self.end_headers()
                            for line in res:
                                if line.startswith(b'data:'):
                                    try:
                                        d=json.loads(line[5:])
                                        if isinstance(d.get('usage'),dict):usage=d['usage']
                                    except (ValueError,UnicodeDecodeError): pass
                                try:self.wfile.write(line);self.wfile.flush()
                                except (BrokenPipeError,ConnectionResetError): break
                            return
                        response_body=res.read(1_500_000)
                except HTTPError as exc:
                    http_code = exc.code
                    response_body = json.dumps({'error': {'message':'Gemini API HTTP '+str(exc.code), 'type':'api_error'}}).encode()
                if http_code == 200:
                    parsed = json.loads(response_body)
                    usage = parsed.get('usage')
                self.send_response(http_code)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
            except (TimeoutError, URLError, OSError) as exc:
                error=type(exc).__name__
                self.send_response(504);self.end_headers()
                try:self.wfile.write(b'{"error":{"message":"upstream timeout"}}')
                except OSError:pass
            except (ValueError, TypeError, KeyError) as exc:
                error=type(exc).__name__
                self.send_response(400);self.end_headers()
                try:self.wfile.write(b'{"error":{"message":"invalid benchmark request"}}')
                except OSError:pass
            finally:
                elapsed = round((time.monotonic()-started)*1000, 1)
                meter.append({'status':http_code,'elapsed_ms':elapsed,'usage':usage,'error':error})
                print('[API] call finished status=%s elapsed_ms=%s usage=%s'%(http_code,elapsed,'yes' if usage else 'missing'),flush=True)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%s/v1'%server.server_port,meter
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
