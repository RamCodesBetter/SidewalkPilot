# Mini Test Dataset

This folder contains 180 real SidewalkPilot images used only to run consistent
inference-speed tests on the Raspberry Pi 5 and Jetson Orin Nano.

It is **not** the model training dataset. These images were sampled from the
separate original 81,237-image Series 3/4 model-training snapshot.

`codex_visual_review.csv` preserves AI-assisted review proposals for these 180
benchmark images. Its `fix` and `drop` rows are suggestions, not verified ground
truth or applied changes to the main dataset's original steering labels.
