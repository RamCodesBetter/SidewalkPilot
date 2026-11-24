# Series 5 Workspace

Keep work on `series-5`. Historical A/B artifacts retain their original recipes.

## Single-sidewalk labeling campaign

For the full D/F inventory, run `tools/labeling/screen_full_inventory.py HISTORY OUTPUT`
on the GPU workstation. It verifies the original strict policy and mask hashes,
reuses both passed and deferred decisions, and screens the remaining distinct
photos. Re-run with the same paths to resume. See `progress.json` for counters
and `sources.json` for both directories of per-frame loop receipts. Deferred is
not background: it means the frame needs correction or adjudication. Screening
completion is not training readiness.

5.D is the full-inventory no-freeze experiment; 5.F is the matched two-epoch
encoder-freeze experiment. Before training, resolve the deferred labels and
freeze one grouped 80/10/10 split that protects the existing C/E partitions.
Do not automatically assign all screened frames to training. The same 50-image
viewer accepts D/F checkpoints with `--df-split`, checks split identities, and
does not show predictions for a checkpoint that has not been trained.

`tools/labeling/run_single_corridor_campaign.py` screens unique training-eligible frames in
128-image loops. A pass requires two matching confident, near-camera sidewalk proposals
and a final target with one connected sidewalk region; temporal drafts never count.
Passed masks are automatic, not verified semantic references. Training and the final
holdout are not touched. Each completed loop is committed before the next starts.
The output includes `STATUS.txt` (one line per loop) and `progress.json` (latest counts).
Re-run with the same inputs/output to resume; policy or source-identity mismatches stop it.
With `--mac`, the status files mirror to `reviews/single-sidewalk/pass-10000/` on the Mac.
Only at 10,000 passes is a 30-image variety review built there under `review30/`.
If the eligible pool runs out first, the status reports the shortfall without relaxing gates.

## Checkpoint Names

The C/E campaign-only pair uses `tools/datasets/campaign10k.py` and the
original 10,000 candidate JPEG/PNG pairs only. The superseded 12,809-image
proposal is not used. The common split is exactly 8,000/1,000/1,000;
adjacent frames (same run, <=0.5 s) and perceptual matches (64-bit DCT hash
distance <=4) stay together transitively. The 30 inspected frames stay in
training. Every training ID occurs once per epoch. Both runs use the same
FP32 initialization, weighted focal objective and sampler seed. C updates
the encoder immediately; E keeps it frozen and in eval mode for the first
two epochs, then trains it with the decoder. Metrics on this cohort measure
agreement with SAM 3 pseudo-labels, not independently measured mask accuracy.
Neither trainer evaluates the test partition during training.

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

## Tools You Actually Run

| Workflow | Entry point |
| --- | --- |
| Full D/F label screening and resume | `tools/labeling/screen_full_inventory.py` |
| Live aggregate progress (five-second refresh) | `tools/packaging/serve_df_history.py` |
| Train A/B/C/E | The corresponding `series_5_*_sidewalkpilot_trainer.py` in this directory |
| Build the unified model comparison | `tools/packaging/package_model_lab.py` |
| Open the offline model viewer on the Mac | `reviews/model-lab-test50/index.html` |

The model viewer compares checkpoint predictions on the same 50 photos. The
progress dashboard reads loop receipts, not photos. Neither is a label editor.
Mask-repair, pretraining dataset preparation, and corridor-sample packaging
are separate workflows; some still share code with the strict SAM 3 worker.

Keep `tools/workspace.py`: the entry points use it to find configs and import
helpers by filename when started from any directory. `models` defines the
network, loss and checkpoint rules; `filtering` decides which candidate masks
to accept; `datasets` prepares targets and partitions. These modules are not
extra copies of the viewer. The Linux training history is in
`~/sidewalkpilot-labels`. The Mac's local `docs` folder is PDF-only and its
notebook remains separate at `~/Desktop/notebook`.

Retired standalone viewers, migration commands, and one-off prompt sweeps
are available in Git history at `e0fac98`. Do not rewrite old receipts or
recreate obsolete folders in order to open the current viewer.
