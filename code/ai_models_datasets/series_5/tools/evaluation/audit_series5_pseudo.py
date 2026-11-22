#!/usr/bin/env python3
"""Report training-reference agreement and create retained-label inspection panels."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import workspace as _workspace
_workspace.activate()

import argparse
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image

from label_grounded_sam2 import sha256, write_json, utc_now
from label_series5_pseudo import load_selection, panel
from prepare_reviewed_dataset import read_json, safe_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--panels',type=int,default=12)
    parser.add_argument('--seed', type=int, help='Seeded sample across all retained cases instead of the first cases')
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a new audit directory')
    args.output.mkdir(parents=True)
    manifest=read_json(args.run/'manifest.json')
    selection=load_selection(Path(manifest['selection']))
    refs={r['id']:r for r in read_json(args.dataset/'manifest.json')['records'] if r['supervision']=='binary-reference'}
    retained = []
    for frame in selection['frames']:
        record_path = args.run/'records'/(frame['id']+'.json')
        if record_path.exists() and read_json(record_path)['filter']['accepted_for_pseudo_training']:
            retained.append(frame['id'])
    chosen = set(random.Random(args.seed).sample(retained, min(args.panels, len(retained)))
                 if args.seed is not None else retained[:args.panels])
    results=[]; count=0; inspected=[]
    for number,frame in enumerate(selection['frames'],1):
        record_path=args.run/'records'/(frame['id']+'.json')
        if not record_path.exists():continue
        record=read_json(record_path)
        if record['frame']!=frame or record['contract_sha256']!=manifest['contract_sha256']:raise ValueError('Record identity differs')
        path=safe_file(args.run,record['mask']['path'])
        if sha256(path)!=record['mask']['sha256']:raise ValueError('Mask changed')
        if frame['id'] in refs or frame['id'] in chosen:
            with Image.open(path) as im:labels=np.array(im)
        if frame['id'] in refs:
            row=refs[frame['id']]
            with Image.open(safe_file(args.dataset,row['mask'])) as im:ref=np.array(im)
            positive=labels==1;valid=ref!=255;known=(labels!=255)&valid
            tp=int((positive&(ref==1)).sum());fp=int((positive&(ref==0)).sum());fn=int((~positive&(ref==1)).sum())
            ratio=lambda a,b:a/b if b else None
            results.append({'id':frame['id'],'image':frame['image'],'retained':record['filter']['accepted_for_pseudo_training'],
                'precision':ratio(tp,tp+fp),'recall_with_ignored_predictions_counted_missing':ratio(tp,tp+fn),
                'iou_with_ignored_predictions_counted_missing':ratio(tp,tp+fp+fn),
                'known_label_agreement':float((labels[known]==ref[known]).mean()) if known.any() else None,
                'known_reference_fraction':float(known.sum()/valid.sum()) if valid.any() else None})
        if frame['id'] in chosen:
            count+=1
            with Image.open(safe_file(Path(selection['source']),frame['image'])) as im:image=im.convert('RGB')
            proposals=[]
            for asset in record['raw']:
                path=safe_file(args.run,asset['path'])
                if sha256(path)!=asset['sha256']:raise ValueError('Raw proposal changed')
                with Image.open(path) as im:proposals.append(np.array(im)==1)
            panel(args.output/f'{count:02d}.jpg',image,proposals,labels,record['filter'])
            inspected.append({'panel':f'{count:02d}.jpg','selection_index':number,'id':frame['id'],'image':frame['image']})
    accepted=[r for r in results if r['retained']]
    summary={'reference_images':len(results),'retained_reference_images':len(accepted),
        'mean_precision':float(np.mean([r['precision'] for r in accepted])) if accepted else None,
        'minimum_precision':min((r['precision'] for r in accepted),default=None),
        'mean_recall':float(np.mean([r['recall_with_ignored_predictions_counted_missing'] for r in accepted])) if accepted else None}
    write_json(args.output/'audit.json',{'created_utc':utc_now(),'run_contract_sha256':manifest['contract_sha256'],
        'summary':summary,'reference_comparisons':results,'panels':inspected,
        'panel_sampling': {'seed': args.seed, 'retained_pool': len(retained), 'sample_size': len(chosen)},
        'scope':'Training-reference diagnostic or qualitative sample only, not an independent accuracy estimate. Panels are not automatically accepted by a human.'})
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
