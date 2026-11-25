# Series 5 tool map

## Follow one photograph

1. **Labeling proposes pixels.** SAM sees an RGB photo and returns candidate regions. In the strict detector, the first prompt is `concrete sidewalk`. The detector checks score, anchoring and fragmentation, then seeks agreement from a second prompt. A missing region, a low score and a failed anchor can all produce the same stored deferral reason.
2. **Filtering decides whether to trust a proposal for training.** Two confident masks are not enough: their overlap must pass the policy too. Disputed boundary pixels can be marked 255 (ignore). A passing mask is still an automatic label, not a human observation.
3. **Datasets decide where examples go.** A manifest pairs each image ID with the right target; a split assigns it to training, validation or test. Dataset code does not predict the mask. The trainers one directory up read those pairs and update the network.
4. **Training lives one directory up.** The shared Series 5 trainer defines the networks, losses, batch samplers, epoch loop, boundary metric and checkpoint selection. The A/B/C/E scripts each select one fixed recipe. The standalone model export tool converts a finished checkpoint to ONNX; it does not train.
5. **Evaluation measures errors.** These tools compare predictions and references, audit labeling methods, or measure boundary agreement. The cross-checkpoint PDF and JSON are now produced by `code/test_files/models/evaluate_series5_models.py`: default mode scores saved masks; `--infer` runs the checkpoints again.
6. **Packaging prepares files; review displays them.** Packaging writes a browser-readable bundle or serves progress counts. The browser code shows photos, overlays and scores and records ratings. A colored overlay is for people; the PNG containing class IDs is what the evaluator reads.

`workspace.py` only locates code and settings for imports. `configs/` stores defaults and class definitions. Neither loads a photo, runs a network or decides whether a mask passes.

**Full-inventory workflow:** `labeling/screen_full_inventory.py` reads the source inventory and first campaign receipts, skips already screened IDs, runs the strict detector on remaining frames, and writes new masks, per-loop decisions and progress. `review/serve_df_history.py` serves that history. A deferred record is not an accepted training mask. Neither program trains a model.

**Training and viewing:** datasets tools freeze image membership and supervision; the family-root trainers update weights. Evaluation measures predictions, packaging bundles data for offline use, and review contains the browser assets. Earlier pilots are retained for reproducing comparisons and as dependencies; they are not steps to rerun for every batch.

| File (relative to this directory) | Responsibility |
|---|---|
| `labeling/deferred_pilot.py` | Reconcile both screening ledgers, group deferred frames by the complete reason set and sample up to 30 for diagnosis. Does not relabel or promote frames. |
| `datasets/campaign10k.py` | Package exactly the original 10k campaign pairs for a shared grouped C/E experiment. |
| `datasets/freeze_ce_partitions.py` | Freeze C/E membership before annotation. Never invent missing reference masks. |
| `datasets/prepare_paired_review.py` | Freeze a new, review-disjoint sample and a private balanced A/B assignment. |
| `datasets/prepare_random_comparison.py` | Freeze a uniform random image sample for named, three-method comparison. |
| `datasets/prepare_reviewed_dataset.py` | Export the reconciled class-1 inventory without inventing negative labels. |
| `datasets/prepare_series5_pseudo_dataset.py` | Combine frozen reviewed labels with screened, explicitly weak SAM 3 labels. |
| `datasets/pseudo_training_targets.py` | Avoid learning questionable tiny negative regions from SAM pseudo-labels. |
| `evaluation/audit_sam_implementations.py` | Fixed ten-frame implementation comparison; never overwrites reviewed labels. |
| `evaluation/audit_series5_pseudo.py` | Report training-reference agreement and create retained-label inspection panels. |
| `evaluation/compare_sam31_sidewalk.py` | Run the official SAM 3.1 per-frame detector on the fixed ten-image audit. |
| `evaluation/compare_sam3_sidewalk.py` | Compare SAM 3 text-only proposals on the fixed ten-frame SAM 2 audit set. |
| `evaluation/diagnose_reviews.py` | Validate a class-1 review, select diagnostic frames, and render paired comparisons. |
| `evaluation/evaluate_class1_corrections.py` | Validate pixel-reference exports and evaluate frozen GSAM 2 diagnostic outputs. |
| `labeling/pseudo_mask_filter.py` | Conservative SAM prompt-agreement filter for explicitly unverified pseudo-labels. |
| `labeling/label_assisted_pilot.py` | Generate at most 200 class-1 masks from explicit, per-image assisted points. |
| `labeling/label_grounded_sam2.py` | Resumable, review-gated Grounding DINO + SAM 2.1 pilot on existing images. |
| `labeling/label_series5_campaign.py` | Screen the corpus resumably without weakening filters or leaking held-out days. |
| `labeling/label_series5_pseudo.py` | Freeze a training-only sample, then resumably label it with pinned native SAM 3. |
| `labeling/run_single_corridor_campaign.py` | Resumable SAM 3 campaign. Publish a diverse review only at 10k distinct automatic passes. |
| `labeling/sam3_assisted_review.py` | Read a historical paired selection for the pinned SAM diagnostic. |
| `labeling/sam3_corridor_batch.py` | Screen cached native SAM 3 labels and attempt a same-run temporal repair of deferred frames. |
| `labeling/sam_point_diagnostic.py` | Small SAM 2 point-prompt diagnostic, explicitly assisted rather than automatic. |
| `labeling/screen_full_inventory.py` | Screen every distinct inventory image once; preserve strict passes and deferred cases. |
| `models/convert_series5_checkpoint_to_onnx.py` | Convert a Series 5 PyTorch checkpoint to ONNX and verify its logits against PyTorch. |
| `review/mask_encoding.py` | Encode class-ID masks in the offline viewers' row-major [value, count] format. |
| `review/package_corridor_sample.py` | Package a deterministic variety sample of 30 single-sidewalk candidates for offline review. |
| `review/package_model_lab.py` | Build one offline comparison from a reproducible sample of the frozen C/E test split. |
| `review/serve_df_history.py` | Serve only aggregate D/F progress and loop counts, never files from the dataset. |
| `workspace.py` | Shared source locations for direct CLI entry points and flat module imports. |
| `review/assets/beta.html, beta.js, beta.css` | Unified model comparison: select checkpoints and compare their masks and metrics. |
| `review/assets/comparison.html, comparison.js, comparison.css` | Side-by-side annotation reviewer, correction severity, keyboard navigation and review export; shared styling is also used by the model viewer. |
| `review/assets/model_metrics.js` | Compute per-image pixel scores and handle unknown or undefined metrics. |
| `review/assets/campaign-history.html` | Render screening counts and loop history; not a mask viewer. |
| `review/assets/lucide.min.js, LUCIDE-LICENSE.txt` | Bundled offline icons and their license. |
| `configs/series_5_a_config.json, series_5_c_config.json` | Default trainer settings for the baseline and ConvNeXt experiments. |
| `configs/label_config.json, taxonomy.json` | Labeling settings and class definitions; the binary model outputs only sidewalk/background. |
