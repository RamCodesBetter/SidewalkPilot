"""Package exactly the original 10k campaign pairs for a shared grouped C/E experiment."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import shutil
import tempfile

from freeze_ce_partitions import digest, phash, read


def allocate(groups, forced, seed):
    pool = sorted(set(groups) - forced)
    rng = random.Random(seed)
    for _ in range(64):
        rng.shuffle(pool)
        parts = {}
        available = pool.copy()
        for part in ("validation", "test"):
            paths = {0: None}
            for g in available:
                n = len(groups[g])
                for s in list(paths):
                    if s+n <= 1000 and s+n not in paths:
                        paths[s+n] = (s,g)
                if 1000 in paths:
                    break
            if 1000 not in paths:
                break
            selected = set()
            s = 1000
            while s:
                s,g = paths[s]
                selected.add(g)
            parts[part] = selected
            available = [g for g in available if g not in selected]
        if len(parts) == 2:
            parts["train"] = set(available) | forced
            return parts
    raise ValueError("Exact sizes unavailable without splitting a group")


def build(root, out):
    manifest = read(root/"manifest.json")
    frames = sorted(manifest["records"],key=lambda r:(r["recording_run"],r["time"],r["id"]))
    assert len(frames)==len({r["id"] for r in frames})==10000
    source = Path(manifest["source"])
    seen = {r["id"] for r in read(root/"review30/manifest.json")["frames"]}
    parent = list(range(len(frames)))
    def find(i):
        while i != parent[i]:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    def join(i,j):
        parent[find(i)]=find(j)
    bins=defaultdict(dict)
    rows=[]
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage=Path(tmp)/"dataset"
        for d in ("images","masks"):
            (stage/d).mkdir(parents=True)
        for i,r in enumerate(frames):
            image,mask = source/r["image"],root/r["candidates"]
            if r["status"]!="candidate" or digest(image)!=r["id"] or digest(mask)!=r["mask_sha256"]:
                raise ValueError("Campaign pair identity mismatch")
            h=phash(image)
            keys=[(k,(h>>(13*k))&8191) for k in range(5)]
            for key in keys:
                for old,j in bins[key].items():
                    if (h^old).bit_count()<=4:
                        join(i,j)
                bins[key][h]=i
            if i and frames[i-1]["recording_run"]==r["recording_run"] and r["time"]-frames[i-1]["time"]<=0.5:
                join(i,i-1)
            im="images/"+r["image"]
            mk="masks/"+r["id"]+".png"
            shutil.copyfile(image,stage/im)
            shutil.copyfile(mask,stage/mk)
            rows.append(dict(id=r["id"],image=im,mask=mk,mask_sha256=r["mask_sha256"],
                             supervision="pseudo-binary",recording_run=r["recording_run"]))
        groups=defaultdict(list)
        for i,r in enumerate(rows):
            r["group"]=find(i)
            groups[r["group"]].append(r["id"])
        forced={r["group"] for r in rows if r["id"] in seen}
        print("Groups:",len(groups),"largest:",max(map(len,groups.values())),
              "pinned training images:",sum(len(groups[g]) for g in forced),flush=True)
        split=allocate(groups,forced,20261122)
        ids={k:[r["id"] for r in rows if r["group"] in v] for k,v in split.items()}
        assert {k:len(v) for k,v in ids.items()}=={"train":8000,"validation":1000,"test":1000}
        assert seen<=set(ids["train"])
        m=dict(schema="sidewalkpilot-campaign10k-v1",accepted_pseudo=10000,records=rows,
               campaign_sha256=digest(root/"manifest.json"),review_package=read(root/"review30/manifest.json")["package_id"])
        (stage/"manifest.json").write_text(json.dumps(m,indent=2)+"\n")
        sp=dict(partitions=ids,seed=20261122,groups=len(groups),review_frames_partition="train",
                manifest_sha256=digest(stage/"manifest.json"),
                policy="Connected groups: same run gaps <=0.5 seconds or DCT pHash Hamming <=4. Known 30 review frames constrained to training. Evaluation measures agreement with pseudo-labels, not independent human accuracy.")
        (stage/"split.json").write_text(json.dumps(sp,indent=2)+"\n")
        stage.rename(out)
        print({k:len(v) for k,v in ids.items()},len(groups),"groups")


def load(root,split_path):
    m,s=read(root/"manifest.json"),read(split_path)
    if m["schema"]!="sidewalkpilot-campaign10k-v1" or digest(root/"manifest.json")!=s["manifest_sha256"]:
        raise ValueError("Unbound split")
    rows={r["id"]:r for r in m["records"]}
    seen,groups=set(),set()
    parts={}
    for k,n in (("train",8000),("validation",1000),("test",1000)):
        ids=s["partitions"][k]
        gs={rows[i]["group"] for i in ids}
        if len(ids)!=n or len(set(ids))!=n or seen.intersection(ids) or gs&groups:
            raise ValueError("Incorrect size or split leakage")
        seen.update(ids)
        groups.update(gs)
        parts[k]=[rows[i] for i in ids]
    if seen!=set(rows) or len(m["records"])!=10000:
        raise ValueError("Unexpected cohort")
    for i,r in rows.items():
        if digest(root/r["image"])!=i or digest(root/r["mask"])!=r["mask_sha256"]:
            raise ValueError("Pair changed")
    return parts


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("campaign",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    build(a.campaign,a.output)
