label-sample/ is a local example, not another training dataset or test set.
It contains ten original RGB photos, ten matching class-ID PNGs, and manifest.json.

A manifest is an inventory. It is not a special Python object, an image, or
a set of model weights. The code and the file agree on what its fields mean.
For each record, "image" and "mask" are paths relative to the manifest folder.
The SHA-256 digests identify the exact file bytes. "size" is [width, height].

Example (run from this code/ai directory with Pillow installed):

    from pathlib import Path
    import json
    from PIL import Image
    root = Path("label-sample")
    manifest = json.loads((root / "manifest.json").read_text())
    row = manifest["records"][0]
    with Image.open(root / row["mask"]) as mask:
        print(row["image"], row["mask"], mask.getpixel((0, 0)))

The photo becomes the input tensor. The mask is the training target: one
integer per pixel (0 = background, 1 = sidewalk, 255 = ignore). These are
automatically screened SAM 3 labels, not independently verified ground truth.
A PNG may look nearly black in Preview because 1 is nearly black at display
scale 0-255; its stored class ID is still sidewalk. No recoloring is applied.
