"""Ephemeral local broken invoice export site."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
HOME='''<!doctype html><html><body><h1>Invoice Portal</h1><button id="export" disabled>Export invoices</button><a id="receipts-link" href="/receipts">View receipts</a></body></html>'''
RECEIPTS='''<!doctype html><html><body><h1>Receipts</h1><table id="receipts"><thead><tr><th>Invoice ID</th><th>Amount</th></tr></thead><tbody><tr><td>INV-101</td><td>120.50</td></tr><tr><td>INV-102</td><td>79.50</td></tr><tr><td>INV-103</td><td>200.00</td></tr></tbody></table></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data,code=(HOME,200) if self.path=='/' else ((RECEIPTS,200) if self.path=='/receipts' else ('Not found',404))
        body=data.encode('utf-8');self.send_response(code)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def log_message(self,*_):pass
@contextmanager
def fixture_server():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    try:yield f'http://127.0.0.1:{server.server_port}'
    finally:server.shutdown();server.server_close();worker.join(timeout=3)
