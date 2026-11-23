SidewalkPilot 5.C architecture guide

Short matrix-shape companion:
  Read sidewalkpilot-layer-shapes.pdf; edit sidewalkpilot-layer-shapes.typ.
  Rebuild/check: python build_layer_shapes.py (requires typst and pymupdf).
  Covers neurons vs layers, batching, bias broadcasting, GELU shapes,
  a numerical example, and the 5.C 1x1 head. Uses New Computer Modern math.

Read: sidewalkpilot-5C-math-and-cs.pdf
Edit: sidewalkpilot-5C-math-and-cs.tex

Campaign edition: sections 14-15 use the actual 8,000/1,000/1,000 split.
Section 21b explains the six batch loss curves and the C/E freeze schedule.
Section 23a traces a photo to logits to the viewer's run-length encoding.
The dated plan audit below is historical, not the active run configuration.

November 22 loss restoration and plan audit:
  Sections 17/17a now document focal and the optional reviewed-only Dice term.
  The CE teaching examples remain explicitly labeled gamma=0 simplifications.
  Read training-plan-audit.txt for all 20 saved decisions versus current code.
  planning-register-snapshot.txt preserves the source register unchanged.
  These files do not change submitted forms or imply full training/deployment.

Checkpoint naming update (section 23):
  5.C.pt = completed end state; 5.Cb.pt = best validation sidewalk IoU.
  5.Cs.pt = highest precision within one percentage point of best validation
  sidewalk IoU; ties favor higher IoU, then earlier epoch. Boundary F1 at
  two reference pixels is reported separately, not used for selection.
  Interrupted runs retain last.pt for resume; smoke runs are not promoted.
  No historical A/B files, training schedules, or splits were changed.

The current PDF is compiled with real LaTeX and classic Computer Modern
text/math fonts. The .tex source is standalone: no screenshots of equations,
external equation images, generated math font substitutions, or project
source files are needed to typeset it.

Compile with Tectonic:
  tectonic sidewalkpilot-5C-math-and-cs.tex

It can also be compiled with a standard LaTeX installation or Overleaf.

The original .typ file is retained as the earlier Typst edition. Future
content revisions target .tex; the two formats are not automatically synced.
implementation-facts.json is the current code and numerical audit, not an
archived Typst-only artifact.

The expanded teaching edition begins on PDF page 2 with mu and sigma.
It includes original TikZ weight/bias, convolution, normalization,
encoder/decoder, and gradient diagrams, plus worked numerical examples.
The small teaching networks are distinct from the real 5.C architecture.

Workstation-only verification, from this directory in the repository:
  /home/rsabavat/.gpu-env/bin/python capture_facts.py
  /home/rsabavat/.venvs/sidewalkpilot-docs/bin/python build_latex.py

capture_facts.py checks actual model shapes and numerical examples without
training the research model. build_latex.py checks the repository snapshot,
typesets from cached TeX resources, and verifies fonts and page layout.
The first Tectonic build must fetch its required TeX resources.

build.py is the original Typst builder. It now writes a separate
sidewalkpilot-5C-math-and-cs-typst.pdf so it cannot overwrite the LaTeX PDF.
