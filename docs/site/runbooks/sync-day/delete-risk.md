# Delete Risk

The single most damaging failure mode of a sync day: a reverse `rsync --delete` that treats "missing on the source" as "delete on the destination" and wipes a tree that only existed on one machine. This runbook is the guardrail I run in my head (and on the command line) before any pull, because this is the mistake that has cost the project the most.

## Preconditions

- I am about to run a sync that could go in the reverse direction (a machine pulling a whole tree onto itself), or any command that contains `--delete`.
- I know what lives on only one side. The docs source (`docs/site/**`), the generated site (`site/**`), and individual photo runs under `media/photos/YYYY_MM_DD_run_N/` are the trees most likely to exist on one machine and not the other.

## The Hazard in One Picture

```
rsync --delete  SRC/  DST/
                 |
                 v
   file exists on DST but NOT on SRC  ==>  rsync DELETES it on DST
```

So a reverse whole-repo pull from a machine that never had `docs/site/` will delete `docs/site/` on the machine that did. That is exactly what happened: a reverse whole-repo `rsync --delete` produced docs/site/generated-site deletion symptoms because the remote did not contain those trees.

## Steps (the check I run before every pull)

1. **Name the direction.** Is this the safe push-code-to-Pi direction (`rpisync`), or the dangerous pull-whole-tree-back direction (`mrpisync`)? If it is the pull direction, I slow down.
2. **Scope it.** Sync only the folder I actually want — `media/photos/2026_07_02_run_1/`, one checkpoint, one run — never the whole repo.
3. **Drop `--delete`.** For any reverse/pull sync, remove `--delete` entirely. I only ever want additive copies of data.
4. **Dry-run.** `rsync -avn ...` and read the output. If it lists a single `deleting ...` line I did not intend, I stop.

   ```bash
   # Read what WOULD happen before it happens
   rsync -avn <source>/ <dest>/
   ```

## Stop condition

- Any `deleting ...` line in a dry run that I did not explicitly intend.
- Any command that mirrors the whole repo in the reverse direction.
- Any uncertainty about which side has the docs/site tree or the newest photo run. When unsure, do not run it — count files first.

## Recovery

- **Docs / site disappeared after a pull.** Recover from git: `git -C ~/rc_car_code status`, then `git checkout -- docs/site site` (or the specific deleted paths). Do not "fix" it by re-syncing from the machine that caused the loss.
- **A photo run got deleted or truncated.** Restore from the other machine's copy — the whole point of scoped, additive copies is that a second intact copy still exists somewhere. Never clean untracked logs/photos during normal work.

## Cleanup

- None to add. The lesson is the opposite of cleanup: do not delete anything to tidy up around a sync. Leftover partial folders are re-filled by a scoped re-copy, not by wiping and re-mirroring.

## Notes / history

- Recorded rule: reverse whole-repo `rsync --delete` is dangerous. `rpisync` pushes local branch code to the Pi (safe). `mrpisync` pulls the whole remote tree to local and is the risky one with `--delete`.
- For photo pulls, sync only the `media/photos/...` folder, or remove `--delete` from the reverse sync.

## Evidence to attach

- Dry-run output showing no unintended `deleting` lines
- File/manifest counts before and after
- The exact rsync command that was run (direction, scope, flags)

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
