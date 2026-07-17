# Mac / PC Sync

Moving code, datasets, photos, and models between the Mac and the NVIDIA PC (and out to the Raspberry Pi 5) without a sync accidentally deleting the docs tree or a photo run. This is the operation that has bitten the project hardest, so the rules here are conservative on purpose.

## How it works

Two directions of sync exist, and they are not symmetric:

- **Push code to the Raspberry Pi 5**: sends the local branch's controller/runtime code to the Raspberry Pi 5 after switching and pulling the chosen branch. This is the safe, everyday direction.
- **Pull the whole remote tree back**: mirrors a remote checkout onto the local machine. This is the direction that can delete local files when `--delete` is used and the remote is missing a tree (docs, generated site, a photo run).

Data lives in a few well-known places and is treated as data, not source:

- `~/logs/` (or `RC_CAR_LOG_DIR`) — runtime CSV logs, outside the repository by default.
- `media/photos/YYYY_MM_DD_run_N/` — field photo runs, often with a JSON manifest.
- `code/ai_models/*.pth` — model checkpoints.

## Why this choice

- A reverse whole-repo `rsync --delete` is dangerous: it has produced docs/site/generated-site deletion symptoms when the remote did not contain those trees. For photo pulls, sync **only** the target `media/photos/...` folder, or drop `--delete` entirely.
- Photos, logs, datasets, and checkpoints are never staged, renamed, or deleted as a side effect of a sync. They are the project's irreplaceable field data.
- Keeping "push code to Raspberry Pi 5" and "pull tree to laptop" as clearly distinct operations stops the risky direction from being run by muscle memory.

## Public-safe examples

Use placeholders for private hosts and pull only the folder you actually want:

```bash
# Pull ONE photo run from a device, no --delete
rsync -av <user>@<device>:~/rc_car_code/media/photos/2026_07_02_run_1/ \
  ./media/photos/2026_07_02_run_1/

# Push code changes to the Raspberry Pi 5 (safe direction), scoped to the controller
rsync -av ./code/controller/current/ <user>@<pi>:~/rc_car_code/code/controller/current/
```

Never run a whole-repo reverse sync with `--delete`.

## Failure and recovery

- **Docs / site disappeared after a pull**: a reverse `--delete` sync removed trees the remote lacked. Recover from git (`git status`, `git checkout` the deleted paths) rather than re-syncing.
- **A photo run looks truncated**: verify the manifest count against the files on disk before assuming loss; do not delete anything to "clean up."
- **Uncertain which direction to run**: default to the push-to-Raspberry Pi 5 direction and pull only a named data folder. When in doubt, drop `--delete`.

## Evidence to attach

- Dry-run (`rsync -avn ...`) output before the real run
- Branch status on both ends
- File/manifest counts before and after

## Related pages

- [Sync Day](../runbooks/sync-day/mac-to-pc.md)
- [MkDocs Site](../publishing/mkdocs-site.md)
- [Data Quality](../data-governance/data-quality/image-quality-checks.md)
