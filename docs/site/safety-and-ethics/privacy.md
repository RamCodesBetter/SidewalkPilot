# Privacy

This page describes what data SidewalkPilot collects, where it is stored, and how privacy is handled. The car carries a forward camera (Raspberry Pi Camera Module 3 Wide) and a GPS, so it captures images of real sidewalks and, potentially, of people, houses, and vehicles nearby. The project treats that as a real privacy responsibility, not an afterthought.

## What is collected

- **Camera frames.** The autonomy loop reads live frames for steering inference (`vision.py`). Frames are written to disk either when the operator presses B (`PHOTO_BUTTON = 1` in Pygame's zero-based numbering) or when the operator explicitly enables run capture with the Menu button. Run capture targets 10 fps while the car is moving and stops when toggled off or when the runtime exits.
- **Steering / throttle labels.** Each queued photo appends a row to the run label CSV. `finalize_photo_run()` later builds the per-run JSON manifest. These labels contain the logical steering command and absolute forward-throttle value; they do not contain GPS coordinates, face data, or an identity field.
- **Runtime CSV logs.** The logger (`logging_utils.py`, headers in `config.py`) records vehicle telemetry: speed, gear, steering, brake, AEB state, LiDAR distances, CPU/temperature, camera confidence. These are numeric vehicle-state logs, not imagery, and they do not store raw GPS coordinates in the CSV headers as defined.

## Where it is stored

Field capture stays local to the vehicle. Photos are written under `media/photos/YYYY_MM_DD_run_N/` (`create_photo_run_dir`), one folder per run, named `photo_<timestamp>.jpg`. CSV logs are written under `~/logs` by default. Camera frames used for remote inference travel over the private Raspberry Pi 5–Jetson Orin Nano Ethernet link; dashboard state travels over the private Raspberry Pi 5–Zero 2 W USB Ethernet link. The runtime does not upload field images to a cloud service. Optional InfluxDB telemetry is numeric vehicle state and is configured separately through `~/.influxdb.json`.

Training telemetry (Weights & Biases) is generated from the training pipeline on a separate machine, not from the car during a drive, and covers model metrics rather than raw field imagery.

## Handling and limits

- **Local-first.** Images live on the Raspberry Pi 5 until Ram intentionally pulls them to the Mac workstation for training-set curation. The documented sync guidance deliberately avoids destructive whole-repo mirroring so field data is not accidentally deleted or duplicated.
- **Purpose-scoped.** Captured sidewalk images exist to train the steering model. They are not used to identify people, and the saved label carries no personal data.
- **Public dataset care.** Datasets and model cards are published on Hugging Face (`ram-shreyas-naik-sabavat`). Incidental bystanders, plates, house details, and location clues remain a release risk. The project policy is to review or exclude sensitive imagery before publication; this page does not claim automated redaction or a completed frame-by-frame privacy certification.
- **Bystander minimization.** The platform is human-supervised, and both single-photo and run-capture modes require an operator action. Run capture can record many frames, so route choice and pre-publication review remain necessary.

## Series 3 note

Series 3 and Series 4 send frames from the Raspberry Pi 5 to the Jetson Orin Nano at `10.42.0.2:8770` for inference. That local transfer is not itself a storage or publication path. Images are persisted only through the Raspberry Pi 5's operator-controlled photo/run-capture flow. Any future inference-frame logging on Jetson Orin Nano would be a new data path and should be reviewed against this page before use.

## Related pages

- `safety-case/safety-overview.md`
- `testing/field-testing/preflight-checklist.md`
- `autonomy-stack/architecture/decision-priority.md`
