label-sample/ is a local example, not another training dataset or test set.
It contains ten original RGB photos, ten matching class-ID PNGs, and manifest.json.

A manifest is a contents list, like a shipping manifest. The filename is a
convention, not a Python command. In this sample, frames is a list of records.
For each frame:
  name: original photo filename; recording_run: the drive it came from.
  id and source_sha256: here both are the SHA-256 digest of the photo bytes.
  image: relative path to the RGB photo. size: [width, height].
  supervision: pseudo-binary (automatically labeled, not a human reference).
  prediction.path: relative path to the original SAM 3 pipeline mask PNG.
  prediction.sha256: digest of the PNG bytes, separate from the photo digest.
  prediction.positive_pixels and ignored_pixels: counts of IDs 1 and 255.
  prediction.rle: the same mask as [value, count] pairs, flattened across
  each row from left to right, top to bottom. Counts sum to width * height.
  screening: which prompt pair agreed, its two scores and prompt IoU.

Prediction here means the SAM label used as a target, not a 5.C output.
These are sample/viewer records; production trainer manifests have their own
schema. Renaming a key in one format doesn't change how another loader works.

Example (run from the series_5 directory with Pillow installed):

    from pathlib import Path
    import json
    from PIL import Image
    root = Path("label-sample")
    manifest = json.loads((root / "manifest.json").read_text())
    row = manifest["frames"][0]
    with Image.open(root / row["prediction"]["path"]) as mask:
        print(row["image"], mask.getpixel((0, 0)), row["prediction"]["rle"][:4])

The photo becomes the input tensor. The mask is the training target: one
integer per pixel (0 = background, 1 = sidewalk, 255 = ignore). These are
automatically screened SAM 3 labels, not independently verified ground truth.
A PNG may look nearly black in Preview because 1 is nearly black at display
scale 0-255; its stored class ID is still sidewalk. No recoloring is applied.

How a mask passes the strict screen
1. SAM 3 proposes regions for "concrete sidewalk" and "sidewalk". If the
   second prompt has no confident anchored instance, the worker tries "paved
   pedestrian walkway" instead. The score gates are 0.65 and 0.55.
2. Each proposal needs a connected corridor near the car: the anchor window
   is the bottom 10% of rows and the middle 30% of columns. The candidate
   must cover more than 0.3% of the whole image inside that window. A separate
   sidewalk or a concrete lid shouldn't win just because it's the largest.
3. After tiny specks are removed, intersection / union of the two proposals
   must be at least 0.90. The shared interior becomes 1, confident exterior
   becomes 0, and disagreement and the narrow boundary band become 255.
   Small enclosed negative regions are ignored, not painted as sidewalk.
4. The final foreground must form one connected, anchored region occupying
   15-94% of the photo, with at least 3% background. If checks fail, the
   worker records the reason and defers the frame rather than inventing a mask.

Example: frame 01's two scores are 0.9023 and 0.6953, with prompt IoU 0.9974.
That is agreement between two prompts on the same model, not 99.74% accuracy
against a human. Both prompts can still include the same wrong driveway edge.
