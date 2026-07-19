# Reports

SidewalkPilot keeps generated reports in the repository so a reader can inspect the exact
evidence associated with a commit rather than relying on a manually copied metric.

## Current Artifacts

| Artifact | File | Source | Scope |
|---|---|---|---|
| Steering Model Report | `docs/steering_model_report.pdf` | `code/test_files/models/evaluate_sidewalkpilot_models.py` | 52 checkpoints from v1.0 through v4.1c on one 6,952-frame shared challenge set, plus a separate 2,224-image historical Series 1/2 table |
| Machine-readable steering results | `docs/steering_eval_current_labels.json` | same evaluator | complete metrics, source breakdowns, confusion matrices, checkpoint metadata, and historical Series 1/2 blocks |
| CNN Parameter Visual Guide | `docs/cnn_parameter_visual_guide.pdf` | hand-authored visual guide | layer and parameter-count explanation for the major architecture families |

The steering PDF is 23 pages in the current build. Its first page identifies the frozen
challenge-set size and architecture-specific preprocessing. The JSON is the source of the
published values; the PDF is a rendering of those values.

## Comparison Contract

Every top-level model row uses the same 6,952 sequence-valid validation anchors drawn from
the 81,237-frame Series 3/4 dataset. Series 1/2 receive those images at 200x66 with their
required preprocessing. Series 3/4 receive 320x180 inputs and use the decoder that matches
their output contract.

The old 2,224-image Series 1/2 correction-set results remain under `historical_evaluation`.
They are useful for reconstructing the early project, but they are not mixed into the
current cross-generation ranking.

The class-balanced ranking uses Bal9, turn exact, turn +/-1, ST exact, MAE, median absolute
error, and signed error. MAE is supporting evidence rather than the sole selection rule.
The current offline leader by Bal9 is v4.0p. Physical testing rejected its history behavior,
while v4.0f remained viable but did not clearly beat v3.4. The six v4.1 models are included
in the report but have not yet been integrated into the live selector or field-tested.

## Reproduce

Run on the evaluation workstation with PyTorch, OpenCV, ReportLab, Matplotlib, and
ONNX Runtime GPU installed:

```bash
cd ~/rc_car_code
/home/rsabavat/.gpu-env/bin/python -u \
  code/test_files/models/evaluate_sidewalkpilot_models.py \
  --device cuda --batch-size 256
```

The default outputs are:

```text
docs/steering_eval_current_labels.json
docs/steering_model_report.pdf
```

`--versions` can restrict a debugging run, but a publishable all-model report must be
generated without that filter.

## Publication Checks

Before publishing:

1. Confirm the PDF and JSON come from the same run;
2. Confirm all 52 expected model keys exist;
3. Confirm the shared challenge count is 6,952;
4. Check that planned work is labeled as planned;
5. Avoid claims about a historical checkpoint's CARLA source mix unless its saved run
   command or source-count log proves it;
6. Keep field verdicts separate from offline rankings.

## Related Pages

- `publishing/pdf-report.md`
- `model-evaluation/offline-evaluation/overview.md`
- `model-evaluation/offline-evaluation/bal9.md`
