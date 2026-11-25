const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const data = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  const keys = Object.keys(data.models);
  assert.equal(data.count, 50);
  assert.equal(new Set(data.frames.map(f => f.id)).size, 50);
  assert.equal(keys.length, 8);
  const browser = await chromium.launch({args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(root,'index.html')).href);
    const ready=()=>page.waitForFunction(()=>!document.body.classList.contains('loading'));
    await ready();
    for (const key of keys) {
      await page.locator('input[name=visible][value='+key+']').check();
      await ready();
    }
    assert.equal(await page.locator('.pane:visible').count(),9);
    const first=data.frames[0];
    function expand(rec){
      const pixels=new Uint8Array(first.size[0]*first.size[1]);
      let k=0;for(let i=0;i<rec.rle.length;i+=2){pixels.fill(rec.rle[i],k,k+rec.rle[i+1]);k+=rec.rle[i+1];}
      assert.equal(k,pixels.length);return pixels;
    }
    const ref=expand(first.reference);
    for(const key of keys){
      const pred=expand(first.predictions[key]), counts=[0,0,0,0];
      for(let i=0;i<pred.length;i++)if(ref[i]!==255)counts[2*ref[i]+pred[i]]++;
      const [tn,fp,fn,tp]=counts;
      const s=tp/(tp+fp+fn),b=tn/(tn+fp+fn);
      const scores=[tp/(tp+fp),tp/(tp+fn),2*tp/(2*tp+fp+fn),s,b,(s+b)/2];
      assert.deepEqual(await page.locator('#pane-'+key+' dd').allTextContents(),
        scores.map(v=>Number.isFinite(v)?(100*v).toFixed(2)+'%':'N/A'));
    }
    for(const key of keys.filter(k=>k!=='es')){
      await page.locator('input[name=visible][value='+key+']').uncheck();await ready();
    }
    assert.equal(await page.locator('.pane:visible').count(),2);
    assert.equal(await page.locator('dd[data-better=true]:visible').count(),0);
    await page.keyboard.press('2');await page.keyboard.press('1');await ready();
    assert.equal(await page.locator('#position').inputValue(),'2');
    await page.reload();await ready();
    assert.equal(await page.locator('input[name=target]:checked').inputValue(),'es');
    await page.locator('input[name=visible][value=cb]').check();await ready();
    await page.locator('#reference').check();
    await page.screenshot({path:'/tmp/model-lab-desktop.png'});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:'/tmp/model-lab-mobile.png'});
    assert.deepEqual(errors,[]);
    console.log('Passed: eight checkpoints, six independently computed scores, selection, ratings, persistence and mobile layout.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
