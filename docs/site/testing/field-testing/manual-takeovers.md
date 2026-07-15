# Manual Takeovers

A manual takeover is when I use the steering stick, gas trigger, or brake to cancel an autonomous run. Takeover frequency is a useful field metric when route, distance, conditions, and intervention criteria are held constant. Controller availability and software priority are not guarantees against a disconnected controller, a stalled process, power loss, or a mechanical fault.

## How takeover works in the runtime

Override is built into `runtime.py`. While `autonomous_mode` is true, these qualifying inputs call `cancel_autonomous_mode()` when processed:

- **Steering:** a left-stick value with `abs(raw_steer_val) > 0.1` calls `cancel_autonomous_mode(..., "Autonomous driving cancelled by steering input.", center=False)` — it hands steering straight to me without re-centering, so I keep the angle I'm holding.
- **Gas:** throttle `> 0.05` cancels with `"Autonomous driving cancelled by gas pedal."`
- **Brake:** brake active cancels with `"Autonomous driving cancelled by brake."`
- **Quit:** button `15` (`QUIT_BUTTON`) sets the shutdown flag and ends the run cleanly (final log row, dashboard shutdown, GPIO cleanup).

`cancel_autonomous_mode()` zeroes requested throttle, clears brake force, resets PID state, and (for gas/brake) re-centers steering rather than intentionally retaining the model's command. If the run was on a GPS `AUTO` navigation segment, the same inputs also cancel the navigation route. Physical response still depends on loop timing, actuator health, traction, and power.

The preflight checklist tests this path on a stand: qualifying input enters the Pi event loop and autonomy cancels on a following control iteration. A timed latency record is still needed before quoting an override time.

## How a takeover is counted

Takeovers are counted from the field logs, not from memory. In the run CSV, a takeover is where `Autonomous Mode (On/Off)` flips from On to Off mid-route (not from a planned segment handoff or arrival). The stdout cancel messages above name the trigger (steering / gas / brake). Each takeover is logged with:

- **When** in the run (and roughly where on the route).
- **Why** — what the car was about to do that made me intervene (drift toward a curb, miss a turn, freeze on a shadow, head for a road edge).
- **Trigger** — steer, gas, or brake.

## Pass / warn / fail

- **Pass:** the route completed with **zero takeovers** — the model held the sidewalk end to end.
- **Warn:** completed but with one or more takeovers I made out of caution, where the car might still have recovered on its own.
- **Fail:** a takeover that was *necessary* to stop the car leaving the sidewalk or hitting something. One necessary takeover fails the run.

The direction I'm chasing is distance-per-takeover going up across model versions. This feeds the field-evaluation takeover-count metric.

## Field note

Takeover counts are only meaningful against a fixed route and defined intervention criteria — otherwise "I grabbed it a couple times" isn't a measurement. The per-run takeover summary (count + trigger breakdown per route) is **planned** as an automated CSV rollup on Jon; today it's read by hand from the `Autonomous Mode` column of each run log.

## Related pages

- `testing/field-testing/overview.md`
- `model-evaluation/field-evaluation/overview.md`
- `safety-case/safety-overview.md`
