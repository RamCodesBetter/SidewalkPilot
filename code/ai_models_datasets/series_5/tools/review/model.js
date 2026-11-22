/* Package-local viewer: ratings never rewrite the predictions or reference masks. */
(() => {
  'use strict';
  const data = window.MODEL_REVIEW_DATA, $ = id => document.getElementById(id);
  const sides = ['original', 'prediction', 'reference'];
  const decisions = ['unreviewed', 'correct', 'needs_correction', 'uncertain'];
  const labels = {unreviewed:'Unreviewed',correct:'Correct',needs_correction:'Needs correction',uncertain:'Uncertain'};
  const levels = {1:'Minor fixes',2:'Moderate fixes',3:'Major fixes'};
  const key = 'sp-model-review:' + data.package_id;
  const state = {index:0, mode:'overlay', opacity:40, zoom:1, reviews:{}};
  let pixels = {}, generation = 0, ready = false, syncing = false;
  const frame = () => data.frames[state.index];
  const notice = text => { $('message').textContent = text; };

  function decode(rle, size) {
    if (!Array.isArray(rle) || !rle.length || rle.length % 2) throw Error('Invalid mask encoding.');
    const out = new Uint8Array(size); let offset = 0;
    for (let i=0;i<rle.length;i+=2) {
      const value=rle[i], n=rle[i+1];
      if (![0,1,255].includes(value) || !Number.isInteger(n) || n<=0 || offset+n>size) throw Error('Invalid mask pixels.');
      out.fill(value,offset,offset+n);offset+=n;
    }
    if (offset!==size) throw Error('Incomplete mask.');
    return out;
  }
  function checkedReviews(reviews) {
    if (!reviews || typeof reviews!=='object' || Array.isArray(reviews)) throw Error('Invalid reviews.');
    const frames=new Map(data.frames.map(f=>[f.id,f])), clean={};
    for (const [id,row] of Object.entries(reviews)) {
      const f=frames.get(id);
      if (!f || !row || row.source_sha256!==f.source_sha256 || row.prediction_sha256!==f.prediction.sha256
          || !decisions.includes(row.decision) || typeof row.notes!=='string' || row.notes.length>20000) throw Error('Review image or prediction identity differs.');
      if (row.correction_level!=null && (row.decision!=='needs_correction' || ![1,2,3].includes(row.correction_level))) throw Error('Invalid correction level.');
      clean[id]={source_sha256:row.source_sha256,prediction_sha256:row.prediction_sha256,decision:row.decision,notes:row.notes};
      if (row.correction_level!=null) clean[id].correction_level=row.correction_level;
    }
    return clean;
  }
  function currentReview() {
    const f=frame();
    return state.reviews[f.id] || {source_sha256:f.source_sha256,prediction_sha256:f.prediction.sha256,decision:'unreviewed',notes:''};
  }
  function persist() {
    try { localStorage.setItem(key,JSON.stringify({index:state.index,reviews:state.reviews}));$('saved').textContent='Saved in this browser'; }
    catch (_) { $('saved').textContent='Browser storage unavailable';notice('Export the review to keep your ratings.'); }
  }
  function updateReview() {
    const r=currentReview();$('rating').textContent=levels[r.correction_level] || labels[r.decision];
    $('notes').value=r.notes;$('notes').disabled=!ready;
    document.querySelectorAll('[data-decision]').forEach(b=>{b.disabled=!ready;b.setAttribute('aria-pressed',String(b.dataset.decision===r.decision));});
    const count=Object.values(state.reviews).filter(r=>r.decision!=='unreviewed').length;
    $('progress').textContent=`${count} / ${data.count} reviewed`;
  }
  function rate(decision, level) {
    if (!ready) return;
    const row={...currentReview(),decision};delete row.correction_level;
    if(level)row.correction_level=level;
    state.reviews[frame().id]=row;updateReview();persist();
  }
  function choose(decision) {
    if(!ready)return;
    if(decision==='needs_correction')$('correction-dialog').showModal();else rate(decision);
  }
  function draw() {
    if(!ready)return;
    for(const side of ['prediction','reference']) {
      const c=$('canvas-'+side);c.style.display=state.mode==='source'?'none':'block';
      const ctx=c.getContext('2d'), image=ctx.createImageData(c.width,c.height), mask=pixels[side];
      for(let i=0;i<mask.length;i++) {
        const value=mask[i], at=i*4;
        let color=value===1?[30,210,140]:value===255?[240,180,40]:[25,29,31];
        let alpha=state.mode==='mask'?255:(value===0?0:Math.round(state.opacity*2.55));
        if(value===255 && state.mode==='overlay' && ((i%c.width+Math.floor(i/c.width))%12<3))color=[174,104,12];
        image.data.set([...color,alpha],at);
      }
      ctx.putImageData(image,0,0);
    }
  }
  function showMetrics() {
    const binary=frame().supervision==='binary-reference';
    const m=window.MODEL_REVIEW_METRICS.score(pixels.prediction,pixels.reference,frame().supervision);
    const values=[['metric-p',m.precision,'TP / (TP + FP)'],['metric-r',m.recall,'TP / (TP + FN)'],['metric-f1',m.f1,'2 TP / (2 TP + FP + FN)']];
    for(const [id,value,formula] of values) {
      const el=$(id);el.textContent=value===null?'N/A':(100*value).toFixed(2)+'%';
      el.dataset.unavailable=String(value===null);
      el.title=!binary&&id!=='metric-r'?'Unavailable: a positive-only reference cannot establish false positives.'
        :value===null?'Undefined: this metric has a zero denominator.':formula+'; unknown reference pixels excluded.';
    }
    $('recall-label').textContent=binary?'Recall':'Known sidewalk';
    $('metric-scope').textContent=binary
      ?`Binary reference / ${m.scored_pixels.toLocaleString()} scored pixels / ${m.ignored.toLocaleString()} ignored`
      :`Positive-only reference / ${m.scored_pixels.toLocaleString()} known sidewalk pixels. P and F1 unavailable.`;
  }
  function zoom(value) {
    state.zoom=Math.max(1,Math.min(4,value));
    document.querySelectorAll('.imagebox').forEach(b=>b.style.width=(state.zoom*100)+'%');
    $('zoom-value').textContent=Math.round(state.zoom*100)+'%';
    $('zoom-out').disabled=state.zoom===1;$('zoom-in').disabled=state.zoom===4;
  }
  async function show(index) {
    if(!Number.isInteger(index))index=state.index;
    if($('correction-dialog').open)$('correction-dialog').close();
    const ticket=++generation;ready=false;document.body.classList.add('loading');
    state.index=Math.max(0,Math.min(data.count-1,index));const f=frame();
    for(const id of ['metric-p','metric-r','metric-f1']){$(id).textContent='...';$(id).title='';}
    $('metric-scope').textContent='';
    $('position').value=state.index+1;$('position').max=data.count;$('total').textContent='/ '+data.count;
    $('previous').disabled=state.index===0;$('next').disabled=state.index===data.count-1;
    $('filename').textContent=f.name;$('dimensions').textContent=f.size.join(' x ');
    $('reference-kind').textContent=f.supervision==='binary-reference'?'Binary reference':'Positive-only / partial';
    $('coverage').textContent=(100*f.prediction.positive_pixels/(f.size[0]*f.size[1])).toFixed(1)+'% area';
    $('download-mask').href=f.prediction.path;$('download-mask').download=f.name.replace(/\.[^.]+$/,'')+'-5.A-mask.png';
    updateReview();
    try {
      const loaded=new Image();
      await new Promise((resolve,reject)=>{loaded.onload=resolve;loaded.onerror=()=>reject(Error('Image unavailable. Keep the images folder beside index.html.'));loaded.src=f.image;});
      if(ticket!==generation)return;
      for(const side of sides) {
        $('image-'+side).src=f.image;
        const box=$('stage-'+side).firstElementChild;box.style.aspectRatio=f.size[0]+'/'+f.size[1];
        $('stage-'+side).style.aspectRatio=f.size[0]+'/'+f.size[1];
        if(side!=='original') {
          const c=$('canvas-'+side);c.width=f.size[0];c.height=f.size[1];pixels[side]=decode(f[side].rle,c.width*c.height);
        }
      }
      ready=true;draw();showMetrics();zoom(state.zoom);updateReview();persist();
      sides.forEach(s=>{$('stage-'+s).scrollLeft=0;$('stage-'+s).scrollTop=0;});
      document.body.classList.remove('loading');
    } catch(error) {if(ticket===generation){notice(error.message);updateReview();}}
  }
  function downloadReview() {
    const result={schema:'sidewalkpilot-model-review-ratings-v1',package_id:data.package_id,
      model_name:data.model_name,checkpoint_sha256:data.checkpoint_sha256,partition:data.partition,
      exported_utc:new Date().toISOString(),reviews:state.reviews};
    const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='sidewalkpilot-5.A-test-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  $('download-mask').onclick=e=>{
    e.preventDefault();if(!ready)return;
    const bytes=Uint8Array.from(atob(frame().prediction.png_base64),c=>c.charCodeAt(0));
    const url=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));
    const a=document.createElement('a');a.href=url;a.download=$('download-mask').download;a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  $('previous').onclick=()=>show(state.index-1);$('next').onclick=()=>show(state.index+1);
  $('position').onchange=()=>show(Number($('position').value)-1);
  document.querySelectorAll('input[name=mode]').forEach(e=>e.onchange=()=>{state.mode=e.value;draw();});
  $('opacity').oninput=()=>{state.opacity=Number($('opacity').value);$('opacity-value').textContent=state.opacity+'%';draw();};
  $('reference').onchange=()=>{$('pane-reference').hidden=!$('reference').checked;$('panes').classList.toggle('with-reference',$('reference').checked);};
  document.querySelectorAll('[data-layout]').forEach(b=>{if(b.tagName==='BUTTON')b.onclick=()=>{
    $('panes').dataset.layout=b.dataset.layout;
    document.querySelectorAll('button[data-layout]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  };});
  $('zoom-in').onclick=()=>zoom(state.zoom+.5);$('zoom-out').onclick=()=>zoom(state.zoom-.5);$('fit').onclick=()=>zoom(1);
  for(const side of sides)$('stage-'+side).onscroll=()=>{
    if(syncing)return;syncing=true;const from=$('stage-'+side);
    for(const other of sides)if(other!==side){const to=$('stage-'+other);to.scrollLeft=from.scrollLeft;to.scrollTop=from.scrollTop;}
    requestAnimationFrame(()=>{syncing=false;});
  };
  document.querySelectorAll('[data-decision]').forEach(b=>b.onclick=()=>choose(b.dataset.decision));
  function level(value){$('correction-dialog').close();rate('needs_correction',value);}
  document.querySelectorAll('[data-level]').forEach(b=>b.onclick=()=>level(Number(b.dataset.level)));
  $('close-correction').onclick=()=>$('correction-dialog').close();
  $('notes').oninput=()=>{if(ready){state.reviews[frame().id]={...currentReview(),notes:$('notes').value.slice(0,20000)};persist();}};
  document.addEventListener('keydown',e=>{
    if(e.repeat||e.ctrlKey||e.metaKey||e.altKey)return;
    if($('correction-dialog').open){if(['1','2','3'].includes(e.key)){e.preventDefault();level(Number(e.key));}return;}
    if(e.target.closest('textarea,select,[contenteditable=true]')
        ||(e.target.tagName==='INPUT'&&!['checkbox','radio'].includes(e.target.type)))return;
    if(['Enter','ArrowRight','ArrowLeft','1','2','3'].includes(e.key))e.preventDefault();
    if(e.key==='Enter'||e.key==='ArrowRight')show(state.index+1);
    else if(e.key==='ArrowLeft')show(state.index-1);
    else if(['1','2','3'].includes(e.key))choose(['correct','needs_correction','uncertain'][Number(e.key)-1]);
  });
  $('export').onclick=downloadReview;$('import').onclick=()=>$('import-file').click();
  $('import-file').onchange=async()=>{
    try {
      const file=$('import-file').files[0];if(!file)return;
      if(file.size>2_000_000)throw Error('Review file is too large.');
      const incoming=JSON.parse(await file.text());
      if(incoming.schema!=='sidewalkpilot-model-review-ratings-v1'||incoming.package_id!==data.package_id
          ||incoming.checkpoint_sha256!==data.checkpoint_sha256||incoming.partition!==data.partition)throw Error('Review belongs to another package or model.');
      const clean=checkedReviews(incoming.reviews);
      if(Object.keys(state.reviews).length&&!confirm('Replace this browser review with the imported review?'))return;
      state.reviews=clean;updateReview();persist();notice('Review imported.');
    }catch(error){notice(error.message);}finally{$('import-file').value='';}
  };
  $('clear').onclick=()=>{if(confirm('Clear ratings and notes for this package only?')){state.reviews={};updateReview();persist();notice('Review cleared.');}};
  try {
    const saved=JSON.parse(localStorage.getItem(key)||'null');
    if(saved){state.reviews=checkedReviews(saved.reviews);if(Number.isInteger(saved.index))state.index=saved.index;}
  }catch(_){notice('Saved review could not be loaded. Original masks are unchanged.');}
  $('scope').textContent=`Development ${data.partition} / ${data.count} images / checkpoint epoch ${data.checkpoint_epoch}`;
  $('provenance').textContent=`${data.binary_references} binary references / ${data.partial_references} partial references / ${data.checkpoint_sha256.slice(0,12)}`;
  lucide.createIcons();show(state.index);
})();
