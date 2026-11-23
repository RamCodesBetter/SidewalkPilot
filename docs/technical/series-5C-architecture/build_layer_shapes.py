"""Build and inspect the two-page matrix-shape companion."""
import math
from pathlib import Path

import pymupdf
import typst

ROOT = Path(__file__).resolve().parent
STEM = "sidewalkpilot-layer-shapes"


def main():
    x = [[0.2, 0.8], [1, 0]]
    w = [[1.5, -0.5], [-1, 1]]
    bias = [0.3, -0.1]
    z = [[sum(a * b for a, b in zip(row, weights)) + bias[j]
          for j, weights in enumerate(w)] for row in x]
    expected = [[0.2, 0.5], [1.8, -1.1]]
    for actual_row, expected_row in zip(z, expected):
        assert all(math.isclose(a, b) for a, b in zip(actual_row, expected_row))
    gelu = [[v * (1 + math.erf(v / math.sqrt(2))) / 2 for v in row] for row in z]
    src = (ROOT / f"{STEM}.typ").read_text()
    for row in gelu:
        for value in row:
            assert f"{value:.4f}" in src
    typst.compile(str(ROOT / f"{STEM}.typ"), output=str(ROOT / f"{STEM}.pdf"), root=str(ROOT))
    previews = ROOT / "preview"
    previews.mkdir(exist_ok=True)
    with pymupdf.open(ROOT / f"{STEM}.pdf") as pdf:
        assert len(pdf) == 2, f"Expected 2 pages, got {len(pdf)}"
        fonts = set()
        for number, (page, title) in enumerate(zip(pdf, ("One neuron, one layer", "Trace a small example")), 1):
            assert title in page.get_text(), f"Heading on wrong page: {title}"
            fonts.update(font[3] for font in page.get_fonts())
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        rect = pymupdf.Rect(span["bbox"])
                        assert rect.x0 >= 0 and rect.y0 >= 0
                        assert rect.x1 <= page.rect.width + 1 and rect.y1 <= page.rect.height + 1
            page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(previews / f"layer-shapes-page-{number}.png")
        assert any("NewCMMath" in name for name in fonts), fonts
    print("Verified two pages, numerical examples, bounds, and New Computer Modern math.")
    print(ROOT / f"{STEM}.pdf")


if __name__ == "__main__":
    main()
