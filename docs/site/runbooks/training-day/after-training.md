# After Training

After Training is the runbook that turns a finished run into a judged, recorded result. The run produced checkpoints; this step evaluates them, decides which one is a candidate to deploy, and writes down the verdict so future runs can be compared.

## Preconditions

- During Training finished and wrote `SidewalkPilot-v3.x.pth` (final) and `SidewalkPilot-v3.xb.pth` (best) into `code/ai_models/`.
- The stdout log and W&B run URL are saved.
- A held-out or field eval set is available for the evaluator.

## Steps

1. Run the common evaluator from the repository root. It discovers supported Series 1-4 checkpoints, evaluates the selected versions on the frozen common Series 3/4 subset, and updates the JSON and PDF:
   ```bash
   python3 code/test_files/models/evaluate_sidewalkpilot_models.py \
     --device cuda \
     --versions 3.x 3.xb
   ```
2. Read the metrics as a set, not one number: Bal9, turn exact, turn +/-1, straight exact, steering MAE, median absolute error, signed steering error, and the confusion matrix. A collapsed model usually concentrates predictions near straight and leaves turn rows weak.
3. Compare final vs paired best. In Series 3/4 the paired checkpoint is lowest steering MAE; in Series 1/2 it is lowest validation loss. Either can still be straight-biased. Shortlist with turn coverage, confusion balance, Bal9, MAE, signed error, and then field behavior.
4. Check signed steering error for a left/right prediction bias. Do not equate offline signed error with physical drift. Reproduce a physical pull on a controlled flat test before changing model, servo, motor-scale, or IMU settings.
5. Record field-test status independently from training status. The July 13 drive rejected v3.3/v3.3b and selected v3.4; Series 4 remains not yet field-tested.
6. Update artifacts that are factual now. The report PDF (bucket + MAE numbers) is factual and can be updated anytime; a Hugging Face model card's pros/cons wait for a field verdict, and a card lists versions only up to itself.

## Stop condition

- Do not declare a model "good" from MAE alone or from the armchair — a verdict needs the evaluator output and, for a deploy claim, a real field test.
- Do not promote a straight-collapsed checkpoint (narrow predicted range, empty turn buckets) just because its loss/MAE is lowest.
- Do not overwrite or delete existing checkpoints/model cards without cause.

## Evidence

- `docs/steering_eval_current_labels.json` and `docs/steering_model_report.pdf`.
- The metric read: Bal9, turn metrics, straight recall, MAE/median/signed error, and confusion balance.
- The chosen deploy candidate and the one-line reason.
- Field-test status: tested / untested-planned.

## Cleanup

- Move only the intended checkpoints into `code/ai_models/`; leave unrelated checkpoints alone.
- Prune scratch/temp exports you created, but do not delete datasets, logs, photos, or existing model checkpoints without explicit approval.

## Notes

- Deploying to the field is a separate step handled in Model Export: the deploy candidate is exported to ONNX, its version is added to the Pi's `STEERING_MODEL_VERSIONS`, and the `.onnx` is copied to Jon, which auto-resolves it.

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
