/* Pixel metrics on known reference pixels, never on ignored pixels. */
(() => {
  'use strict';
  function score(prediction, reference, supervision) {
    if (prediction.length!==reference.length || !['binary-reference','derived-binary-reference','sidewalk-positive-only','pseudo-binary'].includes(supervision)) {
      throw Error('Invalid metric inputs.');
    }
    let tp=0,fp=0,fn=0,tn=0,ignored=0;
    for(let i=0;i<reference.length;i++) {
      const p=prediction[i],r=reference[i];
      if(![0,1].includes(p)||![0,1,255].includes(r))throw Error('Invalid metric label.');
      if(r===255){ignored++;continue;}
      if(r===1){if(p===1)tp++;else fn++;}
      else {if(p===1)fp++;else tn++;}
    }
    const binary=supervision!=='sidewalk-positive-only';
    const ratio=(a,b)=>b?a/b:null;
    if(supervision==='derived-binary-reference' && ignored)throw Error('Derived binary references must not contain unknown pixels.');
    const sidewalkIoU=binary?ratio(tp,tp+fp+fn):null;
    const backgroundIoU=binary?ratio(tn,tn+fp+fn):null;
    const validIoUs=[sidewalkIoU,backgroundIoU].filter(value=>value!==null);
    return {precision:binary?ratio(tp,tp+fp):null,recall:ratio(tp,tp+fn),
      f1:binary?ratio(2*tp,2*tp+fp+fn):null,
      sidewalk_iou:sidewalkIoU,background_iou:backgroundIoU,
      miou:validIoUs.length?validIoUs.reduce((a,b)=>a+b,0)/validIoUs.length:null,
      scope:supervision==='derived-binary-reference'?'provisional-derived-reference':binary?'known-reference-pixels':'known-sidewalk-only',
      tp,fn,fp:binary?fp:null,tn:binary?tn:null,ignored,
      scored_pixels:binary?tp+fp+fn+tn:tp+fn,total_pixels:reference.length};
  }
  function higherDisplayed(a,b) {
    if(!Number.isFinite(a)||!Number.isFinite(b))return null;
    const left=Number((100*a).toFixed(2)),right=Number((100*b).toFixed(2));
    return left===right?null:left>right?'a':'b';
  }
  const api={score,higherDisplayed};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else window.MODEL_REVIEW_METRICS=api;
})();
