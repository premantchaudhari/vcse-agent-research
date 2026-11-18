"""VCSE 0.5.1 -- cross-layout image-download capability experiments.

All pages and images are synthetic and run exclusively in a fresh Chromium
context via page.set_content; this module does NOT navigate the public web.
Only observed, bounded browser actions are permitted. 'Save' is not assumed to
mean 'download'. Skill strategies are revalidated on every reuse.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from hashlib import sha256
from io import BytesIO
from tempfile import TemporaryDirectory
import argparse
import base64
import json
import os
import struct
import zlib

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def png_bytes(width=32, height=24):
    """Small deterministic RGB PNG made without image dependencies."""
    def chunk(tag, payload):
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff)
    pixels = b''.join(b'\x00' + bytes([i % 256, 120, 210] * width) for i in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            + chunk(b'IDAT',zlib.compress(pixels)) + chunk(b'IEND',b''))


IMAGE = png_bytes()
IMAGE_URI = 'data:image/png;base64,' + base64.b64encode(IMAGE).decode('ascii')


@dataclass(frozen=True)
class WallpaperCase:
    id: str
    html: str


def fixture_cases():
    # All flows create a *real browser download* of an actual PNG.
    prelude = f'''<script>
function downloadImage() {{
  const a=document.createElement('a');a.href='{IMAGE_URI}';a.download='wallpaper.png';
  document.body.appendChild(a);a.click();a.remove();
}}
</script>'''
    return [
        WallpaperCase('direct', prelude + '<h1>Landscape wallpaper</h1><button id="download" onclick="downloadImage()">Download image</button>'),
        WallpaperCase('menu', prelude + '<h1>Wallpaper gallery</h1><button id="more" onclick="document.querySelector(\'#menu\').hidden=false">More options</button><section id="menu" hidden><button id="save-device" onclick="downloadImage()">Save to device</button></section>'),
        WallpaperCase('bookmark-decoy', prelude + '<h1>Wallpaper collection</h1><button id="more" onclick="document.querySelector(\'#menu\').hidden=false">More</button><section id="menu" hidden><button id="bookmark" onclick="document.querySelector(\'#notice\').textContent=\'Saved to your account\'">Save</button><button id="download-original" onclick="downloadImage()">Download original</button></section><p id="notice"></p>'),
    ]


def _image_verifier(data: bytes, minimum=(32, 24)):
    """File format + complete PNG stream decode + dimensions + deterministic checksum.

    Expected checksum is fixture ground truth, not a generic file-validity check.
    """
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)<45:
        return False
    w,h = struct.unpack('>II',data[16:24])
    if w < minimum[0] or h < minimum[1] or w > 4096 or h > 4096:
        return False
    if data != IMAGE:
        return False
    try:
        i=8; idat=b''; saw_end=False
        while i<len(data):
            length=struct.unpack('>I',data[i:i+4])[0]; tag=data[i+4:i+8]; payload=data[i+8:i+8+length]
            if len(payload)!=length or i+12+length>len(data):return False
            crc=struct.unpack('>I', data[i+8+length:i+12+length])[0]
            if crc != zlib.crc32(tag+payload)&0xffffffff: return False
            if tag==b'IDAT':idat+=payload
            if tag==b'IEND':saw_end=True
            i+=12+length
        return saw_end and i==len(data) and len(zlib.decompress(idat))==h*(1+w*3)
    except (ValueError,IndexError,struct.error,zlib.error):
        return False


def _observed(page):
    return page.locator('button:visible').evaluate_all('''els => els.map(e=>({id:e.id,label:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,90)})).filter(x=>x.id)''')


def _choose(observed, used, plan=None):
    """Safe deterministic capability policy. Not an LLM and not novel generalization."""
    available=[v for v in observed if v['id'] not in used]
    if plan:
        for selector in plan:
            ident=selector.removeprefix('#')
            if any(v['id']==ident for v in available):
                return ident
    # Prefer actual download; open menus; try ambiguous Save only if necessary.
    for keywords in [('download', 'save to device'),('more', 'options'),('save',)]:
        for item in available:
            if any(k in item['label'].lower() for k in keywords):
                return item['id']
    return None


def _run(case: WallpaperCase, learned_plan=None, max_actions=6):
    actions=[]; used=set(); download_path=None
    with TemporaryDirectory() as td:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True, args=['--no-sandbox'], **({'executable_path': os.environ['VCSE_CHROMIUM_PATH']} if os.environ.get('VCSE_CHROMIUM_PATH') else {}))
            try:
                page=browser.new_page(accept_downloads=True)
                page.set_content(case.html)
                for _ in range(max_actions):
                    observed=_observed(page)
                    target=_choose(observed,used,learned_plan)
                    if target is None:
                        break
                    if not any(x['id']==target for x in observed):
                        raise ValueError('Unobserved selector blocked')
                    used.add(target)
                    label=next(x['label'] for x in observed if x['id']==target)
                    locator=page.locator(f'#{target}')
                    try:
                        with page.expect_download(timeout=850) as event:
                            locator.click(timeout=2000)
                        download=event.value
                        file=Path(td)/'downloaded.png'
                        download.save_as(file)
                        data=file.read_bytes()
                        verified = _image_verifier(data) and download.suggested_filename.lower().endswith('.png')
                        actions.append({'action':'click','element':target,'label':label,'download':True,'verified':verified})
                        if verified:
                            return {'id':case.id,'completed':True,'status':'verified','actions':actions,
                                    'sha256':sha256(data).hexdigest(),'bytes':len(data),'download_filename':download.suggested_filename}
                    except PlaywrightTimeout:
                        # Menu opening or bookmark clicked; no file generated.
                        actions.append({'action':'click','element':target,'label':label,'download':False,'verified':False})
                return {'id':case.id,'completed':False,'status':'no_verified_download','actions':actions}
            finally:
                browser.close()


class CapabilityLibrary:
    """Stores capability-typed plans; only verified plans are persisted.

    File corruption or poisoning does not confer permission to execute unobserved
    actions; stored IDs are matched to currently visible DOM elements.
    """
    def __init__(self, path):self.path=Path(path)
    def read(self):
        if not self.path.exists():return []
        data=json.loads(self.path.read_text(encoding='utf8'))
        if not isinstance(data,list):raise ValueError('Bad library')
        return data
    def candidates(self):
        return [x for x in self.read() if isinstance(x,dict) and x.get('capability')=='download_image' and x.get('status')=='verified' and isinstance(x.get('plan'),list) and all(isinstance(a,str) and len(a)<90 and a.startswith('#') for a in x['plan'])]
    def save(self,case,result):
        if not result.get('completed') or not result.get('sha256'):
            raise ValueError('Unverified skill rejected')
        plan=['#'+a['element'] for a in result['actions']]
        if not _run(case,plan).get('completed'):
            raise ValueError('Fresh validation failed')
        entry={'schema':1,'capability':'download_image','scope':'synthetic_wallpaper_fixture_only',
               'status':'verified','source_case':case.id,'plan':plan,'sha256':result['sha256']}
        existing=[e for e in self.read() if not (isinstance(e,dict) and e.get('source_case')==case.id)]
        existing.append(entry)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(self.path.suffix+'.tmp')
        tmp.write_text(json.dumps(existing,indent=2),encoding='utf8')
        os.replace(tmp,self.path)
        return entry


def run_experiment(library_path='artifacts/wallpaper-skills.json',out='artifacts/wallpaper-results.json'):
    lib=CapabilityLibrary(library_path)
    cases=fixture_cases()
    first=[]
    for case in cases:
        result=_run(case)
        if result['completed']:
            lib.save(case,result)
        first.append(result)
    reused=[]
    for case in cases:
        options=lib.candidates()
        # Test whether a verified skill from ANOTHER page can transfer without assuming the same selectors.
        other=next((x for x in options if x['source_case']!=case.id),None)
        result=_run(case,other['plan'] if other else None)
        result['attempted_cross_site_plan']=bool(other)
        reused.append(result)
    report={'version':'0.5.1','scope':'synthetic_browser_fixture_only','planner':'deterministic_policy_not_llm',
            'first_pass':first,'transfer_pass':reused,'verified_first':sum(x['completed'] for x in first),
            'verified_transfer':sum(x['completed'] for x in reused),'total':len(cases)}
    if out:
        path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2),encoding='utf8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--library',default='artifacts/wallpaper-skills.json')
    p.add_argument('--output',default='artifacts/wallpaper-results.json')
    x=p.parse_args()
    r=run_experiment(x.library,x.output)
    print(json.dumps({k:v for k,v in r.items() if not isinstance(v,list)},indent=2))
    for group in ['first_pass','transfer_pass']:
        for row in r[group]:
            print(group,row['id'],row['status'],'actions='+','.join(x['element'] for x in row['actions']))

if __name__=='__main__':main()
