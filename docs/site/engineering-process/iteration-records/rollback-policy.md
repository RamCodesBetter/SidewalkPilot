# Rollback Policy

Rollback means selecting a previously field-accepted artifact after a newer candidate performs worse. Versioned filenames make this practical, but preservation still depends on not retraining into the same output name and not deleting or replacing the deployed ONNX file.

## Artifact naming

- Series 1/2 and Series 3 runs use versioned final/alternate pairs such as `3.4` and `3.4b`.
- Series 4 uses PC `p/r`, CF `f/g`, and PCF `a/c` pairs.
- The regular and alternate files are checkpoint roles, not automatic field rankings.

The trainer will write to the path implied by the selected version. Reusing a version can overwrite that artifact, so a pre-training check must confirm that output names are new or intentionally replaceable. Git/Hugging Face history and verified copies are the recovery path; filename conventions alone are not a backup.

## Runtime rollback

The Raspberry Pi 5 dashboard selects a registered version. For Series 3/4, Jetson Orin Nano receives that name, resolves the matching ONNX artifact, and hot-swaps models. A rollback is complete only after:

1. The intended artifact is present on Jetson Orin Nano;
2. Jetson Orin Nano logs a successful load with the expected execution provider;
3. The Raspberry Pi 5 receives fresh results tagged for that model; and
4. A restrained bench check confirms expected steering direction before motion.

A controller restart is not normally required for the current hot-swap path. Restart the owning process only when deployment state or logs show that the switch did not take effect.

## Selection rule

v3.4 is the current field-selected baseline from the bounded July 13 comparison. If a Series 4 candidate regresses in the physical comparison, select v3.4 and record the failed candidate, route/case, CSV, and video evidence. Do not call an alternate `b/r/g/c` checkpoint safer merely because its validation loss was lower.

## Limits

- A previous field result is condition-specific, not a guarantee that the artifact is safe in every environment.
- Rollback does not undo runtime/config/hardware changes made at the same time. Preserve those revisions separately.
- A name on the dashboard does not prove the intended bytes loaded on Jetson Orin Nano.

## Related pages

- [B Checkpoints](../design-decisions/b-checkpoints.md)
- [Model Switching](../../runtime-code/vision/model-switching.md)
- [Model Retest Plan](../../testing/field-testing/model-retest-plan.md)
