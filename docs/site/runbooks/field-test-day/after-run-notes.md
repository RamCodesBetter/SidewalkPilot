# After Run Notes

After Run Notes is the runbook for capturing what happened right after a field test, while it is still fresh, so runs can be compared across dates and so the data is triaged before it ever counts toward a training goal. It closes the loop between driving and the training/sync pipeline. Follow it in order; each step ends with a saved artifact or a written note.

## Preconditions

- The run ended cleanly (`stop-procedure.md`) with the CSV closed and the photo-run folder intact.
- The model version, route, and any calibration values used this run are known.

## Steps

1. Record the run identity: date, route, model version that actually loaded (from the `Loaded steering autonomy model ...` line), and the LiPo voltage from `battery-check.md`. These are what make one run comparable to another.
2. Locate the artifacts. The runtime CSV is `~/logs/log_YYYYMMDD_HHMMSS.csv` by default (or under `RC_CAR_LOG_DIR`; nominally 10 rows per second because `LOG_INTERVAL_SEC = 0.1`) and photos are under `media/photos/YYYY_MM_DD_run_N/` with a per-run JSON label file (`{photo_name: {steering, throttle}}`). Here, "logs" means these CSV files, not stdout. Evidence: file paths written down.
3. Note behavior from the drive: where the model held the sidewalk, where it turned late or chased shadows, any AEB stops, LiDAR overrides, or manual takeovers. The turn-vs-shadow tradeoff and mid-RIGHT / turn-in-shadow weakness are the known gaps to watch and log per clip.
4. Triage photos before adding them to a dataset snapshot. Count images/labels, flag corrupt files, and review lighting, blur, exposure, camera angle, obstruction, steering bias, and provenance. Do not delete data without explicit review; record inclusion or exclusion as a decision.
5. Note calibration observations without assigning a cause from one run. If the car pulled with steering centered, record motor balance, linkage/trim, payload, and surface as separate candidates. Leave trim, DELT, motor-scale, and PID constants unchanged until a controlled test supports a specific number.
6. Route the outputs. Photos and logs are data; sync only the target folders (`media/photos/...` and `~/logs/...`, or their configured replacements). Never do a reverse whole-repo `rsync --delete`. Training telemetry goes to Weights & Biases. Treat InfluxDB as an additional artifact only if the controller startup log confirmed that it was enabled.
7. File follow-ups: model versions to retest, data buckets still short, and any hardware issue to fix before the next batch.

## Stop condition (when to discard/redo)

If the run was on a weak pack, a stale camera frame, or a known hardware bias (e.g. left drift), mark the data as not counting toward the clean goal and flag the run for a redo rather than folding it into training.

## Evidence

- Run note: date, route, model version, LiPo voltage
- CSV path and photo-run folder path with image + corrupt counts
- Per-clip behavior notes (turns, AEB, overrides) and the count decision (pending vs counts)

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
