"""Exercise the browser forecast without calling a third-party service."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for browser logic tests')
class AgriForecastTests(unittest.TestCase):
    def test_validation_success_failure_and_superseded_requests(self):
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        script = html.split('        let agriForecastRequest = 0;', 1)[1].split('    </script>', 1)[0]
        harness = r'''
const assert = require('assert');
class Element {
  constructor(value = '') { this.value = value; this.children = []; this.textContent = ''; }
  replaceChildren() { this.children = []; this.textContent = ''; }
  appendChild(child) { this.children.push(child); }
}
const elements = {'agri-forecast': new Element(), 'weather-lat': new Element(''), 'weather-lon': new Element('80')};
const document = {getElementById: id => elements[id], createElement: () => new Element()};
let fetchCount = 0;
let fetch = async () => { fetchCount++; throw Error('offline'); };
let agriForecastRequest = 0;
''' + script + r'''
(async () => {
  await loadAgriForecast();
  assert.equal(fetchCount, 0);
  assert.match(elements['agri-forecast'].textContent, /latitude/);
  elements['weather-lat'].value = '26.8467';
  elements['weather-lon'].value = '181';
  await loadAgriForecast();
  assert.equal(fetchCount, 0);
  elements['weather-lon'].value = '80.9462';
  await loadAgriForecast();
  assert.match(elements['agri-forecast'].textContent, /उपलब्ध नहीं/);
  fetch = async url => {
    assert.match(url, /api.open-meteo.com/);
    assert.match(url, /timezone=Asia%2FKolkata/);
    return {ok: true, json: async () => ({daily: {time: ['2026-11-21'], temperature_2m_min: [10], temperature_2m_max: [20], precipitation_sum: [0], precipitation_probability_max: [null], wind_speed_10m_max: [5], et0_fao_evapotranspiration: [2]}})};
  };
  await loadAgriForecast();
  const output = elements['agri-forecast'];
  assert.match(output.children[0].textContent, /Open-Meteo/);
  assert.match(output.children[1].children[0].textContent, /0 mm/);
  assert.match(output.children[1].children[0].textContent, /—/);
  let finish;
  fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = loadAgriForecast();
  elements['weather-lat'].value = '';
  await loadAgriForecast();
  finish({ok: true, json: async () => ({daily: {time: ['2026-11-21']}})});
  await pending;
  assert.match(output.textContent, /latitude/);
})().catch(e => { console.error(e); process.exitCode = 1; });
'''
        subprocess.run(['node', '-e', harness], check=True, timeout=20)


if __name__ == '__main__':
    unittest.main()
