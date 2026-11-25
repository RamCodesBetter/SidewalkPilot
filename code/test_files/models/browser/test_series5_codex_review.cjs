const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {chromium}=require('playwright');
(async()=>{
 const root=path.resolve(process.argv[2]), previous=path.resolve(process.argv[3]);
 const data=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
 const total=data.count, first=data.frames[0].id;
 const nextPosition=Math.min(2,total), reviewedCount=Math.min(2,total);
 const old=JSON.parse(fs.readFileSync(path.join(previous,'manifest.json')));
 assert.notEqual(data.package_id,old.package_id);assert.deepEqual(data.review_methods,['codex']);
 const out=fs.mkdtempSync(path.join(os.tmpdir(),'sp-codex-round2-'));
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+path.join(root,'index.html'));
  const ready=n=>page.waitForFunction(n=>!document.body.classList.contains('loading')&&document.querySelector('#position').value===String(n),n);
  await ready(1);
  assert.equal(await page.locator('#progress').textContent(),`0 / ${total} ratings`);
  assert.equal(await page.locator('.pane').count(),4);
  assert.equal(await page.locator('#status-gsam2').textContent(),'Reference');
  assert.equal(await page.locator('#status-sam3').textContent(),'Reference');
  assert(await page.locator('#method').isDisabled());
  assert.equal(await page.locator('[data-method=codex]').textContent(),data.methods.codex);
  assert.equal(await page.locator('#method option').textContent(),data.methods.codex);
  if(data.annotation_heading)assert.equal(await page.locator('#annotation-heading').textContent(),data.annotation_heading);
  if(data.uncertain_label)assert.equal(await page.locator('#uncertain-label').textContent(),data.uncertain_label);
  if(data.sample_description)assert((await page.locator('#sample').textContent()).startsWith(data.sample_description));
  for(let n=1;n<=total;n++){
   if(n>1){await page.keyboard.press('Enter');await ready(n);}
   assert(await page.evaluate(()=>Array.from(document.querySelectorAll('.imagebox img')).every(e=>e.naturalWidth===1280)));
   if(data.frames[n-1].source_sample_id)assert((await page.locator('#filename').textContent()).startsWith(data.frames[n-1].source_sample_id+' / '));
   const counts=await page.evaluate(()=>Object.fromEntries(['gsam2','sam3','codex'].map(m=>{
    const c=document.querySelector('#canvas-'+m),rgba=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
    let positive=0,uncertain=0;
    for(let i=0;i<rgba.length;i+=4){if(rgba[i+3]&&rgba[i+1]>rgba[i]&&rgba[i+1]>rgba[i+2])positive++;else if(rgba[i+3])uncertain++;}
    return[m,{positive,uncertain}];
   })));
   for(const m of ['gsam2','sam3','codex']){
    assert.equal(counts[m].positive,data.frames[n-1].methods[m].positive_pixels);
    assert.equal(counts[m].uncertain,data.frames[n-1].methods[m].uncertain_pixels);
   }
  }
  assert(await page.locator('#next').isDisabled());
  await page.locator('#position').fill('1');await page.locator('#position').press('Tab');await ready(1);
  await page.locator('[data-method=codex]').click();await page.keyboard.press('2');await page.keyboard.press('1');
  assert.equal(await page.locator('#status-codex').textContent(),'Minor fixes');
  assert.equal(await page.locator('#progress').textContent(),`1 / ${total} ratings`);
  await page.keyboard.press('Enter');await ready(nextPosition);
  if(total>1)await page.keyboard.press('1');
  else{
   assert(await page.locator('#previous').isDisabled());
   assert(await page.locator('#next').isDisabled());
   assert.equal(await page.locator('#status-codex').textContent(),'Minor fixes');
  }
  await page.locator('#notes').fill('123 stays in notes');
  const downloadPromise=page.waitForEvent('download');await page.locator('#export').click();
  const download=await downloadPromise;const file=path.join(out,'synthetic-test-only.json');await download.saveAs(file);
  const review=JSON.parse(fs.readFileSync(file));assert.deepEqual(review.review_methods,['codex']);
  assert.equal(review.reviews[first].methods.codex.correction_level,1);
  assert(Object.values(review.reviews).every(r=>Object.keys(r.methods).every(m=>m==='codex')));
  await page.reload();await ready(nextPosition);assert.equal(await page.locator('#progress').textContent(),`${reviewedCount} / ${total} ratings`);
  await page.locator('#zoom-in').click();await page.locator('#stage-original').evaluate(e=>{e.scrollLeft=100;});
  await page.waitForFunction(()=>document.querySelector('#stage-codex').scrollLeft>90);await page.locator('#fit').click();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  for(const width of [768,390]){await page.setViewportSize({width,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.locator('[data-decision=needs_correction]').click();
  await page.screenshot({path:path.join(out,'mobile-level.png'),fullPage:true});await page.keyboard.press('3');
  assert.equal(await page.locator('#status-codex').textContent(),'Major fixes');
  for(const kind of ['old','reference']){
   const invalid=JSON.parse(JSON.stringify(review));
   if(kind==='old')invalid.package_id=old.package_id;
   else invalid.reviews[first].methods.gsam2={decision:'correct',sha256:data.frames[0].methods.gsam2.sha256};
   await page.locator('#import-file').setInputFiles({name:'wrong.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
   await page.waitForFunction(kind=>document.querySelector('#message').textContent.includes(kind==='old'?'another package':'identity'),kind);
   assert.equal(await page.locator('#progress').textContent(),`${reviewedCount} / ${total} ratings`);
  }
  page.once('dialog',d=>d.accept());await page.locator('#clear').click();assert.equal(await page.locator('#progress').textContent(),`0 / ${total} ratings`);
  await page.locator('#import-file').setInputFiles(file);await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported.');
  assert.equal(await page.locator('#progress').textContent(),`${reviewedCount} / ${total} ratings`);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,screenshots:out,checks:`${total} images / ${total*3} rendered masks, Codex-only ratings, correction levels, notes, keyboard, storage, export/import, reject old and out-of-scope reviews, zoom, desktop/mobile`},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
