"""Small, allowlisted Playwright workflow runner; no open-ended browsing."""
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit
from decimal import Decimal, InvalidOperation
import os

@dataclass(frozen=True)
class Step:
    action: Literal['navigate','click','assert_visible','extract_table','inspect']
    target: str
    output: str | None = None

class BrowserPolicyError(RuntimeError): pass
class BrowserWorkflowError(RuntimeError): pass

class BrowserSession:
    def __init__(self, allowed_origins: set[str], timeout_ms=2500, executable_path=None, fixture_documents=None):
        if not allowed_origins: raise BrowserPolicyError('Explicit origin allowlist required')
        self.allowed = frozenset(self.origin(s) for s in allowed_origins)
        self.timeout_ms = timeout_ms
        self.executable_path = executable_path or os.environ.get('VCSE_CHROMIUM_PATH')
        self.fixture_documents = fixture_documents or {}
        if any(not s.startswith(('http://127.0.0.1:','http://localhost:','https://')) for s in self.allowed):
            raise BrowserPolicyError('Use loopback HTTP or HTTPS origins only')

    @staticmethod
    def origin(url):
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
            raise BrowserPolicyError('Invalid origin')
        return f'{p.scheme}://{p.netloc.lower()}'

    def require_url(self,url):
        if self.origin(url) not in self.allowed:
            raise BrowserPolicyError('Navigation/request outside allowlist')

    def run(self,steps:list[Step]):
        if not 1 <= len(steps) <= 30: raise ValueError('Need 1-30 workflow steps')
        from playwright.sync_api import sync_playwright
        records=[]; data={}
        with sync_playwright() as pw:
            kwargs={'headless': True, 'args': ['--no-sandbox']}
            if self.executable_path: kwargs['executable_path']=self.executable_path
            browser=pw.chromium.launch(**kwargs)
            try:
                context=browser.new_context(accept_downloads=False,service_workers='block')
                page=context.new_page()
                page.set_default_timeout(self.timeout_ms)
                def route_handler(route):
                    try:
                        self.require_url(route.request.url)
                        route.continue_()
                    except BrowserPolicyError: route.abort('blockedbyclient')
                context.route('**/*',route_handler)
                for i,step in enumerate(steps):
                    try:
                        if step.action=='navigate':
                            self.require_url(step.target)
                            if step.target in self.fixture_documents:
                                page.set_content(self.fixture_documents[step.target])
                            else:
                                page.goto(step.target,wait_until='domcontentloaded',timeout=self.timeout_ms)
                                self.require_url(page.url)
                            records.append({'step':i,'action':'navigate','target':step.target,'mode':'in_memory_fixture' if step.target in self.fixture_documents else 'network','url':page.url})
                        elif step.action=='inspect':
                            # Bounded, structured DOM observation; never execute page-provided instructions.
                            observation=page.evaluate("""() => ({
                              heading: (document.querySelector('h1')?.innerText || '').slice(0,120),
                              links: Array.from(document.querySelectorAll('a[href]')).slice(0,25).map(a=>({
                                selector: a.id ? '#'+CSS.escape(a.id) : null,
                                text: (a.innerText||'').slice(0,100),
                                href: a.getAttribute('href')
                              })),
                              buttons: Array.from(document.querySelectorAll('button')).slice(0,20).map(b=>({
                                selector: b.id ? '#'+CSS.escape(b.id) : null,
                                text: (b.innerText||'').slice(0,100),
                                disabled: b.disabled
                              })),
                              tables: Array.from(document.querySelectorAll('table')).slice(0,15).map(t=>({
                                selector: t.id ? '#'+CSS.escape(t.id) : null,
                                headers: Array.from(t.querySelectorAll('thead th')).map(h=>(h.innerText||'').slice(0,80)),
                                row_count: t.querySelectorAll('tbody tr').length
                              }))
                            })""")
                            data[step.output or 'observation']=observation
                            records.append({'step':i,'action':'inspect','links':len(observation['links']),'tables':len(observation['tables'])})
                        elif step.action=='click':
                            locator=page.locator(step.target)
                            href=locator.get_attribute('href')
                            if href and self.fixture_documents:
                                locator.evaluate("el => el.addEventListener('click', e => e.preventDefault(), {once: true})")
                            locator.click(timeout=self.timeout_ms)
                            if href and self.fixture_documents:
                                from urllib.parse import urljoin
                                # Fixture links are explicitly mapped; no external fetch.
                                destination=urljoin(next(iter(self.allowed))+'/', href)
                                self.require_url(destination)
                                if destination not in self.fixture_documents: raise BrowserPolicyError('Fixture destination not present')
                                page.set_content(self.fixture_documents[destination])
                            else:
                                self.require_url(page.url)
                            records.append({'step':i,'action':'click','selector':step.target})
                        elif step.action=='assert_visible':
                            page.locator(step.target).wait_for(state='visible',timeout=self.timeout_ms)
                            records.append({'step':i,'action':'assert_visible','selector':step.target})
                        elif step.action=='extract_table':
                            table=page.locator(step.target)
                            table.wait_for(state='visible',timeout=self.timeout_ms)
                            headers=[v.strip() for v in table.locator('thead th').all_text_contents()]
                            rows=[[v.strip() for v in row.locator('td').all_text_contents()] for row in table.locator('tbody tr').all()]
                            if not headers or any(len(row)!=len(headers) for row in rows):
                                raise BrowserWorkflowError('Malformed table')
                            data[step.output or 'table']={'headers':headers,'rows':rows}
                            records.append({'step':i,'action':'extract_table','rows':len(rows)})
                        else: raise BrowserWorkflowError('Unsupported action')
                    except Exception as exc:
                        raise BrowserWorkflowError(f'Step {i} ({step.action}) failed: {type(exc).__name__}: {str(exc)[:170]}') from exc
                return {'data':data,'evidence':records,'final_url':page.url}
            finally: browser.close()

def invoice_table_verifier(output,expected):
    try:
        t=output['data']['invoices']
        if t['headers'] != ['Invoice ID','Amount']: return False
        rows=t['rows']
        if len(rows)!=expected['count']:return False
        ids=[row[0] for row in rows]
        if not all(ids) or len(set(ids))!=len(ids):return False
        amounts=[Decimal(row[1]) for row in rows]
        return all(a.is_finite() and a>=0 for a in amounts) and set(ids)==set(expected['invoice_ids']) and sum(amounts)==Decimal(str(expected['total']))
    except (KeyError,TypeError,InvalidOperation,ValueError,IndexError): return False
