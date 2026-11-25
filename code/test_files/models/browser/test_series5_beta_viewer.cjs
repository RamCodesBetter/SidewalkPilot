const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');

function expected(frame,side) {
  const decode=rle=>{const out=[];for(let i=0;i<rle.length;i+=2)for(let n=0;n<rle[i+1];n++)out.push(rle[i]);return out;};
  const ref=frame.comparison_reference||frame.reference;
  const p=decode(frame.predictions[side].rle),r=decode(ref.rle),counts=[0,0,0,0];
  for(let i=0;i<p.length;i++)if(r[i]!==255)counts[2*r[i]+p[i]]++;
  const [tn,fp,fn,tp]=counts,binary=(ref.kind||frame.supervision)!=='sidewalk-positive-only';
  const ratio=(a,b)=>b?(100*a/b).toFixed(2)+'%':'N/A';
  const ious=[[tp,tp+fp+fn],[tn,tn+fp+fn]].filter(([a,b])=>b>0).map(([a,b])=>a/b);
  return {p:binary?ratio(tp,tp+fp):'N/A',r:ratio(tp,tp+fn),f1:binary?ratio(2*tp,2*tp+fp+fn):'N/A',
    iou:binary?ratio(tp,tp+fp+fn):'N/A',miou:binary&&ious.length?(100*ious.reduce((a,b)=>a+b,0)/ious.length).toFixed(2)+'%':'N/A'};
}

(async()=>{
  const root=path.resolve(process.argv[2]),data=JSON.parse(fs.readFileSync(path.join(root,'manifest.json')));
  const out=fs.mkdtempSync(path.join(os.tmpdir(),'sidewalkpilot-beta-viewer-'));
  const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
  try {
    const page=await browser.newPage({viewport:{width:1500,height:960},acceptDownloads:true});
    const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    const ready=n=>page.waitForFunction(n=>!document.body.classList.contains('loading')&&document.querySelector('#position').value===String(n),n);
    const go=async n=>{await page.locator('#position').fill(String(n));await page.locator('#position').press('Tab');await ready(n);};
    await ready(1);assert.equal(await page.locator('.pane:visible').count(),3);
    assert.equal(await page.locator('#progress').textContent(),`0 / ${data.count*2} masks reviewed`);
    await page.locator('#reference').check();assert.equal(await page.locator('.pane:visible').count(),4);
    for(let n=1;n<=data.count;n++) {
      if(n>1)await go(n);
      for(const side of ['a','b']) {
        const scores=expected(data.frames[n-1],side);
        for(const metric of ['p','r','f1','iou','miou'])assert.equal(await page.locator(`#metric-${side}-${metric}`).textContent(),scores[metric],`${n} ${side} ${metric}`);
      }
      for(const metric of ['p','r','f1','iou','miou']) {
        const a=await page.locator(`#metric-a-${metric}`).textContent(),b=await page.locator(`#metric-b-${metric}`).textContent();
        const comparable=a!=='N/A'&&b!=='N/A';
        for(const side of ['a','b']) {
          const better=comparable&&(side==='a'?parseFloat(a)>parseFloat(b):parseFloat(b)>parseFloat(a));
          const el=page.locator(`#metric-${side}-${metric}`);
          assert.equal(await el.getAttribute('data-better'),String(better),`highlight ${n} ${side} ${metric}`);
          assert.equal((await el.getAttribute('aria-label')).includes('higher displayed value'),better);
        }
      }
      if(data.frames[n-1].comparison_reference?.kind==='derived-binary-reference') {
        assert((await page.locator('#metric-scope').textContent()).includes('Provisional'));
        assert((await page.locator('#metric-scope').textContent()).includes('assumed background'));
      }
      const rendered=await page.evaluate(()=>['a','b','reference'].map(side=>{
        const c=document.querySelector('#canvas-'+side),img=document.querySelector('#image-'+side);
        const pixels=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let positive=0,ignored=0;
        for(let i=0;i<pixels.length;i+=4)if(pixels[i+3]){if(pixels[i+1]>pixels[i])positive++;else ignored++;}
        return {side,positive,ignored,width:img.naturalWidth,height:img.naturalHeight,source:img.getAttribute('src')};
      }));
      for(const r of rendered) {
        const frame=data.frames[n-1],mask=r.side==='reference'?(frame.comparison_reference||frame.reference):frame.predictions[r.side];
        assert.equal(r.positive,mask.positive_pixels);assert.equal(r.ignored,mask.ignored_pixels);
        assert.deepEqual([r.width,r.height],frame.size);assert.equal(r.source,frame.image);
      }
    }
    await go(1);await page.locator('#reference').uncheck();await page.keyboard.press('1');
    assert(await page.locator('input[name=target][value=b]').isChecked());
    assert.equal(await page.locator('#rating-a').textContent(),'Correct');
    await page.keyboard.press('2');assert(await page.locator('#correction-dialog').isVisible());
    await page.keyboard.press('1');await ready(2);assert.equal(await page.locator('input[name=target]:checked').inputValue(),'a');
    await page.keyboard.press('Enter');await ready(3);await page.keyboard.press('ArrowLeft');await ready(2);
    await page.locator('#auto-advance').uncheck();
    for(const [level,label] of [[1,'Minor fixes'],[2,'Moderate fixes'],[3,'Major fixes']]) {
      await page.keyboard.press('2');await page.keyboard.press(String(level));
      assert.equal(await page.locator('#rating').textContent(),label);assert.equal(await page.locator('#position').inputValue(),'2');
    }
    await page.keyboard.press('b');await page.keyboard.press('3');assert.equal(await page.locator('#rating').textContent(),'Uncertain');
    await page.locator('#notes').fill('B note 123');await page.locator('#notes').press('Enter');assert.equal(await page.locator('#position').inputValue(),'2');
    await page.locator('#notes').press('Tab');await page.keyboard.press('a');
    assert.equal(await page.locator('#rating').textContent(),'Major fixes');assert.equal(await page.locator('#notes').inputValue(),'');
    await page.keyboard.press('2');await page.keyboard.press('Escape');assert.equal(await page.locator('#rating').textContent(),'Major fixes');
    const pending=page.waitForEvent('download');await page.locator('#export').click();const exported=await pending;
    const reviewPath=path.join(out,'test-review.json');await exported.saveAs(reviewPath);const reviews=JSON.parse(fs.readFileSync(reviewPath));
    if(data.comparison_reference_id)assert.equal(reviews.comparison_reference_id,data.comparison_reference_id);
    assert.equal(reviews.reviews[data.frames[0].id+':b'].correction_level,1);
    assert.equal(reviews.reviews[data.frames[1].id+':b'].notes,'B note 123\n');
    await page.reload();await ready(2);assert.equal(await page.locator('#rating').textContent(),'Major fixes');
    assert(!(await page.locator('#auto-advance').isChecked()));
    for(const change of [{...reviews,package_id:'wrong'},{...reviews,reviews:{[data.frames[0].id+':b']:{...reviews.reviews[data.frames[0].id+':b'],prediction_sha256:'wrong'}}}]) {
      await page.locator('#import-file').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(change))});
      await page.waitForFunction(()=>/another|differs/.test(document.querySelector('#message').textContent));
    }
    page.once('dialog',d=>d.dismiss());await page.locator('#clear').click();assert.equal(await page.locator('#rating').textContent(),'Major fixes');
    page.once('dialog',d=>d.accept());await page.locator('#clear').click();assert.equal(await page.locator('#rating').textContent(),'Unreviewed');
    await page.locator('#import-file').setInputFiles(reviewPath);await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported.');
    if(data.compatible_review_package_ids?.length) {
      const old={...reviews,package_id:data.compatible_review_package_ids[0]};delete old.comparison_reference_id;
      page.once('dialog',d=>d.accept());
      await page.locator('#import-file').setInputFiles({name:'old-review.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(old))});
      await page.waitForFunction(()=>document.querySelector('#message').textContent==='Review imported.');
      await page.evaluate(({id,reviews})=>{
        localStorage.setItem('sp-beta-comparison:'+id,JSON.stringify({index:1,target:'b',autoAdvance:false,reviews}));
        localStorage.removeItem('sp-beta-comparison:'+window.BETA_COMPARISON_DATA.package_id);
      },{id:old.package_id,reviews:old.reviews});
      await page.reload();await ready(2);assert.equal(await page.locator('#rating').textContent(),'Uncertain');
      assert.equal(await page.locator('#notes').inputValue(),'B note 123\n');
    }
    for(const side of ['a','b']) {
      const downloading=page.waitForEvent('download');await page.locator(`[data-download=${side}]`).click();const downloaded=await downloading;
      const dest=path.join(out,side+'.png');await downloaded.saveAs(dest);
      assert.deepEqual(fs.readFileSync(dest),fs.readFileSync(path.join(root,data.frames[1].predictions[side].path)));
    }
    await page.locator('#zoom-in').click();await page.locator('#zoom-in').click();
    await page.locator('#stage-original').evaluate(e=>{e.scrollLeft=120;e.scrollTop=50;});
    await page.waitForFunction(()=>document.querySelector('#stage-b').scrollLeft>110);
    await page.locator('#fit').click();await page.locator('#opacity').fill('0');
    assert(await page.locator('#canvas-b').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.every((v,i)=>i%4!==3||v===0)));
    await page.locator('#opacity').fill('40');
    await page.locator('label').filter({has:page.locator('input[value=mask]')}).click();
    assert(await page.locator('#canvas-a').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.every((v,i)=>i%4!==3||v===255)));
    await page.locator('label').filter({has:page.locator('input[value=source]')}).click();assert(!(await page.locator('#canvas-b').isVisible()));
    await page.locator('label').filter({has:page.locator('input[value=overlay]')}).click();
    await page.locator('button[data-layout=stack]').click();assert.equal(await page.locator('#panes').getAttribute('data-layout'),'stack');
    await page.locator('button[data-layout=columns]').click();await go(1);
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    await page.locator('#reference').check();await page.screenshot({path:path.join(out,'desktop-reference.png'),fullPage:true});
    for(const width of [1024,768,390]) {
      await page.setViewportSize({width,height:844});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert(await page.locator('.pane-heading').evaluateAll(items=>items.every(e=>[...e.children].every(c=>c.scrollWidth<=c.clientWidth+1))));
      assert(await page.locator('.metrics dd').evaluateAll(items=>items.every(e=>e.scrollWidth<=e.clientWidth+1)));
      await page.screenshot({path:path.join(out,`${width}.png`),fullPage:true});
    }
    await page.locator('[data-decision=needs_correction]').click();
    assert(await page.locator('#correction-dialog').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth;}));
    await page.screenshot({path:path.join(out,'mobile-level.png'),fullPage:true});
    assert.deepEqual(errors,[]);assert(requests.every(r=>r.startsWith('file:')||r.startsWith('blob:')));
    console.log(JSON.stringify({passed:true,images:data.count,metrics:'Both models, every image',screenshots:out,offline:true},null,2));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
