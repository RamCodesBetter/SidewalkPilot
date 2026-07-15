# PCB Revisions

This is the revision history of the custom RPi5 breakout board. I am keeping it honest and short: the board has never been fabricated, so there is no "manufactured rev" yet. There is one drawn design, it is already outdated, and a corrected revision is planned before I order anything.

## How it works

I track PCB revisions the same way I track model versions: a revision only counts as "real" once it exists as a physical thing that the car has run on. Everything before that is a design draft. Because the board freezes the pinout in copper, the gate for advancing a revision is that the drawn GPIO map exactly matches the runtime `config.py` pins — not that the layout merely looks finished.

## Revision history

| Rev | State | GPIO match | Fab / on car | Notes |
|---|---|---|---|---|
| Rev A (first draft) | Designed only | **Outdated** — does not match current `config.py` | No / No | Original layout. I re-pinned parts of the runtime after this was drawn, so its GPIO map is stale. Not ordered, not fabricated. |
| Rev B (planned) | Not started | Will be re-drawn to match current runtime pins | Planned | The corrected revision. Blocked on finalizing the runtime pinout so I don't bake in a moving target. Planned / not-yet-done. |

## Why it matters

A PCB respin costs money and lead time, so the discipline here is to *not* fabricate until the pinout is stable. Rev A captured the first layout but also exposed a real trap: the runtime pin assignments were still moving, and fabricating then would have frozen a stale map into copper. Treating Rev A as design-only and deferring Rev B until the GPIO is settled is the cheaper path: fabricate once against a final map instead of chasing respins.

## What has to be true before Rev B is ordered

- Runtime GPIO pinout in `config.py` is finalized and stable (the current source of truth).
- The [GPIO Mapping](gpio-mapping.md) and [Schematic](schematic.md) pages are re-drawn to match, including the LiDAR path decision (USB CP2102 vs GPIO UART).
- Power/ground and motor-driver isolation reviewed on the schematic.

Until all of that holds, the board stays design-only and the breadboard harness remains the car's real wiring.

## Related pages

- `hardware/pcb/overview.md`
- `hardware/pcb/gpio-mapping.md`
- `roadmap/next-steps.md`
