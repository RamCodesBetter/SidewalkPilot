# MkDocs Site

This documentation is a MkDocs site. It is the public, human-facing front door to the whole
SidewalkPilot project - the autonomy stack, hardware, models, evaluation, safety case, and
runbooks are all authored as Markdown and built into a static site by MkDocs.

## How It Works

The site is configured by `mkdocs.yml` at the repo root:

- `site_name: SidewalkPilot RC Car`
- `docs_dir: docs/site` - every page lives under `docs/site/**/*.md`.
- `theme: readthedocs` - the built-in Read the Docs theme.
- The full navigation tree is defined by the `nav:` block in `mkdocs.yml`; adding a page
  means adding both the Markdown file *and* its `nav` entry.

Source Markdown is edited under `docs/site/**`. Running the build turns that into a static
HTML site under `site/` at the repo root:

```bash
cd ~/rc_car_code
mkdocs build          # renders docs/site/** into site/**
mkdocs serve          # live local preview at http://127.0.0.1:8000
```

The generated `site/**` tree is committed output. **Edit the source under `docs/site/`, then
rebuild - do not hand-edit `site/**`**, or the next build
will overwrite the change.

## Why This Choice

- **One source, many readers.** Markdown keeps the docs diffable in git and lets the same
  content render as a browsable site for technical reviewers, mentors, and collaborators.
- **Read the Docs theme** gives a clean, searchable, sidebar-navigated layout with no custom
  front-end work, which fits a solo project.
- **Publishing is separated from drafting.** Public pages should never contain private paths,
  home addresses, private hostnames/IPs, stale claims, or unreviewed field media. Keeping the
  source in `docs/site/` and reviewing before build/publish keeps those out of the public
  site.

## Review Before Publishing

Before a build is treated as publishable, check:

1. **Accuracy** - facts on the page match the actual source code, config, and current model
   versions; Series 4.0 has its bounded field verdict, Series 4.1 is labeled as not yet
   integrated or field-tested, and Jetson Orin Nano quantization remains future work.
2. **Privacy** - no credentials, personal addresses, private hostnames, workstation
   usernames/paths, or unreviewed media appear on a public page. The fixed isolated-link
   addresses documented as part of the car's architecture are intentional.
3. **Links** - internal links resolve after `mkdocs build`, and external references (models,
   datasets) point at the correct Hugging Face repos rather than local paths.

## What Lives Where (GitHub, Read the Docs, and Hugging Face)

- **This MkDocs site** - the narrative: architecture, engineering process, evaluation method,
  safety case, runbooks. It links out to the model/dataset cards; it does not duplicate them.
- **Hugging Face** - the canonical home for full model cards, dataset cards, checkpoints, and
  ONNX exports. Those descriptions live there, not here (see the Hugging Face page).
- **GitHub** - the code, `mkdocs.yml`, and the built `site/**` output.

No documentation deployment workflow is checked into `.github/workflows/` or a
`.readthedocs.yml` file. The repository tracks locally generated `site/**` output;
the hosting configuration itself is external to this source tree.

## Related Pages

- [Reports and PDF](reports.md)
- [Hugging Face](huggingface.md)
- [Mac and Computer Sync](../operations/mac-pc-sync.md)
