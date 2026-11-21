"""Offline browser-logic tests for the optional third-party mirror."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class MandiMirrorTests(unittest.TestCase):
    def test_mirror_results_errors_and_stale_request(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        script = html.split('        let mandiMirrorRequest = 0;', 1)[1].split('    </script>', 1)[0]
        harness = r'''
const assert = require('assert');
class Element {
  constructor(value = '') { this.value = value; this.children = []; this.textContent = ''; }
  replaceChildren() { this.children = []; this.textContent = ''; }
  appendChild(c) { this.children.push(c); }
}
const elements = {'mirror-prices': new Element(), 'mirror-commodity': new Element('Wheat'), 'mirror-market': new Element('Basti')};
const document = {getElementById: id => elements[id], createElement: () => new Element()};
let fetch;
let mandiMirrorRequest = 0;
''' + script + r'''
(async () => {
  const output = elements['mirror-prices'];
  fetch = async url => {
    assert.match(url, /state=Uttar\+Pradesh/);
    assert.match(url, /commodity=Wheat/);
    assert.match(url, /market=Basti/);
    return {ok: true, json: async () => ({success: true, data: [{district:'<img onerror=evil>', market:'Basti', commodity:'Wheat', variety:'Dara', grade:'FAQ', arrival_date:'2026-10-16', modal_price:2492.05, min_price:2450, max_price:2650}]})};
  };
  await loadMandiMirror();
  assert.match(output.children[0].textContent, /Community mirror/);
  const card = output.children[1].children[0];
  assert.match(card.textContent, /2026-10-16/);
  assert.match(card.textContent, /2,492.05/);
  assert.match(card.textContent, /<img onerror=evil>/);
  fetch = async () => ({ok:true, json:async () => ({success:true, data:[]})});
  await loadMandiMirror();
  assert.match(output.textContent, /कोई भाव नहीं/);
  fetch = async () => { throw Error('offline'); };
  await loadMandiMirror();
  assert.match(output.textContent, /उपलब्ध नहीं/);
  let finish;
  fetch = () => new Promise(resolve => {finish = resolve;});
  const old = loadMandiMirror();
  fetch = async () => ({ok:true, json:async () => ({success:true,data:[]})});
  await loadMandiMirror();
  finish({ok:true, json:async () => ({success:true,data:[{district:'old'}]})});
  await old;
  assert.match(output.textContent, /कोई भाव नहीं/);
})().catch(e => {console.error(e); process.exitCode = 1;});
'''
        subprocess.run(['node', '-e', harness], check=True, timeout=25)


if __name__ == '__main__':
    unittest.main()
