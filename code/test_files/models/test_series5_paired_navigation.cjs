const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  const key = 'sidewalkpilot:paired:' + manifest.package_id;
  const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const ready = n => page.waitForFunction(n => !document.body.classList.contains('loading') &&
      document.querySelector('#position').value === String(n), n);
    const record = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)), key);
    await page.goto('file://' + path.join(root, 'index.html'));
    let cases = 0;
    for(const auto of [false,true]) for(const existingB of [false,true]) {
      for(const decision of ['correct','uncertain','needs_correction']) {
        const seed = {index:0, decisions:{}, inspectionTimes:{}};
        if(existingB) seed.decisions['pair-001'] = {B:{decision:'correct', effort:'minor',
          notes:'Preserve this B rating', mask_sha256:manifest.pairs[0].candidates.B.mask_sha256}};
        await page.evaluate(({key,seed}) => localStorage.setItem(key,JSON.stringify(seed)), {key,seed});
        await page.reload(); await ready(1);
        await page.locator('#auto').setChecked(auto);
        await page.locator('.side[data-side="A"]').click();
        if(existingB) await page.locator(`.decisions[data-side="A"] [data-decision="${decision}"]`).click();
        else await page.keyboard.press({correct:'1',needs_correction:'2',uncertain:'3'}[decision]);
        if(decision === 'needs_correction') {
          assert(await page.locator('#correction-dialog').evaluate(e => e.open));
          assert.equal((await record()).active,'A');
          await ready(1);
          if(existingB) await page.locator('[data-level="2"]').click();
          else await page.keyboard.press('1');
        }
        await ready(1);
        assert.equal((await record()).active, 'B', `A must select B: ${JSON.stringify({auto,existingB,decision})}`);
        assert.equal(await page.locator('.side[data-side="B"]').getAttribute('aria-pressed'),'true');
        assert.equal(await page.evaluate(() => document.activeElement.id),'stage-B');
        if(existingB) assert.deepEqual((await record()).decisions['pair-001'].B,seed.decisions['pair-001'].B);
        else assert.equal((await record()).decisions['pair-001'].B,undefined);
        await page.keyboard.press('2');
        assert.equal(await page.locator('#correction-context').textContent(),'Candidate B / image 1 of 200');
        await page.keyboard.press('3'); await ready(auto ? 2 : 1);
        assert.equal((await record()).decisions['pair-001'].B.correction_level,3);
        cases++;
      }
    }
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,cases,checks:'A to B for all decisions, auto on/off, saved B, keyboard/click, focus, next image after B'}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
