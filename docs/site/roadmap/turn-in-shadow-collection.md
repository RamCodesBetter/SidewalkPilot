# Turn-In-Shadow Collection

Turn-in-shadow coverage began as a targeted response to one of SidewalkPilot's clearest
field failures: older models could mistake a hard shadow edge for the sidewalk boundary.
A turn-eager checkpoint chased the shadow, while a straight-biased checkpoint could miss a
real turn in shadow.

## What Changed

The current Series 3/4 dataset contains 81,237 labeled real images and is paired with
lighting and shadow augmentation. v3.3 increased the shadow-focused treatment but regressed
in the July 13 field comparison. v3.4 rebalanced the training treatment and completed every
shadow case presented in that comparison, becoming the current field-selected baseline.

This closes the original immediate milestone, not the whole perception problem. A finite
field run cannot prove robustness for every route, season, exposure, or shadow geometry.

## Collection Policy Now

There is no active promise to collect an arbitrary fixed number such as 5,000 frames per
bucket. New data should be failure-driven:

1. Preserve the exact clip and CSV for a takeover or wrong turn;
2. Tag route, lighting, shadow geometry, target steering class, and model;
3. Collect nearby successful and failed examples, not straight-heavy filler;
4. Audit class and scene coverage before merging;
5. Retrain on a frozen split and repeat the same physical case.

The highest-value additions remain real turns that overlap hard lighting transitions,
especially steering classes with weak balanced recall. Counts matter only after the new
frames are confirmed to occupy the intended class and scene buckets.

## Evidence Rule

Use “v3.4 passed the presented July 13 shadow cases,” not “v3.4 solves shadows.” Any broader
claim requires a named route set, repeated conditions, intervention counts, and stored run
artifacts.

## Related Pages

- `engineering-process/iteration-records/turn-vs-shadow-tradeoff.md`
- `data-governance/data-quality/turn-coverage.md`
- `roadmap/retraining.md`
