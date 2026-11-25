"""Render the offline segmentation report from saved pixel counts and split identities."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def counts(frames):
    return tuple(sum(f["matrix"][i][j] for f in frames) for i, j in [(0, 0), (0, 1), (1, 0), (1, 1)])


def scores(frames):
    tn, fp, fn, tp = counts(frames)
    def ratio(x, y):
        return x / y if y else None
    sw, bg = ratio(tp, tp+fp+fn), ratio(tn, tn+fp+fn)
    defined = [v for v in (sw, bg) if v is not None]
    return (ratio(tp,tp+fp), ratio(tp,tp+fn), ratio(2*tp,2*tp+fp+fn), sw, bg, mean(defined) if defined else None)


def render(data, history, output):
    models = data["checkpoints"]
    excluded = set()
    ids = [f["image_id"] for f in models["5.A"]["frames"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate sample")
    for name, model in models.items():
        family = name[:3]
        folder = {"5.A":"series5-5.A-training/5.A-run-001", "5.B":"series5-5.B/5.B-run-001",
                  "5.C":"series5-ce-grouped/5.C-campaign-run-001", "5.E":"series5-ce-grouped/5.E-campaign-run-001"}[family]
        raw = (history / folder / "split.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != model["data_identity"]["split_sha256"]:
            raise ValueError("Split identity mismatch: " + name)
        if [f["image_id"] for f in model["frames"]] != ids:
            raise ValueError("Mismatched sample order")
        partitions = json.loads(raw)["partitions"]
        excluded.update(set(ids).intersection(partitions["train"] + partitions["validation"]))
    doc = SimpleDocTemplate(str(output), pagesize=landscape(letter), topMargin=38, bottomMargin=38)
    story = []
    styles = getSampleStyleSheet()
    def para(s, style="BodyText"):
        story.append(Paragraph(s, styles[style]))
    def table(rows):
        story.extend([Spacer(1,10), Table(rows, repeatRows=1, style=TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#244b4a")), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#eef4f4")]),
            ("ALIGN",(1,1),(-1,-1),"RIGHT"), ("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6)])), Spacer(1,10)])
    def pct(x):
        return "N/A" if x is None else f"{100*x:.3f}%"
    clean = {n:[f for f in m["frames"] if f["image_id"] not in excluded] for n,m in models.items()}
    para("SidewalkPilot Segmentation Model Report", "Title")
    para("Shared challenge set and evaluation sources", "Heading2")
    para(f"Sample: {len(ids)} frames from the frozen 1,000-image C/E test set (seed {data['sampling_seed']}). "
         f"Primary comparison: {len(ids)-len(excluded)} frames after removing exact training or validation matches across all checkpoints. "
         "This check does not establish independence from neighboring frames on the same drive.")
    runs = Counter(f["recording_run"] for f in models["5.A"]["frames"])
    kept = Counter(f["recording_run"] for f in clean["5.A"])
    table([["Recording run","Viewer frames","Common comparison"]] + [[r,n,kept[r]] for r,n in sorted(runs.items())])
    para("Architecture and reference contract", "Heading2")
    para("A/B: LR-ASPP with MobileNetV3-Large, 640 x 360. C/E: FP32 ConvNeXt-Tiny and U-Net-style decoder, "
         "960 x 540. C trains the encoder immediately; E freezes it for two epochs. For C/E, no suffix is the final epoch, "
         "b selects the best validation sidewalk IoU, and s favors precision near that best IoU.")
    para("The reference is the original SAM 3 pseudo-mask, not a human survey. Ignore class 255. "
         "Native-size logits are converted to class IDs by argmax. High agreement does not measure physical width error or driving safety.")
    for label,groups in [("Common comparison: training and validation matches excluded",clean),
                         ("Historical viewer sample: includes 5.B training matches",{n:m["frames"] for n,m in models.items()})]:
        story.append(PageBreak())
        para(label,"Heading1")
        para("Pool all known pixels before calculating each metric. Precision measures false-positive spill; recall measures "
             "missed sidewalk. F1 balances the two; mIoU averages sidewalk and background IoU.")
        table([["Model","Epoch","Frames","Precision","Recall","F1","IoU SW","IoU BG","mIoU"]] +
              [[n,models[n]["epoch"],len(fs),*map(pct,scores(fs))] for n,fs in sorted(groups.items(),key=lambda item:-scores(item[1])[-1])])
        para("Excluded viewer positions in the common comparison (1-based): " + ", ".join(str(i) for i,k in enumerate(ids,1) if k in excluded))
    story.append(PageBreak())
    para("Pixel confusion and worst-frame behavior","Heading1")
    para("Common comparison only. Reference rows, prediction columns: TN is background kept, FP is spill, FN is missed sidewalk, "
         "TP is sidewalk recovered. Mean frame mIoU weights each photo equally; pooled mIoU weights pixels.")
    rows = [["Model","TN","FP","FN","TP","Ignored","Mean frame","Worst frame","Viewer #"]]
    for n,fs in clean.items():
        vals = [(scores([f])[-1],ids.index(f["image_id"])+1) for f in fs]
        worst,idx=min(vals)
        rows.append([n,*[f"{v:,}" for v in counts(fs)],f"{sum(f['ignored'] for f in fs):,}",
                     pct(mean(v for v,_ in vals)),pct(worst),idx])
    table(rows)
    para("Use the viewer position to examine a failure against the original photograph. These are descriptive results, "
         "not a basis for retuning against the test partition.")
    doc.build(story)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("metrics", "history", "pdf"):
        p.add_argument(arg, type=Path)
    a = p.parse_args()
    render(json.loads(a.metrics.read_text()), a.history, a.pdf)
