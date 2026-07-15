# Hugging Face Model Cards

Each published Series 1-3 model has its own repository:

```text
ram-shreyas-naik-sabavat/SidewalkPilot-v<version>
```

The clean repository layout is `.gitattributes`, `README.md`, one model artifact, and `artifact_manifest.json`. `.DS_Store`, training datasets, report scratch files, and unrelated checkpoints do not belong in a model repository.

## Card Contract

Every card records:

- Architecture, parameter count, checkpoint role, creation time, and artifact format;
- Exact input shape, BGR/preprocessing policy, raw output shape, and decode formula;
- Evaluation dataset and whether metrics are held-out or fit checks;
- Chronological metrics only through that card's version;
- A class-balanced ranking through that version;
- Field verdict when that exact checkpoint has been tested;
- Intended use, limitations, independent safety requirements, and links; and
- Manifest purpose and artifact reproducibility.

Do not call a `b` checkpoint better without field evidence. Do not describe training-set metrics as held-out validation. Do not invent route details, takeover counts, or weather after a field run.

## Current Series 3 Field Text

- v3.3: field tested; worse than v3.2.
- v3.3b: field tested; much worse than v3.2b.
- v3.4: field tested; passed every presented shadow case and tested normal left/right turns; current field-selected baseline.
- v3.4b: field tested; slightly worse than v3.4.

The field report lacks exact route/time/weather/video/takeover metadata, and each card must state that limitation.

## Series 4 Release State

The six Series 4 artifacts are trained, exported, included in the common evaluator, and supported by the live Jetson code. They are not yet field-tested and no public `SidewalkPilot-v4.0*` model repository exists. Do not publish a Series 4 card that implies field selection. When release review begins, each card must document its PC/CF/PCF contract, ONNX inputs, horizon shape, causal-history behavior, and the common 6,952-frame metrics.

## Authentication and Upload

Authentication uses the cached Hugging Face token. Never commit or print the token.

```bash
python3 -c "from huggingface_hub import HfApi; print(HfApi().whoami()['name'])"
```

Upload a reviewed card with `HfApi.upload_file()` to `README.md` in the matching model repo. Use an explicit commit message and inspect the resulting file list afterward. Model-card source copies remain untracked locally by project policy; GitHub documentation links to the live cards instead of duplicating every README.

## Release Checks

1. Confirm repo name, artifact filename, and card version match.
2. Compute and compare artifact SHA-256 with `artifact_manifest.json`.
3. Inspect ONNX input/output signatures.
4. Confirm regular versus `b` checkpoint role.
5. Ensure chronological tables stop at the current card.
6. Search the upload set for `.DS_Store` and unrelated files.
7. Upload, list remote files, and download the remote README for final comparison.

See [Series 3 Models](../ai-and-models/model-zoo/series-3.md) and [Field Evaluation](../model-evaluation/field-evaluation/overview.md).
