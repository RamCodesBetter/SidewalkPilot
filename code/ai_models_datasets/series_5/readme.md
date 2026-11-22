# Series 5 Workspace

Keep work on `series-5`. This is a folder cleanup, not a new model recipe.

| Folder | Contents |
| --- | --- |
| `series_5_*_sidewalkpilot_trainer.py` | A/B/C training entry points, directly in this folder |
| `tools/labeling/` | SAM inference, labeling campaigns, and mask repair |
| `tools/datasets/` | Dataset and review selection, splits, training targets |
| `tools/evaluation/` | Audits, diagnostics, comparisons, and scoring |
| `tools/packaging/` | Portable review bundles and comparison viewers |
| `tools/models/` | Model architecture and export code |
| `tools/filtering/` | Mask filtering policies |
| `tools/configs/` | Model/labeling configs and class taxonomy |
| `tools/review/` | Viewer HTML/CSS/JavaScript and terminal review launcher |
| `reviews/` | Complete local review bundles, including their images, masks and exports |
| `docs/` | Local architecture PDF, LaTeX/Typst source and related documents |

Generated artifacts are ignored by Git. On the Mac, the workspace is
`~/Desktop/rc_car_code/code/ai_models_datasets/series_5/`.
The Linux history store stays at `~/sidewalkpilot-labels`; checkpoint paths there
have not moved. Published model exports stay in `code/ai_models/`.
The recovered Mac journal is `~/Desktop/notebook/`, outside this workspace.

## Open on the Mac

- 5.A versus 5.B: `reviews/5.a-vs-5.b/index.html`
- 5.A test viewer: `reviews/5.a-test/index.html`
- Paired mask review: `reviews/paired-review/index.html`
- Thirty-image comparison: `reviews/random-30-comparison/index.html`
- Architecture PDF: `docs/5.c-architecture/sidewalkpilot-5C-math-and-cs.pdf`
- Older root-level class-1 data: `reviews/legacy-class1/`

Each complete viewer bundle keeps its internal paths and filenames unchanged.
Do not discard downloaded review/correction JSON files: browser-only drafts may
need to be reimported after a viewer's file URL changes. Moving files does not
clear or approve any review decisions.

## Current Entry Points

Run from the repository root; add the existing dataset, split and output arguments.

```sh
python code/ai_models_datasets/series_5/series_5_c_sidewalkpilot_trainer.py --help
python code/ai_models_datasets/series_5/tools/labeling/label_series5_campaign.py --help
python code/ai_models_datasets/series_5/tools/packaging/package_beta_comparison.py --help
```

All three trainers live directly in `series_5/`. Architecture, configs, frozen
label-policy files, viewer templates and historical diagnostics stay in `tools/`.
The entry points resolve those paths without changing the working directory.
`tools/workspace.py` centralizes source lookup and direct-script import paths.
Archived run contracts and code hashes remain historical records. Do not rewrite
them to bypass a resume check after this source-layout change.

## Migrate an Existing Flat Workspace

After updating the checkout, run from the repository root:

```sh
python3 code/ai_models_datasets/series_5/tools/organize_workspace.py
python3 code/ai_models_datasets/series_5/tools/organize_workspace.py --apply
```

The first command is a dry run. The second moves only the recognized generated
bundles, refuses destination collisions, hashes files before/after, and records
the moves in local `workspace-migration.json`. It neither deletes files nor
rewrites historical manifests, masks, checkpoint contracts, or review decisions.
It is safe to rerun after a successful migration.
