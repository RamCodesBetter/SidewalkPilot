const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const dataset = process.argv[2];
  assert(dataset, 'Pass an extracted class-1 diagnostic package');
  const manifest = JSON.parse(fs.readFileSync(path.join(dataset, 'manifest.json')));
  assert.deepEqual(manifest.annotation_scope.class_ids, [1]);
  assert(manifest.images.length >= 4);
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'series5-diagnostic-qa-'));
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  const errors = [];
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('file://' + path.resolve(dataset, 'review/index.html'));
    await page.locator('#load-input').setInputFiles(dataset);
    const waitImage = n => page.waitForFunction(number =>
      document.querySelector('#empty').hidden && document.querySelector('#position').value === String(number), n);
    await waitImage(1);
    assert.equal(await page.locator('#count').textContent(), '/ ' + manifest.images.length);
    assert(await page.locator('#scope').isDisabled());
    assert.equal(await page.locator('#scope').inputValue(), 'class-1');
    assert.match(await page.locator('header small').textContent(), /AI-assisted prompts/);
    assert(await page.evaluate(() => {
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      return data.some((value, i) => i % 4 !== 3 && value > 0);
    }));
    await page.keyboard.press('1'); await waitImage(2);
    await page.keyboard.press('2'); await waitImage(3);
    await page.keyboard.press('Enter'); await waitImage(4);
    assert.equal(await page.locator('#review-count').textContent(), '2 / ' + manifest.images.length);
    const promise = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await promise;
    const exportPath = path.join(output, 'ui-test-only.json');
    await download.saveAs(exportPath);
    const exported = JSON.parse(fs.readFileSync(exportPath));
    assert.deepEqual(exported.review_scope.class_ids, [1]);
    assert.equal(exported.decisions[manifest.images[0]].decision, 'correct');
    assert.equal(exported.decisions[manifest.images[1]].decision, 'needs_correction');
    await page.screenshot({path: path.join(output, 'desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path: path.join(output, 'mobile.png'), fullPage: true});
    await page.reload();
    await page.locator('#load-input').setInputFiles(dataset);
    await waitImage(4);
    assert.equal(await page.locator('#review-count').textContent(), '2 / ' + manifest.images.length);
    const withheld = manifest.images.findIndex(name => {
      const record = JSON.parse(fs.readFileSync(path.join(dataset, 'records', name.replace(/\.jpg$/, '.json'))));
      return Boolean(record.annotation?.abstain);
    });
    if (withheld !== -1) {
      await page.locator('#position').fill(String(withheld + 1));
      await page.locator('#position').press('Enter');
      await waitImage(withheld + 1);
      assert.match(await page.locator('#flags').textContent(), /Annotation withheld:/);
      assert.equal(await page.locator('#status').textContent(), 'Unreviewed');
      assert.equal(await page.locator('#review-count').textContent(), '2 / ' + manifest.images.length);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path: path.join(output, 'mobile-uncertain.png'), fullPage: true});
    }
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed: true, screenshots: output, count: manifest.images.length,
      checks: 'class-1 scope locked, AI assistance visible, nonblank canvas, 1/2/Enter, scoped export, persistent review, desktop/mobile layout'}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
