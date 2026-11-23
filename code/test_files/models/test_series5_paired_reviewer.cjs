const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  const count = manifest.count;
  assert(Number.isInteger(count) && count >= 4);
  assert(!JSON.stringify(manifest).match(/gsam2|facebook|concrete sidewalk/i));
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'sidewalkpilot-paired-qa-'));
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('file://' + path.join(root, 'index.html'));
    const ready = n => page.waitForFunction(n => !document.body.classList.contains('loading') && document.querySelector('#position').value === String(n), n);
    await ready(1);
    assert.equal(await page.locator('#progress').textContent(), `0 / ${count} pairs`);
    if (process.env.CHECK_ALL_MASKS === '1') {
      for (let n=1;n<=manifest.count;n++) {
        await page.locator('#position').fill(String(n)); await page.locator('#position').press('Tab'); await ready(n);
        const counts = await page.evaluate(() => Object.fromEntries(['A','B'].map(side => {
          const c=document.getElementById('canvas-'+side), pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
          let positive=0; for(let i=3;i<pixels.length;i+=4)if(pixels[i])positive++;
          return [side,positive];
        })));
        for(const side of ['A','B']) {
          const rle=manifest.pairs[n-1].candidates[side].rle;
          let value=rle.first, expected=0;
          for(const length of rle.lengths){if(value)expected+=length;value=1-value;}
          assert.equal(counts[side],expected,`Pair ${n} ${side} mask pixels`);
        }
      }
      await page.locator('#position').fill('1'); await page.locator('#position').press('Tab'); await ready(1);
    }
    assert(await page.evaluate(() => ['A','B'].every(side => {
      const image = document.getElementById('image-' + side), canvas = document.getElementById('canvas-' + side);
      return image.naturalWidth === 1280 && image.naturalHeight === 720 && canvas.width === 1280 &&
        canvas.getContext('2d').getImageData(0,0,1280,720).data.some((v,i) => i % 4 === 3 && v > 0);
    })));
    await page.keyboard.press('1');
    assert.equal(await page.locator('.side[data-side=B]').getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('#position').inputValue(), '1');
    await page.keyboard.press('2');
    const levels = await page.locator('#correction-dialog').count() > 0;
    if(levels) {
      assert(await page.locator('#correction-dialog').evaluate(e => e.open));
      assert.equal(await page.locator('#position').inputValue(), '1');
      await page.keyboard.press('Enter');
      assert(await page.locator('#correction-dialog').evaluate(e => e.open));
      await page.keyboard.press('1');
    }
    await ready(2);
    assert.equal(await page.locator('#progress').textContent(), `1 / ${count} pairs`);
    await page.keyboard.press('Enter'); await ready(3);
    assert.equal(await page.locator('#decisions-count').textContent(), `2 / ${count * 2} decisions`);
    await page.locator('#notes').fill('123 Enter is only text here');
    assert.equal(await page.locator('#position').inputValue(), '3');
    assert.equal(await page.locator('#decisions-count').textContent(), `2 / ${count * 2} decisions`);
    await page.locator('.side[data-side=A]').click();
    await page.keyboard.press('3');
    assert.equal(await page.locator('#status-A').textContent(), 'Uncertain');
    assert.equal(await page.locator('.side[data-side=B]').getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('1'); await ready(4);
    if (process.env.CHECK_TIMING === '1') {
      await page.bringToFront(); await page.waitForTimeout(1150);
    }
    const downloadPromise = page.waitForEvent('download'); await page.locator('#export').click();
    const download = await downloadPromise;
    const reviewPath = path.join(out, 'synthetic-ui-test-only.json');
    await download.saveAs(reviewPath);
    const review = JSON.parse(fs.readFileSync(reviewPath));
    assert.equal(review.complete, false); assert.equal(review.package_id, manifest.package_id);
    assert.equal(review.decisions['pair-001'].A.decision, 'correct');
    assert.equal(review.decisions['pair-001'].B.decision, 'needs_correction');
    if(levels)assert.equal(review.decisions['pair-001'].B.correction_level,1);
    assert.equal(review.decisions['pair-003'].A.notes, '123 Enter is only text here');
    assert(!review.decisions['pair-002']);
    assert(!JSON.stringify(review).match(/gsam2|facebook|concrete sidewalk/i));
    if (process.env.CHECK_TIMING === '1') {
      assert(review.inspection_active_seconds['pair-004'].A > 0);
      const invalidTiming={...review,inspection_active_seconds:{'pair-001':{A:-1}}};
      await page.locator('#import-file').setInputFiles({name:'bad-time.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalidTiming))});
      await page.waitForFunction(() => document.querySelector('#message').textContent.includes('Invalid inspection duration'));
    }
    await page.reload(); await ready(4);
    assert.equal(await page.locator('#progress').textContent(), `2 / ${count} pairs`);
    await page.locator('#zoom-in').click(); await page.locator('#zoom-in').click();
    assert.equal(await page.locator('#zoom-value').textContent(), '200%');
    assert(await page.locator('#stage-A').evaluate(e => e.scrollWidth > e.clientWidth));
    await page.locator('#stage-A').evaluate(e => { e.scrollLeft = 150; e.scrollTop = 60; });
    await page.waitForFunction(() => document.querySelector('#stage-B').scrollLeft === 150);
    await page.locator('#fit').click();
    await page.locator('input[value=source]').check();
    assert.equal(await page.locator('#canvas-A').evaluate(e => getComputedStyle(e).display), 'none');
    await page.locator('input[value=mask]').check();
    assert(await page.locator('#canvas-A').evaluate(e => e.getContext('2d').getImageData(0,0,e.width,e.height).data.every((v,i) => i % 4 !== 3 || v === 255)));
    await page.locator('input[value=overlay]').check();
    await page.screenshot({path: path.join(out, 'desktop.png'), fullPage: true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path: path.join(out, 'mobile.png'), fullPage: true});
    const invalid = {...review, package_id:'wrong-package'};
    await page.locator('#import-file').setInputFiles({name:'wrong.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
    await page.waitForFunction(() => document.querySelector('#message').textContent.includes('another package'));
    assert.equal(await page.locator('#progress').textContent(), `2 / ${count} pairs`);
    page.once('dialog', d => d.dismiss()); await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(), `2 / ${count} pairs`);
    page.once('dialog', d => d.accept()); await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(), `0 / ${count} pairs`);
    await page.locator('#import-file').setInputFiles(reviewPath);
    await page.waitForFunction(() => document.querySelector('#message').textContent === 'Decisions imported.');
    assert.equal(await page.locator('#progress').textContent(), `2 / ${count} pairs`);
    await page.locator('#position').fill(String(count)); await page.locator('#position').press('Tab'); await ready(count);
    await page.locator('.side[data-side=A]').click(); await page.keyboard.press('1'); await page.keyboard.press('2');
    if(levels)await page.keyboard.press('3');
    assert.equal(await page.locator('#position').inputValue(), String(count));
    assert.equal(await page.locator('#progress').textContent(), `3 / ${count} pairs`);
    assert(await page.locator('#next').isDisabled());
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed:true, screenshots:out, synthetic_review:reviewPath,
      checks:'offline source+mask pixels, blinded metadata, 1/2/3/Enter, independent A/B decisions, skip, notes, persistence, zoom/pan, export/import identity, clear confirmation, final pair, desktop/mobile'}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
