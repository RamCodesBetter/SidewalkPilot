"""Package a deterministic variety sample of 30 single-sidewalk candidates for offline review."""
import argparse
import json
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import workspace
workspace.activate()
from label_grounded_sam2 import digest_json, sha256, write_json
from mask_encoding import encode_labels
from prepare_reviewed_dataset import read_json


def package(root,out):
    meta = read_json(root/'manifest.json')
    source = Path(meta['source'])
    pool = sorted((r for r in meta['records'] if r['status']=='candidate'),key=lambda r:r['id'])
    features = []
    for r in pool:
        img = cv2.imread(str(source/r['image']),cv2.IMREAD_REDUCED_COLOR_8)
        hsv = cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
        features.append([r['area'],hsv[:,:,1].mean(),hsv[:,:,2].mean(),hsv[:,:,2].std(),
                         (cv2.Canny(img,60,140)>0).mean()])
    x = np.array(features)
    x = ((x-x.mean(0))/np.maximum(x.std(0),1e-6)).clip(-3,3)
    # Balance the two runs and deliberately include repaired as well as direct masks.
    strata = sorted({(r['recording_run'],r['method']) for r in pool})
    chosen, times = [], {}
    dist = ((x-x.mean(0))**2).sum(1)
    for i in range(30):
        run, method = strata[i%len(strata)]
        def allowed(j):
            r = pool[j]
            return (j not in chosen and all(abs(t-r['time'])>=3 for t in times.get(r['recording_run'],[])))
        options = [j for j,r in enumerate(pool) if (r['recording_run'],r['method'])==(run,method) and allowed(j)]
        if not options:
            options = [j for j in range(len(pool)) if allowed(j)]
        j = max(options,key=lambda j:dist[j])
        chosen.append(j)
        times.setdefault(pool[j]['recording_run'],[]).append(pool[j]['time'])
        delta = ((x-x[j])**2).sum(1)
        dist = delta if i==0 else np.minimum(dist,delta)
    out.mkdir(parents=True,exist_ok=False)
    for folder in ('images','masks'):
        (out/folder).mkdir()
    data = dict(count=30,methods={'codex':'SAM 3 + corridor checks'},review_methods=['codex'],
                annotation_heading='Mask provenance',uncertain_label='Ignored',
                sample_description='10k development batch / 30 variety samples',frames=[])
    sheet = None
    for n,j in enumerate(chosen,1):
        r = pool[j]
        path,mask = source/r['image'], root/r['candidates']
        a = cv2.imread(str(mask),cv2.IMREAD_UNCHANGED)
        assert sha256(path)==r['source_sha256'] and cv2.connectedComponents((a==1).astype('uint8'))[0]==2
        img,seg = f'images/{n:02}.jpg',f'masks/{n:02}.png'
        shutil.copy2(path,out/img)
        shutil.copy2(mask,out/seg)
        data['frames'].append(dict(id=r['id'],name=r['image'],size=list(a.shape[::-1]),image=img,
            source_sha256=r['source_sha256'],annotation_notes=r['method']+'; unverified pseudo-label.',
            methods=dict(codex=dict(mask=seg,positive_pixels=int((a==1).sum()),uncertain_pixels=int((a==255).sum()),
                                    sha256=sha256(mask),rle=encode_labels(a)))))
        with Image.open(path) as src:
            orig = src.convert('RGB')
        over = Image.composite(Image.blend(orig,Image.new('RGB',orig.size,'lime'),.45),orig,Image.fromarray(a==1))
        if (n-1)%5==0:
            sheet = Image.new('RGB',(800,5*245),'white')
        y = ((n-1)%5)*245
        ImageDraw.Draw(sheet).text((4,y+2),f'{n}: {r["method"]}',fill='black')
        for col,view in enumerate((orig,over)):
            view.thumbnail((400,225))
            sheet.paste(view,(col*400,y+18))
        if n%5==0:
            sheet.save(out/f'sheet-{n//5}.jpg',quality=94)
    data['package_id'] = digest_json(data)
    write_json(out/'manifest.json',data)
    (out/'data.js').write_text('window.COMPARISON_DATA='+json.dumps(data,separators=(',',':'))+';')
    for name in ('comparison.css','comparison.js','comparison.html','lucide.min.js','LUCIDE-LICENSE.txt'):
        shutil.copy2(workspace.TOOLS/'review'/name,out/('index.html' if name=='comparison.html' else name))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path)
    p.add_argument('out',type=Path)
    args=p.parse_args()
    package(args.root,args.out)
