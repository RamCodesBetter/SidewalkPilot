# Series 5 workflow

- Integrate learning into substantive SidewalkPilot coding tasks without blocking implementation on a quiz: point to the real function and input/output contract, explain the design choice and a failure mode, show a reproducible check, and offer one hard prediction/debugging question about the change. Keep trivial maintenance brief. Distinguish student decisions, AI implementation, measured results, and planned work.

- Keep Series 5 work on the existing `series-5` branch (the user's “s5” branch).
- The canonical Mac label/review workspace is `/Users/ramsabavat/Desktop/rc_car_code/code/ai_models_datasets/series_5`. The old Desktop `SidewalkPilot-Labels` and repository-root `sp-labels` folders have been retired.
- Inside that workspace, keep the A/B/C trainer entry points directly in `series_5/`. Group supporting tools into `tools/labeling`, `datasets`, `evaluation`, `packaging`, `models`, `filtering`, `configs`, and `review`. Keep generated review bundles in `reviews/` and architecture documents in `docs/`. The Mac journal lives at `/Users/ramsabavat/Desktop/notebook`, outside the repository; do not recreate `series_5/notebook`. Do not scatter generated artifacts back across the workspace root.
- Use lowercase folder names and lowercase trainer filenames such as `series_5_a_sidewalkpilot_trainer.py`, following the Series 3/4 convention. Preserve model identifiers and data filename case.
- Keep published 5A/5B `.pth` and `.onnx` exports in `code/ai_models`; exclude model weights and generated review/dataset assets from Git commits.
- The Linux `/home/rsabavat/sidewalkpilot-labels` directory remains the separate training and review history store.
- For every small completed change: create a focused commit, push it to `origin/series-5`, then update the Mac checkout and its local artifacts. Follow this order automatically; do not wait for another reminder.
