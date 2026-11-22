# Series 5 workflow

- Keep Series 5 work on the existing `series-5` branch (the user's “s5” branch).
- The canonical Mac label/review workspace is `/Users/ramsabavat/Desktop/rc_car_code/code/ai_models_datasets/series_5`. The old Desktop `SidewalkPilot-Labels` and repository-root `sp-labels` folders have been retired.
- Use lowercase folder names and lowercase trainer filenames such as `series_5_a_sidewalkpilot_trainer.py`, following the Series 3/4 convention. Preserve model identifiers and data filename case.
- Keep published 5A/5B `.pth` and `.onnx` exports in `code/ai_models`; exclude model weights and generated review/dataset assets from Git commits.
- The Linux `/home/rsabavat/sidewalkpilot-labels` directory remains the separate training and review history store.
