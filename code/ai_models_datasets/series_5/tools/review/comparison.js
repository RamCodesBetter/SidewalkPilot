/* Offline mask review: all images and RLE pixels are package-local. */
(() => {
  'use strict';
  const data = window.COMPARISON_DATA;
  const $ = id => document.getElementById(id);
  const methods = Object.keys(data.methods);
  const reviewMethods = data.review_methods || methods;
  if(!reviewMethods.length || reviewMethods.some(m=>!methods.includes(m)))throw Error('Invalid review scope.');
  const sides = ['original', ...methods];
  const decisions = ['unreviewed', 'correct', 'needs_correction', 'uncertain'];
  const labels = {unreviewed:'Unreviewed', correct:'Correct', needs_correction:'Needs correction', uncertain:'Uncertain'};
  const levels = {1:'Minor fixes',2:'Moderate fixes',3:'Major fixes'};
  const storageKey = 'sp-three-method:' + data.package_id;
  const state = {index:0, method:'codex', mode:'overlay', layout:'grid', opacity:40, zoom:1, reviews:{}};
  let pixels = {}, loadEpoch = 0, syncing = false, ready = false;

  function decode(rle, size) {
    if (!Array.isArray(rle) || !rle.length || rle.length % 2) throw Error('Invalid mask RLE.');
    const result = new Uint8Array(size); let offset = 0;
    for (let i=0;i<rle.length;i+=2) {
      const value=rle[i], count=rle[i+1];
      if (![0,1,255].includes(value) || !Number.isInteger(count) || count<=0 || offset+count>size) throw Error('Invalid mask pixels.');
      result.fill(value,offset,offset+count); offset+=count;
    }
    if (offset!==size) throw Error('Incomplete mask.');
    return result;
  }

  function checkedReviews(reviews) {
    if (!reviews || typeof reviews!=='object' || Array.isArray(reviews)) throw Error('Invalid review records.');
    const frames=new Map(data.frames.map(f=>[f.id,f])); const clean={};
    for (const [id,row] of Object.entries(reviews)) {
      const frame=frames.get(id);
      if (!frame || !row || row.source_sha256!==frame.source_sha256 || typeof row.notes!=='string' || row.notes.length>20000 || !row.methods || typeof row.methods!=='object') throw Error('Review source identity differs.');
      const m={};
      for (const [key,value] of Object.entries(row.methods)) {
        if (!reviewMethods.includes(key) || !value || !decisions.includes(value.decision) || value.sha256!==frame.methods[key].sha256) throw Error('Review mask identity or decision differs.');
        m[key]={decision:value.decision,sha256:value.sha256};
        if (value.correction_level != null) {
          if (value.decision!=='needs_correction' || ![1,2,3].includes(value.correction_level)) throw Error('Invalid correction level.');
          m[key].correction_level=value.correction_level;
        }
      }
      clean[id]={source_sha256:row.source_sha256,notes:row.notes,methods:m};
    }
    return clean;
  }

  try {
    const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
    if (saved) {
      state.reviews=checkedReviews(saved.reviews);
      if (Number.isInteger(saved.index)) state.index=Math.max(0,Math.min(data.count-1,saved.index));
      if (reviewMethods.includes(saved.method)) state.method=saved.method;
    }
  } catch(error) { $('message').textContent='Saved review could not be loaded. Import your exported JSON to recover it.'; }

  function persist() {
    try { localStorage.setItem(storageKey,JSON.stringify({index:state.index,method:state.method,reviews:state.reviews})); $('saved').textContent='Saved in this browser'; }
    catch(error) { $('saved').textContent='Browser storage unavailable; export your review.'; }
  }
  function current() { return data.frames[state.index]; }
  function review(create=false) {
    const frame=current();
    if (!state.reviews[frame.id] && create) state.reviews[frame.id]={source_sha256:frame.source_sha256,notes:'',methods:{}};
    return state.reviews[frame.id];
  }
  function decision(method) { return review()?.methods[method]?.decision||'unreviewed'; }

  for (const side of sides) {
    const pane=document.createElement('section'); pane.className='pane'; pane.id='pane-'+side;
    const heading=document.createElement('div'); heading.className='pane-heading';
    const title=document.createElement(reviewMethods.includes(side)?'button':'span'); title.className='pane-title';
    title.textContent=side==='original'?'Original':data.methods[side];
    if (reviewMethods.includes(side)) {title.dataset.method=side;title.title='Select '+data.methods[side];title.addEventListener('click',()=>select(side));}
    const status=document.createElement('span');status.className='status';status.id='status-'+side;
    heading.append(title,status);
    const stage=document.createElement('div');stage.className='stage';stage.id='stage-'+side;stage.tabIndex=0;stage.setAttribute('aria-label',(data.methods[side]||'Original')+' image');
    const box=document.createElement('div');box.className='imagebox';box.id='box-'+side;
    const img=document.createElement('img');img.id='image-'+side;img.alt='Original sidewalk photograph';
    box.append(img);
    if(side!=='original'){const c=document.createElement('canvas');c.id='canvas-'+side;c.setAttribute('aria-label',data.methods[side]+' mask');box.append(c);}
    stage.append(box);
    const stat=document.createElement('div');stat.className='pane-stat';stat.id='stat-'+side;
    pane.append(heading,stage,stat);$('panes').append(pane);
    stage.addEventListener('scroll',()=>{
      if(syncing)return;syncing=true;
      const x=stage.scrollLeft/Math.max(1,stage.scrollWidth-stage.clientWidth),y=stage.scrollTop/Math.max(1,stage.scrollHeight-stage.clientHeight);
      for(const other of sides){if(other===side)continue;const s=$('stage-'+other);s.scrollLeft=x*(s.scrollWidth-s.clientWidth);s.scrollTop=y*(s.scrollHeight-s.clientHeight);}
      requestAnimationFrame(()=>{syncing=false;});
    });
  }

  function updateReview() {
    for (const method of methods) {
      const level=review()?.methods[method]?.correction_level;
      $('status-'+method).textContent=reviewMethods.includes(method)?(levels[level]||labels[decision(method)]):'Reference';
      $('status-'+method).title=level?`Needs correction: level ${level}`:labels[decision(method)];
      $('pane-'+method).classList.toggle('selected',state.method===method);
      document.querySelector(`[data-method="${method}"]`)?.setAttribute('aria-pressed',String(state.method===method));
    }
    $('status-original').textContent='Source';
    $('method').value=state.method;
    for (const button of document.querySelectorAll('[data-decision]')) button.setAttribute('aria-pressed',String(button.dataset.decision===decision(state.method)));
    let count=0;for(const row of Object.values(state.reviews))for(const method of reviewMethods)if(row.methods[method] && row.methods[method].decision!=='unreviewed')count++;
    $('progress').textContent=`${count} / ${data.count*reviewMethods.length} ratings`;
    $('notes').value=review()?.notes||'';
  }
  function closeLevel() {if($('correction-dialog').open)$('correction-dialog').close();}
  function select(method) {if(!reviewMethods.includes(method))return;closeLevel();state.method=method;updateReview();persist();}
  function mark(value) {
    if(!ready || !reviewMethods.includes(state.method))return;
    const previousLevel=review()?.methods[state.method]?.correction_level;
    review(true).methods[state.method]={decision:value,sha256:current().methods[state.method].sha256};
    if(value==='needs_correction' && previousLevel)review().methods[state.method].correction_level=previousLevel;
    updateReview();persist();
    if(value==='needs_correction'){
      $('correction-context').textContent=`${data.methods[state.method]} / ${current().source_sample_id||'Image '+(state.index+1)} / ${state.index+1} of ${data.count}`;
      document.querySelectorAll('[data-level]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.level)===previousLevel)));
      $('correction-dialog').showModal();
      document.querySelector('[data-level="1"]').focus();
    }else closeLevel();
  }
  function setLevel(level) {
    if(!ready || decision(state.method)!=='needs_correction' || ![1,2,3].includes(level))return;
    review(true).methods[state.method].correction_level=level;
    closeLevel();updateReview();persist();
  }
  function draw() {
    if(!ready)return;
    for(const method of methods){
      const canvas=$('canvas-'+method),values=pixels[method];
      canvas.style.display=state.mode==='source'?'none':'block';
      const ctx=canvas.getContext('2d'),frame=ctx.createImageData(canvas.width,canvas.height);
      for(let i=0;i<values.length;i++){
        const v=values[i],p=i*4,x=i%canvas.width,y=Math.floor(i/canvas.width);
        if(v===1){frame.data[p]=50;frame.data[p+1]=197;frame.data[p+2]=144;frame.data[p+3]=state.mode==='mask'?255:Math.round(state.opacity*2.55);}
        else if(v===255){const stripe=(x+y)%16<3;frame.data[p]=stripe?110:237;frame.data[p+1]=stripe?76:182;frame.data[p+2]=stripe?20:73;frame.data[p+3]=state.mode==='mask'?255:Math.round(state.opacity*2.55);}
        else if(state.mode==='mask'){frame.data[p]=25;frame.data[p+1]=31;frame.data[p+2]=33;frame.data[p+3]=255;}
      }
      ctx.putImageData(frame,0,0);
    }
  }
  function setZoom(zoom) {
    state.zoom=Math.max(1,Math.min(4,zoom));
    for(const side of sides){$('box-'+side).style.width=(state.zoom*100)+'%';if(state.zoom===1){$('stage-'+side).scrollLeft=0;$('stage-'+side).scrollTop=0;}}
    $('zoom-value').textContent=Math.round(state.zoom*100)+'%';$('zoom-out').disabled=state.zoom===1;$('zoom-in').disabled=state.zoom===4;
  }
  async function show(index) {
    closeLevel();
    const epoch=++loadEpoch;ready=false;document.body.classList.add('loading');
    state.index=Math.max(0,Math.min(data.count-1,index));const frame=current();
    $('position').value=state.index+1;$('position').max=data.count;$('total').textContent='/ '+data.count;
    $('previous').disabled=state.index===0;$('next').disabled=state.index===data.count-1;
    $('filename').textContent=(frame.source_sample_id?frame.source_sample_id+' / ':'')+frame.name;$('annotation-notes').textContent=frame.annotation_notes;
    pixels={};
    try {
      for(const method of methods){
        const mask=frame.methods[method],canvas=$('canvas-'+method);canvas.width=frame.size[0];canvas.height=frame.size[1];
        pixels[method]=decode(mask.rle,frame.size[0]*frame.size[1]);
        const area=100*mask.positive_pixels/(frame.size[0]*frame.size[1]);
        const uncertain=100*mask.uncertain_pixels/(frame.size[0]*frame.size[1]);
        $('stat-'+method).textContent=`Sidewalk area ${area.toFixed(1)}%`+(method==='codex'?` / uncertain ${uncertain.toFixed(1)}%`:'');
      }
      $('stat-original').textContent=`${frame.size[0]} x ${frame.size[1]}`;
      await Promise.all(sides.map(side=>new Promise((resolve,reject)=>{const img=$('image-'+side);img.onload=resolve;img.onerror=()=>reject(Error('Source image could not load. Keep the images folder beside index.html.'));img.src=frame.image;})));
      if(epoch!==loadEpoch)return;
      ready=true;document.body.classList.remove('loading');setZoom(state.zoom);draw();updateReview();persist();
      for(const side of sides){$('stage-'+side).scrollLeft=0;$('stage-'+side).scrollTop=0;}
    } catch(error){if(epoch===loadEpoch){$('message').textContent=error.message;document.body.classList.remove('loading');}}
  }

  $('previous').onclick=()=>show(state.index-1);$('next').onclick=()=>show(state.index+1);
  $('position').onchange=()=>{const n=Number($('position').value);show(Number.isFinite(n)?Math.trunc(n)-1:state.index);};
  $('method').onchange=()=>select($('method').value);
  document.querySelectorAll('[data-decision]').forEach(b=>b.onclick=()=>mark(b.dataset.decision));
  document.querySelectorAll('[data-level]').forEach(b=>b.onclick=()=>setLevel(Number(b.dataset.level)));
  $('close-correction').onclick=closeLevel;
  document.querySelectorAll('input[name=mode]').forEach(r=>r.onchange=()=>{state.mode=r.value;draw();});
  document.querySelectorAll('button[data-layout]').forEach(b=>b.onclick=()=>{state.layout=b.dataset.layout;$('panes').dataset.layout=state.layout;document.querySelectorAll('button[data-layout]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});
  $('opacity').oninput=()=>{state.opacity=Number($('opacity').value);$('opacity-value').textContent=state.opacity+'%';draw();};
  $('zoom-in').onclick=()=>setZoom(state.zoom+.5);$('zoom-out').onclick=()=>setZoom(state.zoom-.5);$('fit').onclick=()=>setZoom(1);
  $('notes').oninput=()=>{review(true).notes=$('notes').value.slice(0,20000);persist();};
  document.addEventListener('keydown',event=>{
    if(event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,textarea,select,[contenteditable=true]'))return;
    if(event.repeat)return;
    if($('correction-dialog').open){
      if(['1','2','3'].includes(event.key)){event.preventDefault();setLevel(Number(event.key));}
      return;
    }
    if(event.key==='Enter'||event.key==='ArrowRight'){event.preventDefault();show(state.index+1);}
    else if(event.key==='ArrowLeft'){event.preventDefault();show(state.index-1);}
    else if(['1','2','3'].includes(event.key)){event.preventDefault();mark(['correct','needs_correction','uncertain'][Number(event.key)-1]);}
  });
  $('export').onclick=()=>{
    const blob=new Blob([JSON.stringify({schema:'sidewalkpilot-three-method-review-v1',package_id:data.package_id,review_methods:reviewMethods,exported_utc:new Date().toISOString(),reviews:state.reviews},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='sidewalkpilot-three-method-review.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  $('import').onclick=()=>$('import-file').click();
  $('import-file').onchange=async()=>{
    const file=$('import-file').files[0];if(!file)return;
    try {const value=JSON.parse(await file.text());if(value.schema!=='sidewalkpilot-three-method-review-v1'||value.package_id!==data.package_id)throw Error('Review belongs to another package.');
      const clean=checkedReviews(value.reviews);if(Object.keys(state.reviews).length&&!confirm('Replace this package\'s current ratings with the imported review?'))return;
      state.reviews=clean;updateReview();persist();$('message').textContent='Review imported.';
    }catch(error){$('message').textContent=error.message;}finally{$('import-file').value='';}
  };
  $('clear').onclick=()=>{if(confirm(`Clear ratings and notes for this ${data.count}-image comparison only? Export first to keep a copy.`)){state.reviews={};updateReview();persist();}};
  for(const option of Array.from($('method').options)){
    if(!reviewMethods.includes(option.value))option.remove();
    else option.textContent=data.methods[option.value];
  }
  $('annotation-heading').textContent=data.annotation_heading||'Codex annotation notes';
  $('uncertain-label').textContent=data.uncertain_label||'Codex uncertain';
  $('method').disabled=reviewMethods.length===1;
  $('sample').textContent=(data.sample_description||`${data.count} images / random seed ${data.seed}`)+(data.annotation_revision?` / Revision ${data.annotation_revision}`:'');
  window.lucide.createIcons();show(state.index);
})();
