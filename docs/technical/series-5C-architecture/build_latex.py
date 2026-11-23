"""Build the LaTeX edition, check its source snapshot, fonts, and pagination."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata

import pymupdf

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
STEM = "sidewalkpilot-5C-math-and-cs"


def main():
    facts = json.loads((ROOT / "implementation-facts.json").read_text())
    for item in facts["sources"]:
        current = hashlib.sha256((REPO / item["path"]).read_bytes()).hexdigest()
        if current != item["sha256"]:
            raise SystemExit(f"Implementation changed; refresh the guide and its audit: {item['path']}")
    tex = (ROOT / (STEM + ".tex")).read_text()
    audit_hash = hashlib.sha256((ROOT / "verify_teaching_examples.py").read_bytes()).hexdigest()
    if facts.get("teaching_audit_sha256") != audit_hash:
        raise RuntimeError("Teaching examples changed; run capture_facts.py again")
    for literal in facts["teaching"]["documented_values"]:
        if literal not in tex:
            raise RuntimeError(f"Checked numerical example missing from guide: {literal}")
    diagram_count = tex.count(r"\begin{tikzpicture}")
    if diagram_count < 9:
        raise RuntimeError("Expected the original explanatory diagrams")
    for value in facts["parameters"].values():
        if f"{value:,}" not in tex:
            raise RuntimeError(f"Parameter count absent from LaTeX: {value}")
    for key in ("torch", "torchvision"):
        if facts[key] not in tex:
            raise RuntimeError(f"Environment snapshot differs: {key}")
    compiler = shutil.which("tectonic") or str(Path.home() / ".local/opt/tectonic-0.17.0/tectonic")
    subprocess.run([compiler, "--only-cached", "--untrusted", "--keep-logs", STEM + ".tex"],
                   cwd=ROOT, check=True)
    log = (ROOT / (STEM + ".log")).read_text(errors="replace")
    if "Overfull \\" in log or "Missing character:" in log:
        raise RuntimeError("LaTeX reports overflow or missing glyphs; inspect the log")
    headings = ["SidewalkPilot 5.C"] + re.findall(r"^\\guidepage\{([^}]+)\}", tex, re.MULTILINE)
    previews = ROOT / "preview-latex"
    previews.mkdir(exist_ok=True)
    report, fonts = [], set()
    with pymupdf.open(ROOT / (STEM + ".pdf")) as pdf:
        if len(pdf) != len(headings):
            raise RuntimeError(f"Page overflow: {len(pdf)} pages for {len(headings)} sections")
        if [row[2] for row in pdf.get_toc()] != list(range(1, len(headings) + 1)):
            raise RuntimeError("Expected a navigation bookmark for every teaching page")
        for required in ("mu and sigma", "standard deviation", "0.0740646"):
            if required not in pdf[1].get_text():
                raise RuntimeError(f"Normalization explanation missing on page 2: {required}")
        for number, page in enumerate(pdf, 1):
            text = unicodedata.normalize("NFKC", page.get_text()).replace("\u2019", "'")
            if headings[number - 1] not in text:
                raise RuntimeError(f"Section starts on wrong page: {headings[number - 1]}")
            if len(text.strip()) < 120:
                raise RuntimeError(f"Nearly blank page {number}")
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        box = pymupdf.Rect(span["bbox"])
                        if box.x0 < 0 or box.y0 < 0 or box.x1 > page.rect.width + 1 or box.y1 > page.rect.height + 1:
                            raise RuntimeError(f"Text outside page {number}: {span['text']}")
            fonts.update(f[3].split("+")[-1] for f in page.get_fonts())
            page.get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25)).save(previews / f"page-{number:02d}.png")
            report.append(dict(page=number, text_characters=len(text)))
        for start in range(0, len(pdf), 6):
            with pymupdf.open() as sheet:
                canvas = sheet.new_page(width=918, height=792)
                for offset, source in enumerate(range(start, min(start + 6, len(pdf)))):
                    left, top = (offset % 3) * 306, (offset // 3) * 396
                    canvas.show_pdf_page(pymupdf.Rect(left, top, left + 306, top + 396), pdf, source)
                canvas.get_pixmap().save(previews / f"overview-{start // 6 + 1}.png")
    for family in ("CMR", "CMMI", "CMSY", "CMEX"):
        if not any(name.upper().startswith(family) for name in fonts):
            raise RuntimeError(f"Missing expected Computer Modern font family: {family}; got {fonts}")
    if any("DEJAVU" in name.upper() for name in fonts):
        raise RuntimeError("Old DejaVu font unexpectedly present")
    (ROOT / "latex-build-report.json").write_text(json.dumps(
        dict(pages=report, fonts=sorted(fonts), diagrams=diagram_count,
             tex_sha256=hashlib.sha256(tex.encode()).hexdigest()), indent=2) + "\n")
    print(f"Verified {len(report)} LaTeX pages with Computer Modern: {ROOT / (STEM + '.pdf')}")


if __name__ == "__main__":
    main()
