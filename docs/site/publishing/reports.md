# Reports and PDF

SidewalkPilot keeps generated reports in the repository so a reader can inspect the exact
evidence associated with a commit rather than relying on a manually copied metric.

## Current Outputs

| Output | File | Source | Scope |
|---|---|---|---|
| Steering Model Report | `docs/steering_model_report.pdf` | `code/test_files/models/evaluate_sidewalkpilot_models.py` | 52 checkpoints from v1.0 through v4.1c on one 6,952-frame shared challenge set, plus a separate 2,224-image historical Series 1/2 table |
| Machine-readable steering results | `docs/steering_eval_current_labels.json` | same evaluator | complete metrics, source breakdowns, confusion matrices, checkpoint metadata, and historical Series 1/2 blocks |

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
python -u \
  code/test_files/models/evaluate_sidewalkpilot_models.py \
  --device cuda --batch-size 256
```

The default outputs are:

```text
docs/steering_eval_current_labels.json
docs/steering_model_report.pdf
```

`--versions` can restrict a debugging run, but a publishable all-checkpoint report must be
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

## PDF Generation Contract

The evaluator owns both the JSON and PDF so table values are not manually recopied. A publishable report is generated from the full version list on the frozen challenge set, with GPU execution requested where available. Review page count, model count, gradient coloring, confusion matrices, Series 1/2 historical separation, and the field-status wording before committing the outputs.

If the evaluator or dataset changes, regenerate the JSON and PDF together. Never update one output while leaving the other from a different run.

## Related Pages

- [Offline Evaluation](../model-evaluation/offline-evaluation/overview.md)
- [Bal9](../model-evaluation/offline-evaluation/bal9.md)
- [Model Selection Rubric](../model-evaluation/comparisons/model-selection-rubric.md)
