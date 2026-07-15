# Lighting Coverage

The rule that the dataset must span the lighting conditions the car actually drives in — bright sun, overcast, hard tree/edge shadows, and night — not just easy even light. Uneven lighting coverage is one of the two failure modes Series 3 is built to fight, so lighting is tracked as a first-class quality axis alongside turn coverage.

## How it works

Lighting coverage is addressed in two layers: real captures and synthetic augmentation.

The real layer is the goal. The known Series 3 gap is turns and, specifically, turns-in-shadow: the model's turn-vs-shadow trade-off can only be broken with real turn-in-shadow frames, not synthetic ones. So a lighting-coverage check is really asking "do we have enough real hard-shadow and low-light frames, especially while turning?"

The synthetic layer lives in the trainer (`code/ai_models_datasets/series_3_and_4/series_3_sidewalkpilot_trainer.py`) and stress-tests lighting robustness at train time via `apply_shadow_stress_augmentation()`, which randomly composes:

- `apply_mixed_lighting()` — sun/shade split across the frame.
- `apply_diagonal_shadow_band()` — a hard diagonal shadow edge with a brightened sunny side.
- `apply_tree_shadow_pattern()` — dappled tree-canopy shadow.
- `apply_sidewalk_road_edge_shadow()` — the shadow line where sidewalk meets road.

These run at `shadow_aug_probability` (0.85 by default) on real frames. CARLA/synthetic roots additionally get `apply_carla_domain_randomization()` (brightness/contrast jitter). Augmentation broadens the training distribution, but its effect must be established by controlled evaluation. It is not evidence that the model handles every real shadow or that real lighting coverage is unnecessary.

For measuring what lighting the real dataset already contains, the tracked starting point is `code/test_files/data/dataset_scene_tags.py`, with `dataset_clusters.py` and `dataset_cosine_similarity.py` available for related analysis. These tools can generate local HTML and embedding outputs under `code/test_files/data/`, but those outputs are untracked working files in this branch. They are therefore not cited as published evidence.

## Why it matters

The central field observation is that some turn-eager checkpoints also followed shadow edges, while more center-biased behavior could miss turns. Real turn-in-shadow collection directly covers that combined condition. It complements augmentation and still requires a repeated field test before a robustness claim.

## Good vs bad example

- Good: a run captured in bright midday sun under trees, with dappled shadow crossing the sidewalk during left and right turns.
- Bad: a batch shot only on flat overcast light with the sun behind the camera. It will train cleanly and score well on MAE, and still fail the first time the car meets a hard shadow edge (compare the v3.1b field verdict: good at night, failed on the orange lamppost / shadow-like light).

## Validation (planned)

A dedicated lighting-coverage counter is not yet a single scripted command. The current analysis path is to run the tracked scene-tag script, inspect its local output, and preserve the command and dataset revision with any reported result. A one-command, checked-in lighting histogram report is planned but not yet built.

## Recovery step

If a lighting bucket is thin (usually hard-shadow-while-turning), the fix is to collect real frames in that condition — schedule a bright-sun hard-shadow turn run — not to raise the synthetic shadow probability. Do not count a known-biased lighting batch toward the goal without Ram's decision.

## Evidence to attach

- The scene-tag / lighting split for the batch (from the CLIP tooling).
- Sample thumbnails from the thin bucket (e.g. turn-in-shadow) confirming they are real, not augmented.

## Related pages

- `data/dataset-overview.md`
- `data-governance/dataset-versioning/active-label-set.md`
- `publishing/huggingface.md`
