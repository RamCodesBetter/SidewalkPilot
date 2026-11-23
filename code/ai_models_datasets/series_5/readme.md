# Series 5 Workspace

Keep work on `series-5`. Historical A/B artifacts retain their original recipes.

## Checkpoint Names

Completed non-smoke C runs publish these names inside their run directory:

| Name | Meaning |
| --- | --- |
| `5.C.pt` | End state: last completed epoch, including normal early stopping |
| `5.Cb.pt` | Best validation sidewalk IoU only; earliest epoch wins ties |
| `5.Cs.pt` | Highest sidewalk precision among epochs within 1 percentage point of best validation sidewalk IoU (inclusive); ties: higher IoU, then earlier epoch |

The same convention applies to future base names: `5.0`, `5.0b`, `5.0s`.
The smart rule uses pooled reviewed binary validation pixels only. An undefined
precision cannot win. No eligible defined precision means no smart file.
Validation boundary F1 is reported separately, never used to rank epochs:
match inner sidewalk edge pixels (4-neighbor sidewalk/background transitions)
within Euclidean distance 2 at original reference resolution, pooling directed
match counts over images. Unknown pixels and the image frame are not background.
Two empty boundary sets score null; a one-sided empty set scores zero.
Working snapshots of potentially eligible epochs live in `smart-candidates/`;
as the best IoU improves, the final cutoff may exclude an earlier candidate.
`best.pt` and `last.pt` remain compatible working/resume checkpoints. Named files
are snapshots, not symlinks that follow later replacements. The trainer writes
`checkpoint-selection.json` with each selected epoch and criterion. Smoke and
interrupted runs do not publish completed-model names. No historical A/B
artifacts are renamed, and this change does not alter training or early stopping.

The current trainer updates encoder and decoder together from the first batch.
Planned staged warmup would update only the decoder first, then both; the decoder
would continue without a reset. That schedule is not implemented by naming files.

The old A development dataset contains 247 training, 118 validation, and 33 test
images. All 33 appear in the A/B comparison viewer; this does not establish that
the user inspected every image or that every mask is a complete binary reference.
They are not the final 10% of the full corpus. Preserve development provenance
while preparing the planned grouped 80/10/10 split and unexposed final holdout.

## 5.C Loss and Plan Audit (November 22, 2026)

5.C now defaults to **class-weighted focal loss**, restoring Decision 9 of the
saved Series 5 plan. `train --loss focal-dice --dice-weight 0.5` enables the
separate comparison. Dice is a per-image, two-class soft overlap loss on reviewed
binary references only; unknown (`255`) pixels and weak masks do not enter Dice.
Both modes preserve separate strong/weak means and the weak coefficient 0.5.

The newly explicit starting defaults are gamma 1.5, background/sidewalk weights
2/1, a class-weight cap of 4, and optional Dice weight 0.5. The historical plan
specified the loss families, not these exact S5 coefficients. Set `--focal-gamma
0 --loss focal` for a weighted-CE ablation. Gamma, effective class weights, Dice
settings, and loss source hash enter the run contract; a changed objective cannot
resume an old run. Use distinct output directories for each comparison.

Local history and approved W&B runs include `loss_strong_focal`, `loss_weak_focal`,
`loss_strong_soft_dice`, and `loss_weighted_dice`, plus live `batch/loss_*` values.
`binary_loss` includes weighted Dice when enabled; `partial_loss` is weak focal.
Dice metrics are zero when the term is disabled. This change starts no full run,
uploads nothing, and does not modify A/B losses or trained artifacts.

See the full decision-by-decision audit in
[`training-plan-audit.txt`](../../../docs/technical/series-5C-architecture/training-plan-audit.txt).
The current development split, staged encoder warmup, sequence-aware sampling,
final holdout, safety-aware checkpoint score, and Jetson/planner qualification
remain outstanding. FP32-only, ConvNeXt-Tiny/U-Net, and binary beta naming remain
the newer choices; do not revert them to historical settings.

| Folder | Contents |
| --- | --- |
| `series_5_*_sidewalkpilot_trainer.py` | A/B/C training entry points, directly in this folder |
| `tools/labeling/` | SAM inference, labeling campaigns, and mask repair |
| `tools/datasets/` | Dataset and review selection, splits, training targets |
| `tools/evaluation/` | Audits, diagnostics, comparisons, and scoring |
| `tools/packaging/` | Portable review bundles and comparison viewers |
| `tools/models/` | Model architecture and export code |
| `tools/filtering/` | Mask filtering policies |
| `tools/configs/` | Model/labeling configs and class taxonomy |
| `tools/review/` | Viewer HTML/CSS/JavaScript and terminal review launcher |
| `reviews/` | Complete local review bundles, including their images, masks and exports |
| `docs/` | Local architecture PDF, LaTeX/Typst source and related documents |

Generated artifacts are ignored by Git. On the Mac, the workspace is
`~/Desktop/rc_car_code/code/ai_models_datasets/series_5/`.
The Linux history store stays at `~/sidewalkpilot-labels`; checkpoint paths there
have not moved. Published model exports stay in `code/ai_models/`.
The recovered Mac journal is `~/Desktop/notebook/`, outside this workspace.

## Open on the Mac

- 5.A versus 5.B: `reviews/5.a-vs-5.b/index.html`
- 5.A test viewer: `reviews/5.a-test/index.html`
- Paired mask review: `reviews/paired-review/index.html`
- Thirty-image comparison: `reviews/random-30-comparison/index.html`
- Architecture PDF: `docs/5.c-architecture/sidewalkpilot-5C-math-and-cs.pdf`
- Older root-level class-1 data: `reviews/legacy-class1/`

Each complete viewer bundle keeps its internal paths and filenames unchanged.
Do not discard downloaded review/correction JSON files: browser-only drafts may
need to be reimported after a viewer's file URL changes. Moving files does not
clear or approve any review decisions.

## Current Entry Points

Run from the repository root; add the existing dataset, split and output arguments.

```sh
python code/ai_models_datasets/series_5/series_5_c_sidewalkpilot_trainer.py --help
python code/ai_models_datasets/series_5/tools/labeling/label_series5_campaign.py --help
python code/ai_models_datasets/series_5/tools/packaging/package_beta_comparison.py --help
```

All three trainers live directly in `series_5/`. Architecture, configs, frozen
label-policy files, viewer templates and historical diagnostics stay in `tools/`.
The entry points resolve those paths without changing the working directory.
`tools/workspace.py` centralizes source lookup and direct-script import paths.
Archived run contracts and code hashes remain historical records. Do not rewrite
them to bypass a resume check after this source-layout change.

## Migrate an Existing Flat Workspace

After updating the checkout, run from the repository root:

```sh
python3 code/ai_models_datasets/series_5/tools/organize_workspace.py
python3 code/ai_models_datasets/series_5/tools/organize_workspace.py --apply
```

The first command is a dry run. The second moves only the recognized generated
bundles, refuses destination collisions, hashes files before/after, and records
the moves in local `workspace-migration.json`. It neither deletes files nor
rewrites historical manifests, masks, checkpoint contracts, or review decisions.
It is safe to rerun after a successful migration.
