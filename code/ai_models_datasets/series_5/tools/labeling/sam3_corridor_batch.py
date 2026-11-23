"""Screen cached native SAM 3 labels and attempt a same-run temporal repair of deferred frames."""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workspace
workspace.activate()
from label_grounded_sam2 import sha256, write_json
from label_series5_pseudo import load_selection
from prepare_reviewed_dataset import read_json, safe_file
from pseudo_training_targets import prepare_target


def anchored(mask):
    """Require exactly one region meeting a near-camera anchor; never union detached islands."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'), connectivity=8)
    h, w = mask.shape
    ids, counts = np.unique(labels[int(h*.9):, int(.35*w):int(.65*w)], return_counts=True)
    choices = [i for i,c in zip(ids, counts) if i and c > .003*h*w]
    if len(choices) != 1:
        return None
    selected = labels == choices[0]
    if not .15 <= selected.mean() <= .94:
        return None
    return selected


def timestamp(row):
    return (datetime.strptime(row['image'].split('__photo_')[1][:-4], '%Y%m%d_%H%M%S_%f')
            - datetime(2000, 1, 1)).total_seconds()


def read_mask(path):
    a = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if a is None or a.ndim != 2:
        raise ValueError(f'Invalid mask: {path}')
    return a


def iou(a,b):
    return np.count_nonzero(a & b) / max(1,np.count_nonzero(a | b))


def run(args):
    cv2.setNumThreads(1)
    base, out = args.baseline, args.output
    selection_path = base/'selection-10000.json'
    selection = load_selection(selection_path)
    frames, source, sam = selection['frames'], Path(selection['source']), base/'labels-v1'
    contract = read_json(sam/'manifest.json')
    exclusions = read_json(base/'visual-exclusions.json')
    if (len(frames) != 10000 or read_json(sam/'status.json')['status'] != 'complete'
            or exclusions['run_contract_sha256'] != contract['contract_sha256']
            or sha256(selection_path) != contract['contract']['selection_sha256']):
        raise ValueError('Expected the matched 10k SAM3 selection, predictions and exclusions')
    banned = {r['id'] for r in exclusions['records']}
    out.mkdir(parents=True, exist_ok=False)
    for name in ('drafts','candidates'):
        (out/name).mkdir()

    def write(row, labels, folder):
        dest = out/folder/(row['id']+'.png')
        if not cv2.imwrite(str(dest), labels, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
            raise OSError(dest)
        row[folder] = str(dest.relative_to(out))

    def initial(frame):
        fid = frame['id']
        source_path = safe_file(source,frame['image'])
        rec = read_json(sam/'records'/(fid+'.json'))
        if (rec['frame'] != frame or rec['contract_sha256'] != contract['contract_sha256']
                or sha256(source_path) != frame['source_sha256']):
            raise ValueError(f'Source or prediction mismatch: {fid}')
        row = dict(**frame, original_flags=rec['filter']['reasons'], time=timestamp(frame),
                   human_verified=False, status='deferred')
        if fid in banned:
            row['reason'] = 'prior_visual_exclusion'
            return row
        a = rec['mask']
        path = safe_file(sam,a['path'])
        if sha256(path) != a['sha256']:
            raise ValueError(path)
        if not row['original_flags']:
            labels, _ = prepare_target(read_mask(path))
            fg = labels == 1
            region = anchored(fg)
            if region is not None and np.array_equal(region,fg) and (labels==0).mean() >= .03:
                write(row,labels,'candidates')
                row.update(status='candidate', method='two_prompt_consensus', area=float(fg.mean()))
                return row
        # A single plausible prompt is only a draft. It cannot pass on confidence alone.
        for raw in rec['raw']:
            path = safe_file(sam,raw['path'])
            if sha256(path) != raw['sha256']:
                raise ValueError(path)
            if max(raw['scores'],default=0) < .4:
                continue
            region = anchored(read_mask(path) != 0)
            if region is not None:
                write(row,region.astype('uint8'),'drafts')
                break
        row['reason'] = 'insufficient_independent_support'
        return row

    def mapped(pool, func, rows):
        result = []
        for i,row in enumerate(pool.map(func,rows),1):
            result.append(row)
            if i % 2000 == 0:
                print(func.__name__,i,flush=True)
        return result

    with ThreadPoolExecutor(args.jobs) as pool:
        rows = mapped(pool,initial,frames)
        anchors = defaultdict(list)
        for row in rows:
            if row['status']=='candidate':
                anchors[row['recording_run']].append((row['time'],row['id'],row))
        for items in anchors.values():
            items.sort(key=lambda v:v[:2])

        def small_gray(row):
            return cv2.resize(cv2.imread(str(source/row['image']),cv2.IMREAD_GRAYSCALE),
                              (320,180), interpolation=cv2.INTER_AREA)

        def repair(row):
            if row['status']=='candidate' or 'drafts' not in row:
                return row
            items = anchors[row['recording_run']]
            j = bisect_left(items,(row['time'],''))
            if j==0 or j==len(items):
                return row
            neighbors = [items[j-1],items[j]]
            if any(abs(t-row['time']) > 2 for t,_,_ in neighbors):
                return row
            draft = read_mask(out/row['drafts']).astype(bool)
            small = small_gray(row)
            yy,xx = np.indices(small.shape,dtype='float32')
            support = []
            for _,_,ref in neighbors:
                image = small_gray(ref)
                flow = cv2.calcOpticalFlowFarneback(small,image,None,.5,3,15,3,5,1.2,0)
                x,y = xx+flow[:,:,0], yy+flow[:,:,1]
                warped = cv2.remap(image,x,y,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
                if np.mean(cv2.absdiff(warped,small)) > 12:
                    return row
                prior = cv2.resize((read_mask(out/ref['candidates'])==1).astype('uint8'),
                                   (320,180),interpolation=cv2.INTER_NEAREST)
                mask = cv2.remap(prior,x,y,cv2.INTER_NEAREST).astype(bool)
                mask = cv2.resize(mask.astype('uint8'),draft.shape[::-1],interpolation=cv2.INTER_NEAREST).astype(bool)
                if iou(mask,draft)<.93:
                    return row
                support.append(mask)
            fg = draft & support[0] & support[1]
            region = anchored(fg)
            if region is None or not np.array_equal(region,fg):
                return row
            labels = np.full(draft.shape,255,'uint8')
            labels[~(draft|support[0]|support[1])] = 0
            labels[fg] = 1
            if (labels==0).mean()<.03:
                return row
            write(row,labels,'candidates')
            row.update(status='candidate',method='temporal_consensus',area=float(fg.mean()),
                       supporting_frames=[n[1] for n in neighbors])
            del row['reason']
            return row
        rows = mapped(pool,repair,rows)
    write_json(out/'manifest.json',dict(source=str(source), selection_sha256=sha256(selection_path),
               sam_contract=contract['contract_sha256'], runner_sha256=sha256(Path(__file__)),
               scope='Development pseudo-labels. Drafts and deferred records are not training references.',
               records=rows))
    print(Counter(r.get('method','deferred') for r in rows),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--jobs',type=int,default=12)
    run(p.parse_args())
