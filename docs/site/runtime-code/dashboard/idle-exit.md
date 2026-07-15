# Idle Exit

Idle exit is the receiver's watchdog: if the Zero 2 W has been receiving telemetry
and then the packets stop, the dashboard process exits on its own after a timeout
instead of sitting there showing frozen, stale data.

## How it works

The logic lives in `handle_idle()` inside `code/controller/current/z2w_dashboard.py`.
The UDP socket is bound with a 1-second timeout, so whenever a second passes with no
packet the loop calls `handle_idle()`. That function checks:

```python
if args.idle_exit_sec > 0.0 and have_received_payload \
        and time.monotonic() - last_packet_time >= args.idle_exit_sec:
    return 0   # clean exit
render_current_state()
```

Three conditions must all hold to exit:

- `--idle-exit-sec` is greater than 0 (the command-line default is `0.0`, which disables idle exit).
- `have_received_payload` is `True` — the receiver only self-exits *after* it has
  seen at least one real packet, so a receiver started before the car never exits
  just from waiting.
- No packet has arrived for at least `idle_exit_sec` seconds.

When those hold, `main()` returns `0`, the cleanup path clears the HUB75 panel,
and the process ends (0 exit code, so a `systemd` unit with
`Restart=on-failure` will *not* respawn it, while `Restart=always` would). If the
timeout has not elapsed, `handle_idle()` instead repaints the last known state so
page transitions and notification timers keep advancing during the gap.

There is a separate, deliberately-shutdown path: if a packet with `shutdown: true`
arrives, `handle_payload()` returns `0` immediately. That is the linked-shutdown
case (the car quitting), not idle exit. Idle exit specifically covers the *silent*
case where the link drops without a shutdown packet — a pulled USB cable, a crashed
car process, or a network stall.

The Pi side also defines `HUB75_DASHBOARD_IDLE_EXIT_SEC = 2.0` in `config.py`, but
that is only printed in the Pi's startup log for reference; the value that actually
governs receiver exit is the Zero's `--idle-exit-sec` argument.

## Why this choice

A frozen dashboard is worse than a blank one — it implies the car state is current
when it is not. Exiting cleanly makes the failure obvious (blank panel / stopped
service) and lets the service manager decide whether to restart. Requiring
`have_received_payload` first is what prevents a boot-order race: the Zero can come
up before the Pi and simply wait, only arming the watchdog once real data has flowed.

## Failure symptom

- Panel goes blank and the `dash` process/service stops a few seconds after the car
  stops sending — this is idle exit working as intended; check the Pi and the
  `usb0` link, not the Zero.
- The log line on exit states the configured timeout value.

## Evidence to attach

- Source: `code/controller/current/z2w_dashboard.py` (`handle_idle`, `--idle-exit-sec`)
- Pi reference constant: `code/controller/current/rc_car_app/config.py`
  (`HUB75_DASHBOARD_IDLE_EXIT_SEC`)
- Compile check: `python -m py_compile code/controller/current/z2w_dashboard.py`

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
