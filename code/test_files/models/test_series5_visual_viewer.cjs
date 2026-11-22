const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  assert.equal(manifest.count, 30);
  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'sidewalkpilot-visual-qa-'));
  const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}, acceptDownloads:true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('file://' + path.join(root, 'index.html'));
    const ready = n => page.waitForFunction(n => !document.body.classList.contains('loading') && document.querySelector('#position').value === String(n), n);
    const go = async n => { await page.locator('#position').fill(String(n)); await page.locator('#position').press('Tab'); await ready(n); };
    await ready(1);
    assert.equal(await page.locator('#progress').textContent(), '0 / 90 ratings');
    assert.equal(await page.locator('.pane').count(), 4);
    for (let n=1;n<=30;n++) {
      if(n>1) await go(n);
      const stats = await page.evaluate(() => {
        const expected = window.COMPARISON_DATA.frames[Number(document.querySelector('#position').value)-1];
        return Object.fromEntries(['gsam2','sam3','codex'].map(method => {
          const c=document.querySelector('#canvas-'+method), img=document.querySelector('#image-'+method);
          const rgba=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
          let positive=0, uncertain=0;
          for(let i=0;i<rgba.length;i+=4) {
            // Canvas alpha premultiplication can round RGB values by one.
            if(rgba[i+3] && rgba[i+1]>rgba[i] && rgba[i+1]>rgba[i+2]) positive++;
            else if(rgba[i+3]) uncertain++;
          }
          return [method,{width:img.naturalWidth,height:img.naturalHeight,positive,uncertain,
            expected:expected.methods[method],source:img.getAttribute('src')}];
        }));
      });
      for(const [method,s] of Object.entries(stats)) {
        assert.equal(s.width, 1280); assert.equal(s.height,720);
        assert.equal(s.positive, s.expected.positive_pixels, `positive ${n} ${method}`);
        assert.equal(s.uncertain, s.expected.uncertain_pixels, `uncertain ${n} ${method}`);
        assert.equal(s.source, manifest.frames[n-1].image);
      }
    }
    assert(await page.locator('#next').isDisabled());
    await go(1);
    await page.locator('[data-method=codex]').click();
    await page.keyboard.press('1');
    assert.equal(await page.locator('#status-codex').textContent(),'Correct');
    assert.equal(await page.locator('#status-gsam2').textContent(),'Unreviewed');
    assert.equal(await page.locator('#position').inputValue(),'1');
    await page.locator('[data-method=gsam2]').click(); await page.keyboard.press('2');
    assert(await page.locator('#correction-dialog').isVisible());
    await page.keyboard.press('1');
    assert.equal(await page.locator('#status-gsam2').textContent(),'Minor fixes');
    assert(!(await page.locator('#correction-dialog').isVisible()));
    await page.locator('[data-method=sam3]').click(); await page.keyboard.press('3');
    assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    await page.keyboard.press('Enter'); await ready(2);
    await page.locator('#notes').fill('123 is text, not ratings');
    await page.locator('#notes').press('Enter');
    assert.equal(await page.locator('#position').inputValue(),'2');
    assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    await page.locator('[data-method=codex]').click();
    await page.keyboard.press('ArrowLeft'); await ready(1);
    const downloadPromise=page.waitForEvent('download'); await page.locator('#export').click();
    const download=await downloadPromise, reviewPath=path.join(out,'synthetic-ui-test-only.json');
    await download.saveAs(reviewPath);
    const review=JSON.parse(fs.readFileSync(reviewPath));
    assert.equal(review.package_id,manifest.package_id);
    assert.equal(review.reviews['image-01'].methods.codex.decision,'correct');
    assert.equal(review.reviews['image-01'].methods.gsam2.decision,'needs_correction');
    assert.equal(review.reviews['image-01'].methods.gsam2.correction_level,1);
    assert.equal(review.reviews['image-01'].methods.sam3.decision,'uncertain');
    assert.equal(review.reviews['image-02'].notes,'123 is text, not ratings\n');
    await page.reload(); await ready(1);
    assert.equal(await page.locator('#status-gsam2').textContent(),'Minor fixes');
    assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    await page.locator('#zoom-in').click(); await page.locator('#zoom-in').click();
    assert.equal(await page.locator('#zoom-value').textContent(),'200%');
    await page.locator('#stage-original').evaluate(e=>{e.scrollLeft=150;e.scrollTop=60;});
    await page.waitForFunction(()=>['gsam2','sam3','codex'].every(m=>document.querySelector('#stage-'+m).scrollLeft>140));
    await page.locator('#fit').click();
    await page.locator('label').filter({has:page.locator('input[value=source]')}).click();
    assert.equal(await page.locator('#canvas-codex').evaluate(e=>getComputedStyle(e).display),'none');
    await page.locator('label').filter({has:page.locator('input[value=mask]')}).click();
    assert(await page.locator('#canvas-codex').evaluate(e=>e.getContext('2d').getImageData(0,0,e.width,e.height).data.every((v,i)=>i%4!==3||v===255)));
    await page.locator('label').filter({has:page.locator('input[value=overlay]')}).click();
    await page.locator('#opacity').fill('0');
    assert(await page.locator('#canvas-codex').evaluate(e=>e.getContext('2d').getImageData(0,0,e.width,e.height).data.every((v,i)=>i%4!==3||v===0)));
    await page.locator('#opacity').fill('40');
    await page.locator('button[data-layout=columns]').click();
    assert(await page.locator('#panes').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length===4));
    await page.screenshot({path:path.join(out,'columns.png'),fullPage:true});
    await page.locator('button[data-layout=focus]').click();
    assert.equal(await page.locator('.pane:visible').count(),1);
    assert(await page.locator('#pane-codex').isVisible());
    await page.locator('#method').selectOption('gsam2');
    assert(await page.locator('#pane-gsam2').isVisible());
    await page.locator('button[data-layout=grid]').click();
    await page.locator('[data-method=codex]').click();
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    for(const width of [768,390]) {
      await page.setViewportSize({width,height:844});
      await page.screenshot({path:path.join(out,width===390?'mobile.png':'tablet.png'),fullPage:true});
      const overflow = await page.evaluate(()=>Array.from(document.querySelectorAll('body *')).filter(e=>{
        const r=e.getBoundingClientRect();return r.width>0&&r.right>innerWidth+1;
      }).map(e=>({tag:e.tagName,id:e.id,class:e.className,right:e.getBoundingClientRect().right})));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),JSON.stringify({width,overflow}));
      assert(await page.locator('.pane-heading').evaluateAll(headings=>headings.every(e=>{
        const [a,b]=e.children, x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return x.right<=y.left;
      })));
      await page.screenshot({path:path.join(out,width===390?'mobile.png':'tablet.png'),fullPage:true});
    }
    for(const invalid of [{...review,package_id:'wrong'}, {...review,reviews:{'image-01':{...review.reviews['image-01'],methods:{codex:{decision:'correct',sha256:'wrong'}}}}}]) {
      await page.locator('#import-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
      await page.waitForFunction(()=>document.querySelector('#message').textContent.length>0);
      assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    }
    page.once('dialog',d=>d.dismiss()); await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    page.once('dialog',d=>d.accept()); await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(),'0 / 90 ratings');
    await page.locator('#import-file').setInputFiles(reviewPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported.');
    assert.equal(await page.locator('#progress').textContent(),'3 / 90 ratings');
    await go(30); await page.locator('[data-method=codex]').click();await page.keyboard.press('1');
    await page.keyboard.press('Enter');await ready(30);
    assert.equal(await page.locator('#progress').textContent(),'4 / 90 ratings');
    for(const [level,label] of [[1,'Minor fixes'],[2,'Moderate fixes'],[3,'Major fixes']]) {
      await page.keyboard.press('2');
      await page.keyboard.press(String(level));
      assert.equal(await page.locator('#status-codex').textContent(),label);
      assert.equal(await page.locator('#position').inputValue(),'30');
      await page.reload();await ready(30);
      assert.equal(await page.locator('#status-codex').textContent(),label);
      await page.locator('[data-method=codex]').click();
    }
    await page.keyboard.press('2');
    assert(await page.locator('#correction-dialog').isVisible());
    assert(await page.locator('#correction-dialog').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}));
    await page.screenshot({path:path.join(out,'mobile-correction-level.png'),fullPage:true});
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#status-codex').textContent(),'Major fixes');
    await page.locator('[data-decision=needs_correction]').click();
    await page.locator('[data-level="2"]').click();
    assert.equal(await page.locator('#status-codex').textContent(),'Moderate fixes');
    await page.keyboard.press('1');
    assert.equal(await page.locator('#status-codex').textContent(),'Correct');
    const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('sp-three-method:'+window.COMPARISON_DATA.package_id)));
    assert(!('correction_level' in saved.reviews['image-30'].methods.codex));
    const legacy=JSON.parse(JSON.stringify(review));delete legacy.reviews['image-01'].methods.gsam2.correction_level;
    page.once('dialog',d=>d.accept());
    await page.locator('#import-file').setInputFiles({name:'legacy.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(legacy))});
    await go(1);
    assert.equal(await page.locator('#status-gsam2').textContent(),'Needs correction');
    const invalidLevel=JSON.parse(JSON.stringify(review));invalidLevel.reviews['image-01'].methods.gsam2.correction_level=4;
    await page.locator('#import-file').setInputFiles({name:'invalid-level.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalidLevel))});
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Invalid correction level.');
    assert.equal(await page.locator('#status-gsam2').textContent(),'Needs correction');
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,screenshots:out,checks:'all 90 masks exact pixels + 30 sources, independent ratings, keyboard, notes, storage, export/import identities, confirmation, last image, layouts, zoom/pan, opacity, desktop/tablet/mobile'},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
