/* Offline paired review. Ratings never change model predictions or reference masks. */
(() => {
  'use strict';
  const data=window.BETA_COMPARISON_DATA, $=id=>document.getElementById(id);
  const models=Object.keys(data.models), sides=['original',...models,'reference'];
  let visible=models.includes('e')?['c','e']:models.slice(0,2);
  const labels={unreviewed:'Unreviewed',correct:'Correct',needs_correction:'Needs correction',uncertain:'Uncertain'};
  const levels={1:'Minor fixes',2:'Moderate fixes',3:'Major fixes'};
  const storageKey='sp-beta-comparison:'+data.package_id;
  const compatiblePackages=[data.package_id,...(data.compatible_review_package_ids||[])];
  const metricFields=[['p','precision'],['r','recall'],['f1','f1'],['iou','sidewalk_iou'],['ioub','background_iou'],['miou','miou']];
  const state={index:0,target:visible[0],mode:'overlay',opacity:40,zoom:1,reviews:{}};
  let ready=false, generation=0, pixels={}, syncing=false;
  const frame=()=>data.frames[state.index];
  const notice=text=>{$('message').textContent=text;};
  const reviewKey=side=>frame().id+':'+side;
  const record=(f,side)=>side==='reference'?(f.comparison_reference||f.reference):f.predictions[side];
  const referenceKind=f=>f.comparison_reference?.kind||f.supervision;

  const targetBox=document.querySelector('.review-bar fieldset');
  for(const key of models){
    const name=data.models[key].name;
    for(const [parent,type] of [[$('model-picker'),'checkbox'],[targetBox,'radio']]){
      const label=document.createElement('label'),input=document.createElement('input');
      input.type=type;input.value=key;input.name=type==='radio'?'target':'visible';
      label.append(input,' '+name);parent.append(label);
      if(type==='checkbox')input.title=name+' / epoch '+data.models[key].epoch;
    }
  }
  function layout(){
    for(const key of models){
      const on=visible.includes(key);
      $('pane-'+key).hidden=!on;
      document.querySelector(`input[name=target][value=${key}]`).parentElement.hidden=!on;
      const box=document.querySelector(`input[name=visible][value=${key}]`);
      box.checked=on;box.disabled=on&&visible.length===1;
    }
  }
  if(data.schema==='sidewalkpilot-model-lab-v1'){
    for(const [key,policy] of [['d','No encoder freeze'],['f','Encoder frozen for epochs 1 and 2']]){
      if(models.includes(key))continue;
      const label=document.createElement('label'),box=document.createElement('input');
      box.type='checkbox';box.disabled=true;
      label.append(box,' 5.'+key.toUpperCase()+' (pending)');
      label.title=policy+'; no trained checkpoint in this package';
      $('model-picker').append(label);
    }
  }
  for(const side of sides) {
    const model=models.includes(side), title=model?data.models[side].name:side==='original'?'Original':'Reference';
    const pane=document.createElement('section');pane.className='pane';pane.id='pane-'+side;pane.hidden=side==='reference';
    pane.innerHTML=`<div class="pane-heading">${model?`<button class="pane-title" data-select="${side}" title="Review ${title}">${title}</button>`:`<h2>${title}</h2>`}
      <span class="status" id="status-${side}"></span>${model?`<button class="icon" data-download="${side}" title="Download ${title} mask" aria-label="Download ${title} mask"><i data-lucide="image-down"></i></button>`:''}</div>
      <div class="stage" id="stage-${side}"><div class="imagebox"><img id="image-${side}" alt="${title} sidewalk image">${side==='original'?'':`<canvas id="canvas-${side}" aria-label="${title} mask"></canvas>`}</div></div>
      ${model?`<dl class="metrics"><div><dt title="Precision">P</dt><dd id="metric-${side}-p"></dd></div><div><dt id="recall-${side}" title="Recall">R</dt><dd id="metric-${side}-r"></dd></div><div><dt>F1</dt><dd id="metric-${side}-f1"></dd></div><div><dt title="Sidewalk intersection over union">IoUs</dt><dd id="metric-${side}-iou"></dd></div><div><dt title="Background intersection over union">IoUb</dt><dd id="metric-${side}-ioub"></dd></div><div><dt title="Mean of sidewalk and background IoU; classes with zero union excluded">mIoU</dt><dd id="metric-${side}-miou"></dd></div></dl><div class="pane-stat" id="rating-${side}"></div>`:''}`;
    $('panes').append(pane);
  }
  function decode(rle,size) {
    if(!Array.isArray(rle)||!rle.length||rle.length%2)throw Error('Invalid mask encoding.');
    const result=new Uint8Array(size);let offset=0;
    for(let i=0;i<rle.length;i+=2) {
      const value=rle[i],n=rle[i+1];
      if(![0,1,255].includes(value)||!Number.isInteger(n)||n<=0||offset+n>size)throw Error('Invalid mask pixels.');
      result.fill(value,offset,offset+n);offset+=n;
    }
    if(offset!==size)throw Error('Incomplete mask.');
    return result;
  }
  function checkedReviews(incoming) {
    if(!incoming||typeof incoming!=='object'||Array.isArray(incoming))throw Error('Invalid reviews.');
    const valid=new Map(data.frames.flatMap(f=>models.map(side=>[f.id+':'+side,{f,side}]))), clean={};
    for(const [id,row] of Object.entries(incoming)) {
      const expected=valid.get(id);
      if(!expected||!row)throw Error('Unknown review image.');
      const {f,side}=expected;
      if(row.model!==side||row.source_sha256!==f.source_sha256||row.prediction_sha256!==f.predictions[side].sha256
          ||!Object.hasOwn(labels,row.decision)||typeof row.notes!=='string'||row.notes.length>20000)throw Error('Review model or image identity differs.');
      if(row.correction_level!=null&&(row.decision!=='needs_correction'||![1,2,3].includes(row.correction_level)))throw Error('Invalid correction level.');
      clean[id]={model:side,source_sha256:row.source_sha256,prediction_sha256:row.prediction_sha256,decision:row.decision,notes:row.notes};
      if(row.correction_level!=null)clean[id].correction_level=row.correction_level;
    }
    return clean;
  }
  function currentReview(side=state.target) {
    const f=frame();
    return state.reviews[reviewKey(side)]||{model:side,source_sha256:f.source_sha256,
      prediction_sha256:f.predictions[side].sha256,decision:'unreviewed',notes:''};
  }
  function persist() {
    try {localStorage.setItem(storageKey,JSON.stringify({index:state.index,target:state.target,visible,autoAdvance:$('auto-advance').checked,reviews:state.reviews}));$('saved').textContent='Saved in this browser';}
    catch(_){$('saved').textContent='Browser storage unavailable';notice('Export the review to preserve ratings.');}
  }
  function updateReview() {
    const r=currentReview();$('rating').textContent=levels[r.correction_level]||labels[r.decision];
    $('notes-title').textContent=data.models[state.target].name+' notes';$('notes').value=r.notes;$('notes').disabled=!ready;
    for(const side of models) {
      const row=currentReview(side);$('rating-'+side).textContent=levels[row.correction_level]||labels[row.decision];
      $('pane-'+side).classList.toggle('selected',side===state.target);
      document.querySelector(`input[name=target][value=${side}]`).checked=side===state.target;
    }
    document.querySelectorAll('[data-decision]').forEach(b=>{b.disabled=!ready;b.setAttribute('aria-pressed',String(b.dataset.decision===r.decision));});
    const count=Object.values(state.reviews).filter(r=>r.decision!=='unreviewed').length;
    $('progress').textContent=`${count} / ${data.count*models.length} masks reviewed`;
  }
  function select(side) {if(!visible.includes(side))return;state.target=side;updateReview();persist();}
  function rate(decision,level) {
    if(!ready)return;
    const row={...currentReview(),decision};delete row.correction_level;
    if(level)row.correction_level=level;
    state.reviews[reviewKey(state.target)]=row;updateReview();persist();
    if($('auto-advance').checked&&decision!=='unreviewed') {
      const next=visible.indexOf(state.target)+1;
      if(next<visible.length)select(visible[next]);
      else if(state.index<data.count-1)show(state.index+1);
      else notice('End of image set.');
    }
  }
  function choose(decision) {
    if(!ready)return;
    if(decision==='needs_correction') {
      $('correction-title').textContent=data.models[state.target].name+' correction level';
      $('correction-dialog').showModal();
    }else rate(decision);
  }
  function draw() {
    if(!ready)return;
    for(const side of [...visible,'reference']) {
      const canvas=$('canvas-'+side);canvas.style.display=state.mode==='source'?'none':'block';
      const ctx=canvas.getContext('2d'), image=ctx.createImageData(canvas.width,canvas.height), mask=pixels[side];
      for(let i=0;i<mask.length;i++) {
        const v=mask[i],offset=i*4,color=v===1?[30,210,140]:v===255?[240,180,40]:[25,29,31];
        image.data[offset]=color[0];image.data[offset+1]=color[1];image.data[offset+2]=color[2];
        image.data[offset+3]=state.mode==='mask'?255:v===0?0:Math.round(state.opacity*2.55);
      }
      ctx.putImageData(image,0,0);
    }
  }
  function showMetrics() {
    const kind=referenceKind(frame()),binary=kind!=='sidewalk-positive-only',derived=kind==='derived-binary-reference';let m;
    const scores={};
    for(const side of visible) {
      m=window.MODEL_REVIEW_METRICS.score(pixels[side],pixels.reference,kind);
      scores[side]=m;
      for(const [short,key] of metricFields) {
        const el=$(`metric-${side}-${short}`),value=m[key];
        el.textContent=value===null?'N/A':(value*100).toFixed(2)+'%';el.dataset.unavailable=String(value===null);
        const basis=derived?'Provisional: pixels outside the accepted sidewalk outline are assumed background.':'Known reference pixels only; unknown pixels excluded.';
        el.title=value===null?'Unavailable from this reference or undefined denominator.':basis;
        if(key==='miou'&&value!==null)el.title+=' Mean of sidewalk and background IoU; zero-union classes excluded.';
      }
      $('recall-'+side).textContent=binary?'R':'R (known)';
    }
    for(const [short,key] of metricFields) {
      const values=visible.filter(k=>Number.isFinite(scores[k][key])).map(k=>Number((100*scores[k][key]).toFixed(2)));
      const best=Math.max(...values),competitive=values.some(value=>value<best);
      for(const side of visible) {
        const el=$(`metric-${side}-${short}`);
        const wins=competitive&&Number.isFinite(scores[side][key])&&Number((100*scores[side][key]).toFixed(2))===best;
        el.dataset.better=String(wins);
        if(wins)el.title+=' Higher displayed value for this image.';
        el.setAttribute('aria-label',`${short==='iou'?'Sidewalk IoU':short==='miou'?'mIoU':short.toUpperCase()}: ${el.textContent}${wins?', higher displayed value':''}`);
      }
    }
    $('metric-scope').dataset.provisional=String(derived);
    $('metric-scope').textContent=derived
      ?`Provisional scores / derived binary reference: outside the accepted sidewalk outline is assumed background (${frame().comparison_reference.assumed_background_pixels.toLocaleString()} formerly unknown pixels). Not independently verified.`
      :kind==='pseudo-binary'
      ?`SAM 3 reference / ${m.scored_pixels.toLocaleString()} scored pixels / ${m.ignored.toLocaleString()} ignored`
      :binary
      ?`Binary reference / ${m.scored_pixels.toLocaleString()} scored pixels / ${m.ignored.toLocaleString()} ignored`
      :`Positive-only reference / ${m.scored_pixels.toLocaleString()} known sidewalk pixels / P, F1, IoU and mIoU unavailable`;
  }
  function zoom(value) {
    state.zoom=Math.max(1,Math.min(4,value));
    document.querySelectorAll('.imagebox').forEach(e=>e.style.width=(state.zoom*100)+'%');
    $('zoom-value').textContent=Math.round(state.zoom*100)+'%';$('zoom-out').disabled=state.zoom===1;$('zoom-in').disabled=state.zoom===4;
  }
  async function show(index,keepTarget=false) {
    if(!Number.isInteger(index))index=state.index;
    if($('correction-dialog').open)$('correction-dialog').close();
    const ticket=++generation;ready=false;document.body.classList.add('loading');
    state.index=Math.max(0,Math.min(data.count-1,index));if(!keepTarget||!visible.includes(state.target))state.target=visible[0];layout();
    const f=frame();notice('');$('position').value=state.index+1;$('position').max=data.count;$('total').textContent='/ '+data.count;
    $('previous').disabled=state.index===0;$('next').disabled=state.index===data.count-1;
    $('filename').textContent=f.name;$('status-original').textContent=f.size.join(' x ');
    const kind=referenceKind(f);
    $('status-reference').textContent=kind==='derived-binary-reference'?'Derived / provisional':kind==='binary-reference'?'Binary reference':kind==='pseudo-binary'?'SAM 3 pseudo-label':'Positive-only';
    for(const side of models) {
      $('status-'+side).textContent=(100*f.predictions[side].positive_pixels/(f.size[0]*f.size[1])).toFixed(1)+'% area';
      for(const [metric] of metricFields) {
        const el=$(`metric-${side}-${metric}`);
        el.textContent='...';el.dataset.better='false';el.title='';el.removeAttribute('aria-label');
      }
    }
    $('metric-scope').textContent='';updateReview();
    try {
      const loaded=new Image();
      await new Promise((resolve,reject)=>{loaded.onload=resolve;loaded.onerror=()=>reject(Error('Image unavailable. Keep the images folder beside index.html.'));loaded.src=f.image;});
      if(ticket!==generation)return;
      if(loaded.naturalWidth!==f.size[0]||loaded.naturalHeight!==f.size[1])throw Error('Image dimensions differ from this package.');
      for(const side of ['original',...visible,'reference']) {
        $('image-'+side).src=f.image;$('stage-'+side).style.aspectRatio=f.size.join('/');
        $('stage-'+side).firstElementChild.style.aspectRatio=f.size.join('/');
        if(side!=='original') {
          const c=$('canvas-'+side);c.width=f.size[0];c.height=f.size[1];pixels[side]=decode(record(f,side).rle,c.width*c.height);
        }
      }
      ready=true;draw();showMetrics();zoom(state.zoom);updateReview();persist();
      sides.forEach(s=>{$('stage-'+s).scrollLeft=0;$('stage-'+s).scrollTop=0;});
      document.body.classList.remove('loading');
    }catch(e){if(ticket===generation){ready=false;notice(e.message);updateReview();}}
  }
  function download(bytes,type,name) {
    const url=URL.createObjectURL(new Blob([bytes],{type}));
    const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  document.querySelectorAll('[data-download]').forEach(b=>b.onclick=()=>{
    if(!ready)return;const side=b.dataset.download;
    download(Uint8Array.from(atob(frame().predictions[side].png_base64),c=>c.charCodeAt(0)), 'image/png',
      frame().name.replace(/\.[^.]+$/,'')+'-'+data.models[side].name+'-mask.png');
  });
  document.querySelectorAll('input[name=visible]').forEach(box=>box.onchange=()=>{
    visible=models.filter(k=>document.querySelector(`input[name=visible][value=${k}]`).checked);
    show(state.index,true);
  });
  $('previous').onclick=()=>show(state.index-1);$('next').onclick=()=>show(state.index+1);
  $('position').onchange=()=>show(Number($('position').value)-1);
  document.querySelectorAll('input[name=mode]').forEach(e=>e.onchange=()=>{state.mode=e.value;draw();});
  document.querySelectorAll('input[name=target]').forEach(e=>e.onchange=()=>select(e.value));
  document.querySelectorAll('[data-select]').forEach(e=>e.onclick=()=>select(e.dataset.select));
  $('opacity').oninput=()=>{state.opacity=Number($('opacity').value);$('opacity-value').textContent=state.opacity+'%';draw();};
  $('reference').onchange=()=>{$('pane-reference').hidden=!$('reference').checked;$('panes').classList.toggle('with-reference',$('reference').checked);};
  document.querySelectorAll('button[data-layout]').forEach(b=>b.onclick=()=>{
    $('panes').dataset.layout=b.dataset.layout;
    document.querySelectorAll('button[data-layout]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  });
  $('zoom-in').onclick=()=>zoom(state.zoom+.5);$('zoom-out').onclick=()=>zoom(state.zoom-.5);$('fit').onclick=()=>zoom(1);
  for(const side of sides)$('stage-'+side).onscroll=()=>{
    if(syncing)return;syncing=true;const from=$('stage-'+side);
    const x=from.scrollLeft/Math.max(1,from.scrollWidth-from.clientWidth),y=from.scrollTop/Math.max(1,from.scrollHeight-from.clientHeight);
    for(const other of sides)if(other!==side){const to=$('stage-'+other);to.scrollLeft=x*(to.scrollWidth-to.clientWidth);to.scrollTop=y*(to.scrollHeight-to.clientHeight);}
    requestAnimationFrame(()=>{syncing=false;});
  };
  document.querySelectorAll('[data-decision]').forEach(b=>b.onclick=()=>choose(b.dataset.decision));
  function level(value){$('correction-dialog').close();rate('needs_correction',value);}
  document.querySelectorAll('[data-level]').forEach(b=>b.onclick=()=>level(Number(b.dataset.level)));
  $('close-correction').onclick=()=>$('correction-dialog').close();
  $('auto-advance').onchange=persist;
  $('notes').oninput=()=>{if(ready){state.reviews[reviewKey(state.target)]={...currentReview(),notes:$('notes').value.slice(0,20000)};persist();}};
  document.addEventListener('keydown',e=>{
    if(e.repeat||e.ctrlKey||e.metaKey||e.altKey)return;
    if($('correction-dialog').open){if(['1','2','3'].includes(e.key)){e.preventDefault();level(Number(e.key));}return;}
    if(e.target.closest('textarea,select,[contenteditable=true]')||(e.target.tagName==='INPUT'&&!['checkbox','radio'].includes(e.target.type)))return;
    if(['Enter','ArrowLeft','ArrowRight','1','2','3','a','b','A','B'].includes(e.key))e.preventDefault();
    if(e.key==='Enter'||e.key==='ArrowRight')show(state.index+1);
    else if(e.key==='ArrowLeft')show(state.index-1);
    else if(['a','b'].includes(e.key.toLowerCase()))select(e.key.toLowerCase());
    else if(['1','2','3'].includes(e.key))choose(['correct','needs_correction','uncertain'][Number(e.key)-1]);
  });
  $('export').onclick=()=>download(JSON.stringify({schema:'sidewalkpilot-beta-comparison-ratings-v1',package_id:data.package_id,
    models:data.models,partition:data.partition,comparison_reference_id:data.comparison_reference_id||null,
    exported_utc:new Date().toISOString(),reviews:state.reviews},null,2),
    'application/json','sidewalkpilot-model-review.json');
  $('import').onclick=()=>$('import-file').click();
  $('import-file').onchange=async()=>{
    try {
      const file=$('import-file').files[0];if(!file)return;
      if(file.size>2_000_000)throw Error('Review file is too large.');
      const incoming=JSON.parse(await file.text());
      if(incoming.schema!=='sidewalkpilot-beta-comparison-ratings-v1'||!compatiblePackages.includes(incoming.package_id)||incoming.partition!==data.partition
          ||models.some(s=>incoming.models?.[s]?.checkpoint_sha256!==data.models[s].checkpoint_sha256))throw Error('Review belongs to another package or model.');
      const clean=checkedReviews(incoming.reviews);
      if(Object.keys(state.reviews).length&&!confirm('Replace this browser review with the imported review?'))return;
      state.reviews=clean;updateReview();persist();notice('Review imported.');
    }catch(e){notice(e.message);}finally{$('import-file').value='';}
  };
  $('clear').onclick=()=>{if(confirm('Clear ratings and notes for this comparison only?')){state.reviews={};updateReview();persist();notice('Review cleared.');}};
  try {
    const saved=JSON.parse(compatiblePackages.map(id=>localStorage.getItem('sp-beta-comparison:'+id)).find(Boolean)||'null');
    if(saved){if(Array.isArray(saved.visible)&&saved.visible.some(k=>models.includes(k)))visible=models.filter(k=>saved.visible.includes(k));state.reviews=checkedReviews(saved.reviews);if(Number.isInteger(saved.index))state.index=saved.index;if(models.includes(saved.target))state.target=saved.target;if(typeof saved.autoAdvance==='boolean')$('auto-advance').checked=saved.autoAdvance;}
  }catch(_){notice('Saved review could not be loaded. Original masks are unchanged.');}
  $('scope').textContent=data.population?`C/E test partition / ${data.count} of ${data.population.toLocaleString()} images / ${models.length} checkpoints`:`Development ${data.partition} / ${data.count} images`;
  $('unknown-legend').hidden=data.frames.every(f=>record(f,'reference').ignored_pixels===0);
  $('provenance').textContent=data.population?`Random seed ${data.seed} / frozen predictions`:data.comparison_reference_id
    ?`${data.comparison_reference_summary.preserved_binary} original binary / ${data.comparison_reference_summary.derived_binary} derived references / frozen predictions`
    :`${data.binary_references} binary / ${data.partial_references} partial references / frozen predictions`;
  lucide.createIcons();show(state.index,true);
})();
