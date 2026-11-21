import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import import_mandi_csv as importer


class UploadedPricesTests(unittest.TestCase):
    def test_import_filters_and_preserves_values(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'feed.csv'
            with source.open('w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(importer.REQUIRED)
                writer.writerow(['Uttar Pradesh', 'Lucknow', 'Market', 'Wheat', 'Dara', 'FAQ', '21/11/2026', '2400', '2500', '2450.25'])
                writer.writerow(['Bihar', 'Patna', 'Market', 'Rice', 'Other', 'FAQ', '21/11/2026', '1', '2', '1'])
                writer.writerow(['Uttar Pradesh', 'Lucknow', 'Market', 'Rice', '', '', 'bad-date', '1', '2', '1'])
            payload = importer.convert(source)
            self.assertEqual(len(payload['records']), 1)
            self.assertEqual(payload['skipped_up_rows'], 1)
            self.assertEqual(payload['records'][0]['modal_price'], '2450.25')
            self.assertEqual(payload['records'][0]['arrival_date'], '2026-11-21')
            self.assertFalse(payload['cross_verified'])

    def test_invalid_import_does_not_overwrite_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bad.csv'
            out = Path(directory) / 'snapshot.json'
            source.write_text('bad,header\n1,2\n')
            out.write_text('old')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/import_mandi_csv.py'), str(source), '--output', str(out)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(out.read_text(), 'old')

    def test_supplied_snapshot_is_separate_and_has_reported_date(self):
        payload = json.loads((ROOT / 'data/uploaded_prices.json').read_text())
        self.assertEqual(len(payload['records']), 374)
        self.assertFalse(payload['cross_verified'])
        self.assertEqual({r['arrival_date'] for r in payload['records']}, {'2026-11-21'})
        self.assertEqual(sum(r['commodity'] == 'Wheat' for r in payload['records']), 34)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_frontend_filters_and_limits_rows(self):
        html = (ROOT / 'index.html').read_text()
        script = html.split('        let uploadedPriceRows = null;', 1)[1].split('    </script>', 1)[0]
        harness = r'''
const assert = require('assert');
class E { constructor(value='') { this.value=value; this.children=[]; this.textContent=''; }
 replaceChildren(){this.children=[]; this.textContent='';} appendChild(e){this.children.push(e);} }
const elements={'uploaded-prices':new E(), 'uploaded-search':new E()};
const document={getElementById:id=>elements[id],createElement:()=>new E()};
let uploadedPriceRows=null;
let fetch = async () => ({ok:true,json:async()=>({records:Array.from({length:60},(_,i)=>({district:'Lucknow',market:'<x>',commodity:i===0?'Rice':'Wheat',arrival_date:'2026-11-21',min_price:'10',modal_price:'11',max_price:'12'}))})});
''' + script + r'''
(async()=>{await loadUploadedPrices(); const out=elements['uploaded-prices'];
 assert.equal(out.children[1].children.length,50);
 assert.match(out.children[1].children[0].textContent, /<x>/);
 renderUploadedPrices(true); assert.equal(out.children[1].children.length,60);
 elements['uploaded-search'].value='Rice'; renderUploadedPrices();
 assert.equal(out.children[1].children.length,1);
 assert.match(out.children[1].children[0].textContent,/2026-11-21/);
 fetch=async()=>{throw Error('offline')}; await loadUploadedPrices(); assert.match(out.textContent,/उपलब्ध नहीं/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
        subprocess.run(['node', '-e', harness], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
