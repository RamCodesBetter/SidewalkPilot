const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const data = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  const key = 'sidewalkpilot:paired:' + data.package_id;
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'sidewalkpilot-levels-qa-'));
  const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}, acceptDownloads:true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const legacy = {decisions:{'pair-001':{}}, index:0, inspectionTimes:{}};
    for(const side of ['A','B']) legacy.decisions['pair-001'][side] = {
      decision:side === 'A' ? 'correct' : 'needs_correction',
      notes:'Existing notes ' + side, effort:'major',
      mask_sha256:data.pairs[0].candidates[side].mask_sha256,
    };
    await page.addInitScript(({key,legacy}) => {
      if(!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(legacy));
    }, {key,legacy});
    await page.goto('file://' + path.join(root,'index.html'));
    const ready = n => page.waitForFunction(n => !document.body.classList.contains('loading') &&
      document.querySelector('#position').value === String(n), n);
    const stored = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)), key);
    const select = side => page.locator(`.side[data-side="${side}"]`).click();
    const isOpen = () => page.locator('#correction-dialog').evaluate(e => e.open);
    await ready(1);
    assert.deepEqual((await stored()).decisions, legacy.decisions);
    assert.equal(await page.locator('#status-B').textContent(), 'Needs correction');
    await page.locator('#auto').uncheck();
    await select('B');
    await page.keyboard.press('2');
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowRight');
    await page.evaluate(() => document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {
      key:'2', repeat:true, bubbles:true,
    })));
    assert(await isOpen());
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, null);
    await page.keyboard.press('Escape');
    assert(!(await isOpen()));
    await ready(1);
    assert.equal((await stored()).decisions['pair-001'].B.notes, 'Existing notes B');
    for(const [level,label] of [[1,'Minor'],[2,'Moderate'],[3,'Major']]) {
      await page.keyboard.press('2');
      assert(await isOpen());
      if(level === 2) await page.locator('[data-level="2"]').click();
      else await page.keyboard.press(String(level));
      assert(!(await isOpen()));
      await ready(1);
      assert.equal((await stored()).decisions['pair-001'].B.correction_level, level);
      assert.equal((await stored()).decisions['pair-001'].A.correction_level, undefined);
      assert.equal(await page.locator('#status-B').textContent(), label + ' fixes');
    }
    await page.keyboard.press('2');
    await page.locator('#close-correction').click();
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, 3);
    await ready(1);
    await page.keyboard.press('1');
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, null);
    await page.keyboard.press('2'); await page.keyboard.press('2');
    await page.keyboard.press('3');
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, null);
    await page.keyboard.press('2'); await page.keyboard.press('2');
    await page.locator('#effort').selectOption('minor');
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, 2);
    await page.locator('#notes').fill('123 stays in notes');
    await page.locator('#notes').press('2');
    assert(!(await isOpen()));
    assert.equal((await stored()).decisions['pair-001'].B.decision, 'needs_correction');
    await page.reload(); await ready(1);
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, 2);
    const pending = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await pending;
    const reviewPath = path.join(out,'synthetic-levels-test-only.json');
    await download.saveAs(reviewPath);
    const review = JSON.parse(fs.readFileSync(reviewPath));
    assert.equal(review.review_ui_version, 'paired-correction-levels-v2');
    assert.equal(review.decisions['pair-001'].B.correction_level, 2);
    for(const level of [0,4,'1',true]) {
      const invalid = structuredClone(review);
      invalid.decisions['pair-001'].B.correction_level = level;
      await page.locator('#import-file').setInputFiles({name:'invalid.json',mimeType:'application/json',
        buffer:Buffer.from(JSON.stringify(invalid))});
      await page.waitForFunction(() => document.querySelector('#message').textContent === 'Invalid correction level');
      assert.equal((await stored()).decisions['pair-001'].B.correction_level, 2);
    }
    page.once('dialog', d => d.accept()); await page.locator('#clear').click();
    await page.locator('#import-file').setInputFiles(reviewPath);
    await page.waitForFunction(() => document.querySelector('#message').textContent === 'Decisions imported.');
    assert.equal((await stored()).decisions['pair-001'].B.correction_level, 2);
    await page.locator('#next').click(); await ready(2);
    await select('B'); await page.keyboard.press('2');
    assert(await isOpen()); await ready(2);
    await page.keyboard.press('1');
    assert.equal(await page.locator('.side[data-side="A"]').getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('2');
    await ready(2);
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    for(const width of [390,320]) {
      await page.setViewportSize({width,height:844});
      assert(await page.locator('#correction-dialog').evaluate(e => {
        const r=e.getBoundingClientRect();
        return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight &&
          e.scrollWidth <= e.clientWidth;
      }));
      await page.screenshot({path:path.join(out,`mobile-${width}.png`),fullPage:true});
    }
    await page.keyboard.press('3'); await ready(2);
    assert.equal(await page.locator('.side[data-side="B"]').getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('2'); await page.keyboard.press('1'); await ready(3);
    assert.equal((await stored()).decisions['pair-002'].A.correction_level, 3);
    assert.equal((await stored()).decisions['pair-002'].B.correction_level, 1);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed:true,screenshots:out,
      checks:'all levels, keyboard/mouse, cancellation, repeat guard, auto advance, independent sides, old storage, notes, export/import, invalid levels, responsive dialog'}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
