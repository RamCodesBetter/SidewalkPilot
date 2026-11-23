const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

function expectedMetrics(frame) {
  const decode=rle=>{const result=[];for(let i=0;i<rle.length;i+=2)for(let n=0;n<rle[i+1];n++)result.push(rle[i]);return result;};
  const prediction=decode(frame.prediction.rle),reference=decode(frame.reference.rle);
  const counts=[0,0,0,0];
  for(let i=0;i<prediction.length;i++)if(reference[i]!==255)counts[2*reference[i]+prediction[i]]++;
  const [tn,fp,fn,tp]=counts, binary=frame.supervision==='binary-reference';
  const percent=(a,b)=>b?(100*a/b).toFixed(2)+'%':'N/A';
  return {p:binary?percent(tp,tp+fp):'N/A',r:percent(tp,tp+fn),f1:binary?percent(2*tp,2*tp+fp+fn):'N/A'};
}

(async () => {
  const root=path.resolve(process.argv[2]), manifest=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
  const out=fs.mkdtempSync(path.join(os.tmpdir(),'sidewalkpilot-model-viewer-'));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:960},acceptDownloads:true});
    const errors=[], requests=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    const ready=n=>page.waitForFunction(n=>!document.body.classList.contains('loading')&&document.querySelector('#position').value===String(n),n);
    const go=async n=>{await page.locator('#position').fill(String(n));await page.locator('#position').press('Tab');await ready(n);};
    await ready(1);
    assert.equal(await page.locator('#progress').textContent(),`0 / ${manifest.count} reviewed`);
    assert.equal(await page.locator('.pane:visible').count(),2);
    await page.locator('#reference').check();
    assert.equal(await page.locator('.pane:visible').count(),3);
    for(let n=1;n<=manifest.count;n++) {
      if(n>1)await go(n);
      const inspected=await page.evaluate(()=>{
        const f=window.MODEL_REVIEW_DATA.frames[Number(document.querySelector('#position').value)-1];
        return ['prediction','reference'].map(side=>{
          const canvas=document.querySelector('#canvas-'+side), img=document.querySelector('#image-'+side);
          const values=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
          let positive=0,ignored=0;
          for(let i=0;i<values.length;i+=4)if(values[i+3]){if(values[i+1]>values[i]&&values[i+1]>values[i+2])positive++;else ignored++;}
          return {side,positive,ignored,expected:f[side],source:img.getAttribute('src'),width:img.naturalWidth,height:img.naturalHeight};
        });
      });
      for(const item of inspected) {
        assert.equal(item.source,manifest.frames[n-1].image);
        assert.equal(item.width,manifest.frames[n-1].size[0]);assert.equal(item.height,manifest.frames[n-1].size[1]);
        assert.equal(item.positive,item.expected.positive_pixels,`positive ${n} ${item.side}`);
        assert.equal(item.ignored,item.expected.ignored_pixels,`ignored ${n} ${item.side}`);
      }
      const expected=expectedMetrics(manifest.frames[n-1]);
      for(const metric of ['p','r','f1'])assert.equal(await page.locator('#metric-'+metric).textContent(),expected[metric],`${metric} on image ${n}`);
      assert.equal(await page.locator('#recall-label').textContent(),manifest.frames[n-1].supervision==='binary-reference'?'Recall':'Known sidewalk');
      if(n%10===0)console.log(`Verified displayed pixels: ${n}/${manifest.count}`);
    }
    assert(await page.locator('#next').isDisabled());
    await go(1);await page.locator('#reference').uncheck();
    await page.keyboard.press('1');
    assert.equal(await page.locator('#rating').textContent(),'Correct');
    await page.keyboard.press('Enter');await ready(2);
    for(const [level,label] of [[1,'Minor fixes'],[2,'Moderate fixes'],[3,'Major fixes']]) {
      await page.keyboard.press('2');assert(await page.locator('#correction-dialog').isVisible());
      await page.keyboard.press(String(level));assert.equal(await page.locator('#rating').textContent(),label);
      assert.equal(await page.locator('#position').inputValue(),'2');
    }
    await page.keyboard.press('2');await page.keyboard.press('Escape');
    assert.equal(await page.locator('#rating').textContent(),'Major fixes');
    await page.keyboard.press('Enter');await ready(3);await page.keyboard.press('3');
    assert.equal(await page.locator('#rating').textContent(),'Uncertain');
    await page.locator('#notes').fill('Test note: 123');await page.locator('#notes').press('Enter');
    assert.equal(await page.locator('#position').inputValue(),'3');
    assert.equal(await page.locator('#progress').textContent(),`3 / ${manifest.count} reviewed`);
    const exporting=page.waitForEvent('download');await page.locator('#export').click();const download=await exporting;
    const reviewPath=path.join(out,'synthetic-review.json');await download.saveAs(reviewPath);
    const review=JSON.parse(fs.readFileSync(reviewPath));
    assert.equal(review.checkpoint_sha256,manifest.checkpoint_sha256);
    assert.equal(review.reviews[manifest.frames[1].id].correction_level,3);
    assert.equal(review.reviews[manifest.frames[2].id].notes,'Test note: 123\n');
    await page.reload();await ready(3);assert.equal(await page.locator('#rating').textContent(),'Uncertain');
    assert.equal(await page.locator('#notes').inputValue(),'Test note: 123\n');
    for(const invalid of [{...review,package_id:'different'}, {...review,reviews:{[manifest.frames[0].id]:{...review.reviews[manifest.frames[0].id],prediction_sha256:'different'}}}]) {
      await page.locator('#import-file').setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
      await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('differ')||document.querySelector('#message').textContent.includes('another'));
      assert.equal(await page.locator('#progress').textContent(),`3 / ${manifest.count} reviewed`);
    }
    page.once('dialog',d=>d.dismiss());await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(),`3 / ${manifest.count} reviewed`);
    page.once('dialog',d=>d.accept());await page.locator('#clear').click();
    assert.equal(await page.locator('#progress').textContent(),`0 / ${manifest.count} reviewed`);
    await page.locator('#import-file').setInputFiles(reviewPath);
    await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported.');
    assert.equal(await page.locator('#progress').textContent(),`3 / ${manifest.count} reviewed`);
    const maskExport=page.waitForEvent('download');await page.locator('#download-mask').click();
    const mask=await maskExport;const maskPath=path.join(out,'mask.png');await mask.saveAs(maskPath);
    assert.deepEqual(fs.readFileSync(maskPath),fs.readFileSync(path.join(root,manifest.frames[2].prediction.path)));
    await page.locator('#zoom-in').click();await page.locator('#zoom-in').click();
    assert.equal(await page.locator('#zoom-value').textContent(),'200%');
    await page.locator('#stage-original').evaluate(e=>{e.scrollLeft=120;e.scrollTop=50;});
    await page.waitForFunction(()=>document.querySelector('#stage-prediction').scrollLeft>110);
    await page.locator('#fit').click();
    await page.locator('#opacity').fill('0');
    assert(await page.locator('#canvas-prediction').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.every((v,i)=>i%4!==3||v===0)));
    await page.locator('#opacity').fill('40');
    await page.locator('label').filter({has:page.locator('input[value=mask]')}).click();
    assert(await page.locator('#canvas-prediction').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.every((v,i)=>i%4!==3||v===255)));
    await page.locator('label').filter({has:page.locator('input[value=source]')}).click();assert(!(await page.locator('#canvas-prediction').isVisible()));
    await page.locator('label').filter({has:page.locator('input[value=overlay]')}).click();
    await page.keyboard.press('1');assert.equal(await page.locator('#rating').textContent(),'Correct');
    await page.locator('button[data-layout=stack]').click();assert.equal(await page.locator('#panes').getAttribute('data-layout'),'stack');
    await page.locator('button[data-layout=columns]').click();
    await go(1);await page.locator('#reference').check();
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    const binaryIndex=manifest.frames.findIndex(f=>f.supervision==='binary-reference');
    if(binaryIndex>=0){await go(binaryIndex+1);await page.screenshot({path:path.join(out,'desktop-binary.png'),fullPage:true});await go(1);}
    for(const width of [768,390]) {
      await page.setViewportSize({width,height:844});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert(await page.locator('.pane-heading').evaluateAll(items=>items.every(e=>{
        const [a,b]=e.children, ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();return ra.right<=rb.left+1||ra.bottom<=rb.top+1;
      })));
      await page.screenshot({path:path.join(out,`${width}.png`),fullPage:true});
    }
    await page.locator('[data-decision=needs_correction]').click();
    assert(await page.locator('#correction-dialog').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}));
    await page.screenshot({path:path.join(out,'mobile-level.png'),fullPage:true});
    await page.keyboard.press('Escape');
    assert.deepEqual(errors,[]);
    assert(requests.every(r=>r.startsWith('file:')||r.startsWith('blob:')),'Unexpected remote request');
    console.log(JSON.stringify({passed:true,images:manifest.count,screenshots:out,checks:'all per-image P/R/F1 and partial-reference limits, exact pixels, source loading, keyboard, levels, persistence, import/export identity, mask download, opacity, zoom/pan, layouts, mobile, no network'},null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
