"""Evaluate saved Series 5 class-ID predictions against reference PNGs and build a local report."""
import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
import sys
import tempfile
from pathlib import Path
from statistics import mean

import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image as Figure, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from evaluate_sidewalkpilot_models import make_table, add_metric_gradients, plt

def counts(frames):
    return tuple(sum(f["matrix"][i][j] for f in frames) for i, j in [(0, 0), (0, 1), (1, 0), (1, 1)])


def scores(frames):
    tn, fp, fn, tp = counts(frames)
    def ratio(x, y):
        return x / y if y else None
    sw, bg = ratio(tp, tp+fp+fn), ratio(tn, tn+fp+fn)
    defined = [v for v in (sw, bg) if v is not None]
    return (ratio(tp,tp+fp), ratio(tp,tp+fn), ratio(2*tp,2*tp+fp+fn), sw, bg, mean(defined) if defined else None)


RUNS = {"5.A":"series5-5.A-training/5.A-run-001", "5.B":"series5-5.B/5.B-run-001",
        "5.C":"series5-ce-grouped/5.C-campaign-run-001", "5.E":"series5-ce-grouped/5.E-campaign-run-001"}


def read_labels(root, record, allowed):
    path = (root / record["path"]).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError(f"Mask path or hash mismatch: {path.name}")
    with Image.open(path) as im:
        pixels = np.array(im)
    if pixels.ndim != 2 or not np.isin(pixels, allowed).all():
        raise ValueError(f"Expected class IDs, not a visible preview: {path.name}")
    return pixels


def evaluate(bundle, history):
    manifest = json.loads((bundle/"manifest.json").read_text())
    frames = manifest["frames"]
    ids = {f["id"] for f in frames}
    if manifest["partition"] != "test" or len(ids) != len(frames) or len(ids) != manifest["count"]:
        raise ValueError("Expected unique test frames")
    models, overlaps = {}, {}
    for model in manifest["models"].values():
        name = model["name"]
        raw = (history/RUNS[name[:3]]/"split.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != model["data_identity"]["split_sha256"]:
            raise ValueError(f"Changed split for {name}")
        parts = json.loads(raw)["partitions"]
        if name[:3] in ("5.C","5.E") and not ids <= set(parts["test"]):
            raise ValueError(f"Sample not in {name} test split")
        overlaps[name] = sorted(ids.intersection(parts["train"] + parts["validation"]))
        models[name] = dict(model, frames=[])
    for pos,f in enumerate(frames,1):
        ref = read_labels(bundle,f["reference"],[0,1,255])
        valid = ref != 255
        for key,record in f["predictions"].items():
            pred = read_labels(bundle,record,[0,1])
            if ref.shape != pred.shape:
                raise ValueError("Unaligned masks")
            matrix = np.bincount(2*ref[valid]+pred[valid],minlength=4).reshape(2,2).tolist()
            models[manifest["models"][key]["name"]]["frames"].append(dict(position=pos,image_id=f["id"],
                recording_run=f["recording_run"],matrix=matrix,ignored=int((~valid).sum())))
    if any(len(m["frames"])!=len(ids) for m in models.values()):
        raise ValueError("Incomplete predictions")
    source = history/"series5-ce-grouped/campaign-only-v1"
    inventory = json.loads((source/"manifest.json").read_text())["records"]
    runs_by_id = {r["id"]: r["recording_run"] for r in inventory}
    test_ids = json.loads((source/"split.json").read_text())["partitions"]["test"]
    if not ids <= set(test_ids) or len(test_ids) != manifest["population"]:
        raise ValueError("Viewer sample does not match the campaign test population")
    return dict(campaign_by_drive=Counter(runs_by_id.values()),test_by_drive=Counter(runs_by_id[i] for i in test_ids),
                seed=manifest["seed"],population=manifest["population"],reference=manifest["reference_policy"],
                split=manifest["data_identity"],overlap=overlaps,checkpoints=models)


def render(data, output, bundle):
    models = data["checkpoints"]
    excluded = set().union(*data["overlap"].values())
    clean = {n:[f for f in m["frames"] if f["image_id"] not in excluded] for n,m in models.items()}
    sample = models["5.C"]["frames"]
    if not all(clean.values()):
        raise ValueError("No eligible photos")
    ranking = sorted(clean,key=lambda n:-scores(clean[n])[-1])
    styles, story = getSampleStyleSheet(), []
    def para(s,style="BodyText"):
        story.append(Paragraph(s,styles[style]))
    def table(rows,rules=None):
        t = make_table(rows)
        if rules:
            add_metric_gradients(t,rows,rules)
        story.extend([Spacer(1,9),t,Spacer(1,9)])
    def page(title,caption):
        story.append(PageBreak())
        para(title,"Heading1")
        para(caption)
    def plot(fig,w,h):
        stream=BytesIO()
        fig.savefig(stream,format="png",dpi=150,bbox_inches="tight")
        plt.close(fig)
        stream.seek(0)
        story.append(Figure(stream,width=w,height=h,kind="proportional"))
    def pct(v):
        return "N/A" if v is None else f"{100*v:.3f}%"
    def footer(canvas,doc):
        canvas.setFont("Helvetica",8)
        canvas.drawString(28,17,"SidewalkPilot  /  Offline segmentation evaluation")
        canvas.drawRightString(764,17,f"Series 5    |    {doc.page}")
    total, eligible = len(sample), len(clean["5.C"])
    para("SidewalkPilot Series 5 Model Report","Title")
    para("Which checkpoint matched the sidewalk best?","Heading2")
    para(f"Eight checkpoints predicted a sidewalk mask on the same photos. The table ranks agreement with SAM 3 reference masks on {eligible} photos. "
         f"We started with {total} from the frozen {data['population']:,}-photo C/E test set and excluded {len(excluded)} used for training or validation by at least one model.")
    table([["Rank","Checkpoint","Epoch","Precision","Recall","F1","Sidewalk IoU","Background IoU","mIoU"]]+
          [[i,n,models[n]["epoch"],*map(pct,scores(clean[n]))] for i,n in enumerate(ranking,1)],{i:"high" for i in range(3,9)})
    para("How to read the ranking","Heading2")
    para("Precision: of pixels called sidewalk, how many matched? Recall: of reference sidewalk pixels, how many were found? "
         "F1 balances the two. IoU is overlap divided by union for each class. mIoU gives the two class scores equal weight. "
         "Counts are pooled before division. Green marks a better value within each column, not a safety threshold.")
    para(f"{ranking[0]} ranked first at {pct(scores(clean[ranking[0]])[-1])} mIoU; {ranking[1]} followed at {pct(scores(clean[ranking[1]])[-1])}. "
         "A small difference on two drives does not establish a better field system. None of these scores measures sidewalk width in centimeters.")
    page("Why only two July 2 drives?",f"The 10,000 accepted images came from two recordings. The viewer samples the frozen test split, not the full camera archive. Scored: {eligible} of {total} viewer photos after checking training and validation membership. These results do not test another day's conditions.")
    runs=sorted(data["campaign_by_drive"])
    table([["Recording","In original 10,000","In 1,000 test","Drawn for viewer","Scored","Excluded"]]+[[r,data["campaign_by_drive"][r],data["test_by_drive"].get(r,0),(a:=sum(f["recording_run"]==r for f in sample)),
             (b:=sum(f["recording_run"]==r for f in clean["5.C"])),a-b] for r in runs])
    table([["Checkpoint","Training architecture","Model input (W x H)","Evaluation precision","Saved epoch"]]+
          [[n,"MobileNetV3 / LR-ASPP" if n[2] in "AB" else "ConvNeXt-Tiny / U-Net",
            " x ".join(map(str,m["input_size"])),m["precision"],m["epoch"]] for n,m in models.items()])
    para("A/B are development baselines. C trained its encoder immediately; E kept it frozen for the first two epochs. For C/E, no suffix means final epoch; b selects by validation sidewalk IoU; s favors validation precision near the best IoU. The test photos did not select those checkpoints.")
    para("Excluded photo numbers: "+(", ".join(str(f["position"]) for f in sample if f["image_id"] in excluded) or "none")+
         ". Scores compare stored class IDs at the original resolution; label 255 is unknown and never counted as background.")
    page("Where did each model add or miss sidewalk?","False positives are background mislabeled as sidewalk (spill). False negatives are sidewalk mislabeled as background (misses). The graph divides each error count by its own reference class size, so class imbalance does not hide mistakes.")
    names=list(models)
    cm=np.array([counts(clean[n]) for n in names])
    fig,ax=plt.subplots(figsize=(9,2.8))
    x=np.arange(len(names))
    ax.bar(x-.19,100*cm[:,1]/(cm[:,0]+cm[:,1]),.38,color="#c16627",label="Background called sidewalk")
    ax.bar(x+.19,100*cm[:,2]/(cm[:,2]+cm[:,3]),.38,color="#25808a",label="Sidewalk missed")
    ax.set_xticks(x,names);ax.set_ylabel("Percent of reference class");ax.legend(frameon=False)
    plot(fig,630,190)
    table([["Model","Background kept (TN)","Spill (FP)","Missed (FN)","Sidewalk found (TP)"]]+
          [[n,*[f"{v:,}" for v in row]] for n,row in zip(names,cm)])
    scored=sum(counts(clean["5.C"]))
    ignored=sum(f["ignored"] for f in clean["5.C"])
    para(f"Unit: pixels, not photos. Across {eligible} photos the masks contain {scored+ignored:,} pixels. Skip {ignored:,} unknown reference pixels. Each row then sorts the same {scored:,} pixels into four outcomes; a pixel appears exactly once per model.")
    page("Can a high average hide a bad mask?",f"Compute one mIoU per photo by averaging sidewalk and background IoU. Sort the {eligible} scores: minimum is the worst, the 10th percentile marks the low end, and the median marks the middle. Mean is the sum divided by {eligible}. Photo numbers match the viewer.")
    rows=[["Model","Worst photo #","Minimum","10th percentile","Median","Mean"]]
    for n in names:
        fs=clean[n]; vals=[scores([f])[-1] for f in fs]
        rows.append([n,fs[int(np.argmin(vals))]["position"],*map(pct,[min(vals),np.percentile(vals,10),np.median(vals),mean(vals)])])
    table(rows,{i:"high" for i in range(2,len(rows[0]))})
    para("Why report more than the average?","Heading2")
    para("A model can agree on most pixels in most photos while missing an entire stretch of path in one. "
         "The worst photo is a diagnostic case, not an estimate of how often that failure occurs on another route.")
    page("What does a missed sidewalk look like?","The example is selected by a reproducible rule: the scored photo with the largest mIoU drop from 5.C to 5.Cs. This illustrates the cost of favoring precision; it is not a random example.")
    a,b=clean["5.C"],clean["5.Cs"]
    k=max(range(len(a)),key=lambda i:scores([a[i]])[-1]-scores([b[i]])[-1])
    pos=a[k]["position"]
    manifest=json.loads((bundle/"manifest.json").read_text()); f=manifest["frames"][pos-1]
    photo=np.asarray(Image.open(bundle/f["image"]).convert("RGB"))
    ref=read_labels(bundle,f["reference"],[0,1,255])
    fig,axes=plt.subplots(2,2,figsize=(9,4.9))
    for ax,tag in zip(axes.flat,["Original","Reference","c","cs"]):
        img=photo.copy()
        if tag=="Reference":
            img[ref==1]=(.55*img[ref==1]+.45*np.array([30,205,125])).astype(np.uint8)
        elif tag in ("c","cs"):
            pred=read_labels(bundle,f["predictions"][tag],[0,1])
            for mask,color in [((ref==1)&(pred==0),[0,170,235]),((ref==0)&(pred==1),[255,136,0])]:
                img[mask]=color
        ax.imshow(img);ax.set_axis_off();ax.set_title(tag if tag in ("Original","Reference") else "5."+tag.capitalize()+" errors")
    fig.tight_layout(pad=.5);plot(fig,630,345)
    para(f"Photo {pos}: 5.C {pct(scores([a[k]])[-1])} vs 5.Cs {pct(scores([b[k]])[-1])} mIoU. Green: reference sidewalk. Blue: missed sidewalk. Orange: spill. Unknown pixels are not marked as errors.")
    SimpleDocTemplate(str(output),pagesize=landscape(letter),leftMargin=28,rightMargin=28,topMargin=27,bottomMargin=35,
                      title="SidewalkPilot Series 5 Model Report").build(story,onFirstPage=footer,onLaterPages=footer)


def write_report(root, history, out):
    result = evaluate(root, history)
    out.mkdir(parents=True, exist_ok=True)
    render(result, out/"series_5_model_report.pdf", root)
    (out/"series_5_evaluation.json").write_text(json.dumps(result, indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history",type=Path,default=Path.home()/"sidewalkpilot-labels")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--bundle",type=Path,help="Score an existing offline model-lab package")
    mode.add_argument("--infer",action="store_true",help="Run the eight checkpoints on the original 50 photos before scoring")
    p.add_argument("--out",type=Path,default=Path(__file__).resolve().parents[3]/"docs")
    args=p.parse_args()
    root=(args.bundle or args.history/"model-lab-test50").resolve()
    if args.infer:
        import torch
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"ai_models_datasets/series_5/tools/review"))
        from package_model_lab import package
        names = ("5.A","5.B","5.C","5.Cb","5.Cs","5.E","5.Eb","5.Es")
        checkpoints = [(n,args.history/RUNS[n[:3]]/("best.pt" if n in ("5.A","5.B") else n+".pt")) for n in names]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"predictions"
            package(args.history/"series5-ce-grouped/campaign-only-v1", root, checkpoints,
                    20261123,50,torch.device("cuda"))
            write_report(root,args.history,args.out)
    else:
        write_report(root,args.history,args.out)
