"""Resumable SAM 3 campaign. Publish a diverse review only at 10k distinct automatic passes."""
import argparse
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import workspace
workspace.activate()
from compare_sam31_sidewalk import hf_outputs
from label_grounded_sam2 import digest_json, sha256, utc_now, write_json
from label_series5_pseudo import load_runtime
from package_corridor_sample import package
from prepare_reviewed_dataset import read_json, safe_file
from pseudo_mask_filter import filter_masks
from pseudo_training_targets import prepare_target
from sam3_corridor_batch import anchored, iou, timestamp

TARGET = 10000
PROMPTS = ("concrete sidewalk", "sidewalk", "paved pedestrian walkway")
MAC = "ramsabavat@Rams-MacBook-Pro.local"
DEST = "/Users/ramsabavat/Desktop/rc_car_code/code/ai_models_datasets/series_5/reviews/single-sidewalk/pass-10000"


def instance(masks, scores, threshold):
    choices = []
    for raw, score in zip(masks, scores):
        if score < threshold:
            continue
        fg = np.asarray(raw).reshape(raw.shape[-2:]).astype(bool)
        region = anchored(fg)
        # Never select a big island from a clearly fragmented instance.
        if region is not None and (fg & ~region).sum() <= 128 * fg.size / (1280*720):
            choices.append((score,region))
    if not choices:
        return None, "no_confident_anchored_instance"
    choices.sort(key=lambda v:-v[0])
    if any(iou(choices[0][1],r)<.90 for _,r in choices[1:]):
        return None, "competing_sidewalk_instances"
    return choices[0], None


class Detector:
    def __init__(self):
        self.torch,self.model,self.processor,self.native,self.runtime = load_runtime()
        with self.torch.inference_mode(),self.torch.autocast("cuda",dtype=self.torch.bfloat16):
            self.text = {p:self.model.backbone.forward_text([p],device="cuda") for p in PROMPTS}

    def predict(self, im):
        torch = self.torch
        with torch.inference_mode(),torch.autocast("cuda",dtype=torch.bfloat16):
            pixels = self.processor(images=im,return_tensors="pt").pixel_values.to("cuda")
            backbone = self.model.backbone.forward_image(pixels)
            def proposal(i):
                features = {**backbone,**self.text[PROMPTS[i]]}
                raw = self.model.forward_grounding(backbone_out=features,find_input=self.native.find_stage,
                    geometric_prompt=self.model._get_dummy_prompt(),find_target=None)
                if not all(torch.isfinite(raw[k]).all() for k in ("pred_masks","pred_logits","presence_logit_dec")):
                    raise ValueError("Nonfinite SAM result")
                pred = self.processor.post_process_instance_segmentation(
                    hf_outputs(raw,self.model.supervise_joint_box_scores),threshold=.4,mask_threshold=.5,
                    target_sizes=[(im.height,im.width)])[0]
                return instance(pred["masks"].cpu().numpy(),pred["scores"].cpu().tolist(),.65 if i==0 else .55)
            a,reason = proposal(0)
            if a is None:
                return None,[reason],{}
            b,reason = proposal(1)
            j=1
            if b is None and reason=="no_confident_anchored_instance":
                j=2
                b,reason=proposal(j)
            if b is None:
                return None,[reason],{}
            mask, detail=filter_masks(a[1],b[1],[a[0],b[0]])
            if detail["reasons"]:
                return None,detail["reasons"],{}
            labels,_=prepare_target(mask)
            fg=labels==1
            region=anchored(fg)
            if region is None or not np.array_equal(region,fg) or (labels==0).mean()<.03:
                return None,["invalid_final_corridor"],{}
            return labels,[],dict(method="grounded_prompt_pair_"+str(j),prompt_iou=detail["prompt_iou"],
                                  scores=detail["top_scores"],area=float(fg.mean()))


def mirror(out, final=False):
    args=["-o","BatchMode=yes","-o","ConnectTimeout=5"]
    try:
        subprocess.run(["ssh",*args,MAC,"mkdir -p "+DEST],check=True,timeout=12)
        paths=[str(out/"STATUS.txt"),str(out/"progress.json")]
        if final:
            paths.append(str(out/"review30"))
        subprocess.run(["scp",*args,"-r",*paths,MAC+":"+DEST+"/"],check=True,timeout=180)
    except (subprocess.SubprocessError,OSError) as exc:
        print("Mac unavailable; local report retained:",exc,flush=True)


def work(args):
    root,out=args.history,args.output
    cv2.setNumThreads(1)
    os.environ["HF_HUB_OFFLINE"]="1"
    os.environ["TRANSFORMERS_OFFLINE"]="1"
    out.mkdir(parents=True,exist_ok=True)
    lock=(out/"worker.lock").open("a")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for name in ("loops","candidates"):
        (out/name).mkdir(exist_ok=True)
    inventory=root/"series5-5CD-labeling/manifest.json"
    m=read_json(inventory)
    banned=set(m["visual_exclusions"])
    for path in [root/"sam3-single-10k-v1/review30/manifest.json",root/"single-sidewalk-batch-001/selection.json"]:
        banned.update(r["id"] for r in read_json(path)["frames"])
    rows=[r for r in m["frames"] if r["training_eligible"] and not r["existing_review"]
          and r["id"] not in banned and all(a["day"] in m["train_days"] for a in r["aliases"])]
    assert len(rows)==len({r["id"] for r in rows})
    random.Random(220611).shuffle(rows)
    source=Path(m["source"])
    contract=dict(target=TARGET,loop_size=args.loop_size,inventory=sha256(inventory),
                  order=digest_json([r["id"] for r in rows]),prompts=PROMPTS,
                  code={p:sha256(workspace.source_path(p)) for p in
                        [Path(__file__).name,"sam3_corridor_batch.py","pseudo_mask_filter.py",
                         "pseudo_training_targets.py","label_series5_pseudo.py","compare_sam31_sidewalk.py"]})
    identity=digest_json(contract)
    spec=out/"policy.json"
    if spec.exists() and read_json(spec)["identity"]!=identity:
        raise ValueError("Frozen policy changed; not mixing campaigns")
    write_json(spec,dict(identity=identity,contract=contract))
    history=[]
    accepted=[]
    attempted=0
    def publish(state):
        summary=dict(state=state,updated_utc=utc_now(),loops=len(history),attempted=attempted,
                     passed=len(accepted),deferred=attempted-len(accepted),remaining=TARGET-len(accepted),
                     eligible=len(rows),last_loop=history[-1] if history else None,
                     human_verified=False,scope="Automated screening, no final research test or training")
        write_json(out/"progress.json",summary)
        tmp=out/"STATUS.tmp"
        with tmp.open("w") as f:
            print("SAM 3 single-sidewalk campaign | "+state,file=f)
            print("Loop   Attempted  Passed  Deferred  Total passed  Still needed (of 10,000)",file=f)
            for h in history:
                print("{loop:4d}   {attempted:9d}  {passed:6d}  {deferred:8d}  {total:12d}  {remaining:12d}".format(**h),file=f)
        tmp.replace(out/"STATUS.txt")
        print(json.dumps(summary),flush=True)
        if args.mac:
            mirror(out, state=="target_reached")
    def account(result):
        nonlocal attempted
        assert result["identity"]==identity
        batch=result["records"]
        if [r["id"] for r in batch]!=[r["id"] for r in rows[attempted:attempted+len(batch)]]:
            raise ValueError("Loop identity mismatch")
        passed=[r for r in batch if r["status"]=="candidate"]
        accepted.extend(passed)
        attempted+=len(batch)
        history.append(dict(loop=len(history)+1,attempted=len(batch),passed=len(passed),
                            deferred=len(batch)-len(passed),total=len(accepted),remaining=TARGET-len(accepted),
                            flags=dict(Counter(s for r in batch for s in r.get("reasons",[])))))
    for path in sorted((out/"loops").glob("*.json")):
        result=read_json(path)
        for row in result["records"]:
            if row["status"]=="candidate" and sha256(out/row["candidates"])!=row["mask_sha256"]:
                raise ValueError("Saved candidate changed")
        account(result)
    publish("running")
    try:
        detector=Detector() if attempted<len(rows) and len(accepted)<TARGET else None
        while attempted<len(rows) and len(accepted)<TARGET:
            if shutil.disk_usage(out).free<20*1024**3:
                raise RuntimeError("Less than 20 GiB free")
            batch=[]
            new=0
            for frame in rows[attempted:attempted+args.loop_size]:
                path=safe_file(source,frame["image"])
                if sha256(path)!=frame["id"]:
                    raise ValueError("Source changed")
                with Image.open(path) as im:
                    labels,reasons,detail=detector.predict(im.convert("RGB"))
                row={k:frame[k] for k in ("id","image","source_sha256","recording_run")}
                row.update(status="deferred",reasons=reasons,human_verified=False)
                if labels is not None:
                    rel="candidates/"+row["id"]+".png"
                    p=out/rel
                    tmp=p.with_suffix(".tmp.png")
                    if not cv2.imwrite(str(tmp),labels,[cv2.IMWRITE_PNG_COMPRESSION,3]):
                        raise OSError(tmp)
                    tmp.replace(p)
                    row.update(status="candidate",candidates=rel,mask_sha256=sha256(p),time=timestamp(row),**detail)
                    new+=1
                batch.append(row)
                if len(accepted)+new==TARGET:
                    break
            result=dict(identity=identity,records=batch)
            write_json(out/"loops"/f"{len(history)+1:05d}.json",result)
            account(result)
            publish("running")
        if len(accepted)==TARGET:
            write_json(out/"manifest.json",dict(source=str(source),identity=identity,records=accepted))
            if not (out/"review30").exists():
                temp=out/"review30-building"
                if temp.exists():
                    raise ValueError("Incomplete review build already exists")
                package(out,temp)
                temp.rename(out/"review30")
            publish("target_reached")
        else:
            publish("eligible_pool_exhausted")
    except BaseException as exc:
        publish("stopped: "+repr(exc))
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--loop-size",type=int,default=128)
    parser.add_argument("--mac",action="store_true")
    args=parser.parse_args()
    if args.loop_size<1:
        parser.error("loop size must be positive")
    work(args)
