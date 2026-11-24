# SidewalkPilot model workflow

- Integrate learning into substantive SidewalkPilot coding tasks without blocking implementation on a quiz: point to the real function and input/output contract, explain the design choice and a failure mode, show a reproducible check, and offer one hard prediction/debugging question about the change. Keep trivial maintenance brief. Distinguish student decisions, AI implementation, measured results, and planned work.

- Work on the branch selected for the task. The active model development branch is `series-5`; do not switch to main for cleanup.
- Use each model family's existing workspace under `code/ai_models_datasets/`. Keep trainer entry points at its root and supporting tools grouped by function. Keep generated review bundles under `reviews/`; do not create parallel Desktop review workspaces.
- Keep the student's technical study materials in `~/Desktop/technical` and journal in `~/Desktop/notebook` on the Mac, outside Git. Publishable evaluation reports belong in repo `docs/`.
- Use lowercase folders and trainer filenames. Preserve model identifiers and data filename case.
- Keep published local model exports in `code/ai_models`; exclude weights and generated review/dataset assets from Git commits.
- The Linux `/home/rsabavat/sidewalkpilot-labels` directory remains the separate training and review history store.
- For each completed change, commit only the relevant files, push to the matching remote branch, then fast-forward the Mac checkout and sync its local artifacts. Do not wait for another reminder.
