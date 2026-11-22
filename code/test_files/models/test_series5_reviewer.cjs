const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');

(async () => {
  const output = fs.mkdtempSync(path.join(os.tmpdir(), 'series5-review-qa-'));
  const root = path.resolve(__dirname, '../../ai_models_datasets/series_5/tools');
  const dataset = process.argv[2] || path.join(os.homedir(), 'sidewalkpilot-labels/series5-12-pilot-v1');
  const reviewer = process.argv[3] || path.join(root, 'review/index.html');
  const errors = [];
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('file://' + reviewer);
    const fixtureManifest=JSON.parse(fs.readFileSync(path.join(dataset,'manifest.json')));
    const fixtureName=fixtureManifest.images[0];
    const fixtureRecord=JSON.parse(fs.readFileSync(path.join(dataset,'records',fixtureName.replace(/\.jpg$/,'.json'))));
    const installationReset=await page.evaluate(({name,hash})=>{
      const request=JSON.parse(document.querySelector('#review-reset-request').textContent);
      if(!request.id)return null;
      const old=JSON.stringify({[name]:{decision:'correct',notes:'Pre-update test review',mask_sha256:hash}});
      localStorage.setItem(request.dataset_key,old);
      localStorage.setItem(request.dataset_key+':class-1',old);
      localStorage.setItem(request.dataset_key+':class-1:position','9');
      return request;
    },{name:fixtureName,hash:fixtureRecord.mask_sha256});
    await page.locator('#load-input').setInputFiles(dataset);
    try {await page.locator('#empty').waitFor({state: 'hidden'});} catch(error) {
      console.error('Reviewer message:', await page.locator('#message').textContent());
      console.error('Page errors:', errors);
      console.error('Selected paths:', await page.evaluate(() => Array.from(document.querySelector('#load-input').files).slice(0,12).map(f=>f.webkitRelativePath)));
      console.error('Record keys:', await page.evaluate(() => Array.from(files.keys()).filter(k=>k.includes('records')).slice(0,3)));
      await page.screenshot({path:path.join(output,'error.png'),fullPage:true});
      throw error;
    }
    assert.equal(await page.locator('#count').textContent(), '/ 200');
    if(installationReset){
      assert.equal(await page.locator('#review-count').textContent(),'0 / 200');
      assert.equal(await page.locator('#position').inputValue(),'1');
      assert.match(await page.locator('#last-action').textContent(),/Previous reviews cleared/);
      assert.equal(await page.evaluate(k=>localStorage.getItem(k),installationReset.dataset_key),null);
      assert.equal(await page.evaluate(k=>localStorage.getItem(k+':applied-reset'),installationReset.dataset_key),installationReset.id);
    }
    assert.equal(await page.locator('.legend-item').count(), 13);
    assert.equal(await page.locator('#scope').inputValue(), 'class-1');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'canvas');
    assert(await page.locator('#focus-only').isChecked());
    assert(await page.locator('#auto-advance').isChecked());
    const waitImage = number => page.waitForFunction(n => document.querySelector('#position').value === String(n) && document.querySelector('#empty').hidden, number, {timeout:8000});
    const legacy = await page.evaluate(() => {
      const value = {schema:'sidewalkpilot-mask-review-v1',dataset_key:datasetKey,decisions:{
        [names[0]]:{decision:'correct',notes:'Legacy whole-mask test review',mask_sha256:current.record.mask_sha256}
      }};
      localStorage.setItem(datasetKey,JSON.stringify(value.decisions));
      return value;
    });
    const legacyPath = path.join(output,'legacy-review.json');
    fs.writeFileSync(legacyPath,JSON.stringify(legacy));
    const samplePixels = () => page.evaluate(() => {
      const c = document.querySelector('canvas'), values = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
      let sum = 0; for(let i=0;i<values.length;i+=100)sum+=values[i]; return sum;
    });
    const overlayPixels = await samplePixels();
    assert(overlayPixels > 0);
    await page.locator('input[value=source]').check();
    if (await page.evaluate(() => current.mask.includes(1))) assert.notEqual(await samplePixels(), overlayPixels);
    await page.locator('input[value=mask]').check();
    assert(await page.evaluate(() => {
      const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
      return current.mask.every((id,i)=>{
        const color=id===1?[38,190,148]:[28,33,34];
        return color.every((v,c)=>pixels[i*4+c]===v);
      });
    }), 'Focused mask must show exactly class 1, not relabel other classes');
    const focusedPixels = await samplePixels();
    await page.locator('#focus-only').uncheck();
    assert.notEqual(await samplePixels(),focusedPixels);
    await page.locator('#focus-only').check();
    await page.screenshot({path: path.join(output, 'desktop-labels.png'), fullPage: true});
    await page.locator('input[value=overlay]').check();
    await page.screenshot({path: path.join(output, 'desktop.png'), fullPage: true});
    await page.locator('#notes').focus();
    await page.keyboard.type('12');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#position').inputValue(),'1');
    assert.equal(await page.locator('#review-count').textContent(),'0 / 200');
    await page.locator('#notes').fill('Automated UI test only; not a research review.');
    await page.locator('#opacity').focus();
    await page.keyboard.press('1');
    await waitImage(2);
    assert.equal(await page.locator('#review-count').textContent(),'1 / 200');
    assert.match(await page.locator('#last-action').textContent(),/Image 1 \/ Class 1: Marked correct/);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#export').click();
    const download = await downloadPromise;
    const exportPath = path.join(output, 'test-review.json');
    await download.saveAs(exportPath);
    const saved = JSON.parse(fs.readFileSync(exportPath));
    assert.equal(saved.schema,'sidewalkpilot-mask-review-v2');
    assert.equal(saved.review_scope.kind,'class');
    assert.deepEqual(saved.review_scope.class_ids,[1]);
    assert.equal(download.suggestedFilename(),'sidewalkpilot-class-1-review.json');
    assert.equal(Object.keys(saved.decisions).length, 1);
    assert.equal(Object.values(saved.decisions)[0].decision, 'correct');
    // Enter must navigate even with a button focused, not activate that button.
    await page.locator('[data-decision=correct]').focus();
    await page.keyboard.press('Enter');
    await waitImage(3);
    assert.equal(await page.locator('#status').textContent(), 'Unreviewed');
    assert.equal(await page.locator('#review-count').textContent(), '1 / 200');
    await page.locator('#next').focus();
    await page.keyboard.press('Enter');
    await waitImage(4);
    await page.keyboard.press('ArrowLeft');
    await waitImage(3);
    await page.keyboard.down('2');
    await waitImage(4);
    await page.keyboard.down('2');
    await page.keyboard.up('2');
    assert.equal(await page.locator('#position').inputValue(),'4');
    assert.equal(await page.locator('#review-count').textContent(),'2 / 200');
    await page.keyboard.press('ArrowLeft');
    await waitImage(3);
    assert.equal(await page.locator('#status').textContent(),'Needs correction');
    await page.locator('#import-input').setInputFiles(exportPath);
    await page.waitForFunction(() => document.querySelector('#message').textContent === 'Review imported');
    assert.equal(await page.locator('#status').textContent(), 'Unreviewed');
    await page.locator('#auto-advance').uncheck();
    await page.keyboard.press('1');
    assert.equal(await page.locator('#position').inputValue(),'3');
    assert.equal(await page.locator('#status').textContent(),'Marked correct');
    await page.locator('[data-decision=unreviewed]').click();
    assert.equal(await page.locator('#status').textContent(),'Unreviewed');
    await page.locator('#position').fill('1');
    await page.locator('#position').press('Enter');
    await waitImage(1);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'canvas');
    assert.equal(await page.locator('#notes').inputValue(), 'Automated UI test only; not a research review.');
    // Existing approvals remain whole-mask decisions, not class-1 decisions.
    await page.locator('#scope').selectOption('all');
    await waitImage(1);
    assert.equal(await page.locator('#notes').inputValue(),'Legacy whole-mask test review');
    assert(!await page.locator('#focus-only').isChecked());
    await page.locator('#import-input').setInputFiles(exportPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Review scope differs'));
    await page.locator('#import-input').setInputFiles(legacyPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported');
    await page.locator('#scope').selectOption('class-1');
    await waitImage(1);
    assert.equal(await page.locator('#notes').inputValue(),'Automated UI test only; not a research review.');
    await page.locator('#import-input').setInputFiles(legacyPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Legacy reviews cover the whole mask'));
    const badHashPath=path.join(output,'wrong-hash.json'), badHash=structuredClone(saved);
    Object.values(badHash.decisions)[0].mask_sha256='not-the-mask';
    fs.writeFileSync(badHashPath,JSON.stringify(badHash));
    await page.locator('#import-input').setInputFiles(badHashPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('mask hash does not match'));
    assert.equal(await page.locator('#review-count').textContent(),'1 / 200');
    await page.locator('#position').fill('3');
    await page.locator('#position').press('Enter');
    await waitImage(3);
    await page.reload();
    await page.locator('#load-input').setInputFiles(dataset);
    await waitImage(3);
    assert.equal(await page.locator('#review-count').textContent(),'1 / 200');
    assert.deepEqual(await page.evaluate(k=>JSON.parse(localStorage.getItem(k)),legacy.dataset_key),legacy.decisions);
    await page.locator('#position').fill('200');
    await page.locator('#position').press('Enter');
    await waitImage(200);
    await page.locator('#canvas').focus();
    await page.keyboard.press('2');
    assert.equal(await page.locator('#position').inputValue(),'200');
    assert.equal(await page.locator('#status').textContent(),'Needs correction');
    assert(await page.locator('#next').isDisabled());
    await page.keyboard.press('Enter');
    await waitImage(200);
    assert.equal(await page.locator('#review-count').textContent(),'2 / 200');
    await page.locator('#position').fill('1');
    await page.locator('#position').press('Enter');
    await waitImage(1);
    for(const width of [390, 768]) {
      await page.setViewportSize({width, height: 844});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({path:path.join(output, `mobile-${width}.png`), fullPage:true});
    }
    const invalidDataset=path.join(output,'invalid-dataset');fs.mkdirSync(invalidDataset);
    fs.writeFileSync(path.join(invalidDataset,'manifest.json'),'{}');
    await page.locator('#load-input').setInputFiles(invalidDataset);
    await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('Missing file'));
    assert.equal(await page.locator('#count').textContent(),'/ 0');
    assert(await page.locator('[data-decision=correct]').isDisabled());
    await page.locator('#load-input').setInputFiles(dataset);
    await page.locator('#empty').waitFor({state:'hidden'});
    await page.locator('#scope').focus();
    await page.keyboard.press('2');
    await waitImage(2);
    assert.equal(await page.evaluate(()=>decisions[names[0]].decision),'needs_correction');
    // Hardware codes cover number-pad keys and keyboards whose number-row symbols differ.
    await page.locator('#canvas').dispatchEvent('keydown',{key:'End',code:'Numpad1',bubbles:true});
    await waitImage(3);
    assert.equal(await page.evaluate(()=>decisions[names[1]].decision),'correct');
    await page.locator('#canvas').dispatchEvent('keydown',{key:'\u00e9',code:'Digit2',bubbles:true});
    await waitImage(4);
    assert.equal(await page.evaluate(()=>decisions[names[2]].decision),'needs_correction');
    await page.locator('#notes').focus();
    await page.keyboard.type('12');
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'canvas');
    await page.keyboard.press('Control+1');
    assert.equal(await page.locator('#position').inputValue(),'4');

    // Clearing reviews must not affect other datasets or clear anything on cancellation.
    await page.evaluate(()=>localStorage.setItem('sp-review:another-dataset','preserve'));
    const reviewedBeforeClear=await page.locator('#review-count').textContent();
    page.once('dialog',dialog=>dialog.dismiss());
    await page.locator('#clear-reviews').click();
    assert.equal(await page.locator('#review-count').textContent(),reviewedBeforeClear);
    page.once('dialog',dialog=>dialog.accept());
    await page.locator('#clear-reviews').click();
    await waitImage(1);
    assert.equal(await page.locator('#review-count').textContent(),'0 / 200');
    assert.equal(await page.locator('#notes').inputValue(),'');
    assert.equal(await page.evaluate(()=>localStorage.getItem('sp-review:another-dataset')),'preserve');
    assert.equal(await page.evaluate(()=>localStorage.getItem(datasetKey)),null);
    assert.equal(await page.evaluate(()=>localStorage.getItem(datasetKey+':class-1')),null);
    await page.locator('#scope').selectOption('all');
    await waitImage(1);
    assert.equal(await page.locator('#review-count').textContent(),'0 / 200');
    await page.locator('#scope').selectOption('class-1');
    await waitImage(1);

    const resetRequest=await page.evaluate(value=>{
      localStorage.setItem(datasetKey,JSON.stringify(value.decisions));
      localStorage.setItem(datasetKey+':class-1',JSON.stringify(value.decisions));
      const request={id:'test-authorized-reset',dataset_key:datasetKey};
      document.querySelector('#review-reset-request').textContent=JSON.stringify(request);
      return request;
    },legacy);
    // Reopening the folder applies the requested reset once, not on every load.
    await page.locator('#load-input').evaluate(input=>{input.value='';});
    await page.locator('#load-input').setInputFiles(dataset);
    await waitImage(1);
    assert.equal(await page.locator('#review-count').textContent(),'0 / 200');
    assert.match(await page.locator('#last-action').textContent(),/Previous reviews cleared/);
    assert.equal(await page.evaluate(()=>localStorage.getItem(datasetKey)),null);
    await page.keyboard.press('1');
    await waitImage(2);
    await page.reload();
    await page.evaluate(request=>document.querySelector('#review-reset-request').textContent=JSON.stringify(request),resetRequest);
    await page.locator('#load-input').setInputFiles(dataset);
    await waitImage(2);
    assert.equal(await page.locator('#review-count').textContent(),'1 / 200');
    // A request aimed at another dataset cannot clear this one.
    await page.evaluate(()=>document.querySelector('#review-reset-request').textContent=JSON.stringify({id:'other-reset',dataset_key:'sp-review:another-dataset'}));
    await page.locator('#load-input').evaluate(input=>{input.value='';});
    await page.locator('#load-input').setInputFiles(dataset);
    await waitImage(2);
    assert.equal(await page.locator('#review-count').textContent(),'1 / 200');
    assert.equal(await page.evaluate(()=>localStorage.getItem('sp-review:another-dataset')),'preserve');
    assert.deepEqual(errors, []);
    const server = spawn('python3', [path.join(root,'review_masks.py'),dataset,'--no-browser'], {stdio:['pipe','pipe','pipe']});
    const stopped = new Promise(resolve=>server.on('exit',resolve));
    try {
      const url = await new Promise((resolve,reject)=>{
        let text='';const timeout=setTimeout(()=>reject(Error('Review server startup timeout')),10000);
        server.on('error',error=>{clearTimeout(timeout);reject(error);});
        server.stdout.on('data',chunk=>{text+=chunk;const found=text.match(/http:\/\/127\.0\.0\.1:\d+\/\?terminal=1/);if(found){clearTimeout(timeout);resolve(found[0]);}});
        server.stderr.on('data',chunk=>console.error(String(chunk)));
      });
      const terminalPage=await browser.newPage({viewport:{width:1440,height:1000}});
      terminalPage.on('pageerror',error=>errors.push(error.message));
      await terminalPage.goto(url);
      await terminalPage.locator('#empty').waitFor({state:'hidden'});
      server.stdin.write('\n');
      await terminalPage.waitForFunction(()=>document.querySelector('#position').value==='2'&&document.querySelector('#empty').hidden);
      assert.equal(await terminalPage.locator('#review-count').textContent(),'0 / 200');
      server.stdin.write('b\n');
      await terminalPage.waitForFunction(()=>document.querySelector('#position').value==='1'&&document.querySelector('#empty').hidden);
      const response=await terminalPage.request.get(new URL('/dataset/%2Fetc%2Fpasswd',url).href);
      assert.equal(response.status(),404);
      await terminalPage.close();
    } finally {server.stdin.write('q\n');await stopped;}
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({passed:true, screenshots:output, checks:'class-1 exact pixels, three modes, 1/2 from slider/select/button focus, keypad/non-US keys, Enter skips, key repeats ignored, notes safe, auto-advance, last-image bounds, scoped export/import, legacy reviews preserved, mask hash check, resume position, manual reset/cancel, targeted one-time reset, desktop/mobile layout, real terminal Enter/back/quit, path traversal blocked'}));
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode=1;});
