"""Compile the source-checked guide and render page thumbnails for inspection."""
import hashlib
import json
from pathlib import Path
import re

import pymupdf
import typst

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
STEM = "sidewalkpilot-5C-math-and-cs"
PDF = ROOT / (STEM + "-typst.pdf")


def main():
    facts = json.loads((ROOT / "implementation-facts.json").read_text())
    for item in facts["sources"]:
        current = hashlib.sha256((REPO / item["path"]).read_bytes()).hexdigest()
        if current != item["sha256"]:
            raise SystemExit(f"Implementation changed; refresh capture_facts.py first: {item['path']}")
    typst.compile(str(ROOT / (STEM + ".typ")), output=str(PDF), root=str(ROOT))
    previews = ROOT / "preview"
    previews.mkdir(exist_ok=True)
    report = []
    with pymupdf.open(PDF) as pdf:
        headings = ["SidewalkPilot 5.C"] + re.findall(
            r'^#next\("([^"]+)"', (ROOT / (STEM + ".typ")).read_text(), re.MULTILINE)
        if len(pdf) != len(headings):
            raise RuntimeError(f"Unexpected page overflow: {len(pdf)} pages for {len(headings)} sections")
        for number, page in enumerate(pdf, 1):
            page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(previews / f"page-{number:02d}.png")
            text = page.get_text()
            if headings[number - 1] not in text:
                raise RuntimeError(f"Section starts on the wrong page: {headings[number - 1]}")
            if len(text.strip()) < 120:
                raise RuntimeError(f"Unexpected nearly blank page {number}")
            out_of_bounds = []
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        box = pymupdf.Rect(span["bbox"])
                        if box.x0 < 0 or box.y0 < 0 or box.x1 > page.rect.width + 1 or box.y1 > page.rect.height + 1:
                            out_of_bounds.append(span["text"])
            if out_of_bounds:
                raise RuntimeError(f"Text outside page {number}: {out_of_bounds}")
            report.append(dict(page=number, text_characters=len(text)))
        (ROOT / (STEM + ".txt")).write_text("\n\n".join(page.get_text() for page in pdf))
        # Group small rendered pages into preview sheets for a visual layout audit.
        for start in range(0, len(pdf), 6):
            with pymupdf.open() as sheet:
                canvas = sheet.new_page(width=3 * 306, height=2 * 396)
                for offset, source in enumerate(range(start, min(start + 6, len(pdf)))):
                    left, top = (offset % 3) * 306, (offset // 3) * 396
                    canvas.show_pdf_page(pymupdf.Rect(left, top, left + 306, top + 396), pdf, source)
                canvas.get_pixmap().save(previews / f"overview-{start // 6 + 1}.png")
    (ROOT / "build-report.json").write_text(json.dumps(dict(pages=report, typst=str(typst.__version__)), indent=2) + "\n")
    print(f"Compiled and checked {len(report)} pages: {PDF}")


if __name__ == "__main__":
    main()
