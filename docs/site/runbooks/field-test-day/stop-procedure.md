# Stop Procedure

Stop Procedure is the runbook for ending a run cleanly so the car halts safely, the dashboard receiver is told to stop, and the logs and photos are flushed intact. The runtime's `finally` block in `rc_car_app/runtime.py` does the ordered teardown; this runbook is how the operator drives it. Follow it in order; each step ends with an observed shutdown state.

## Preconditions

- The controller is connected, the Raspberry Pi 5 loop is responsive, and the operator has a physical power-stop option.
- If autonomous, cancel it first. Qualifying steering, gas, or brake input calls `cancel_autonomous_mode` when processed by the controller loop.

## Steps

1. Bring the car to a stop and take manual control. Touching the steering axis, throttle, or brake cancels autonomy and any active navigation route on the spot. Shift toward `P` if parking; gear `P` forces a hard brake and zero PWM.
2. Quit the controller. Press the quit button (button 15) or send `Ctrl+C`. Either sets `event_quit_pressed` and the `shutdown_flag`, breaking the main loop. Evidence: the loop exits into teardown.
3. Confirm the ordered teardown runs. The `finally` block: writes a final CSV row, stops the LiDAR thread, stops the GPS reader, stops the camera/vision thread, sends the dashboard shutdown and closes it, cleans up GPIO, closes the CSV file, removes an empty photo-run folder, and quits pygame. Evidence: no lingering errors on exit.
4. Confirm linked shutdown reached the Zero 2 W. `dashboard_sender.send_shutdown()` tells the receiver to stop, so the Zero 2 W display should go dark or show its shutdown state rather than sitting on stale telemetry. If it instead shows `NO LINK`, the receiver is alive but stopped getting packets — expected once the car quits.
5. Confirm GPIO returned to a safe state. `hardware.cleanup()` zeroes and closes all four motor channels and returns the steering servo to center (`STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0`) before releasing it. Evidence: motors dead, wheels near center.
6. Verify the outputs landed. The CSV `~/logs/log_YYYYMMDD_HHMMSS.csv` (or the equivalent under `RC_CAR_LOG_DIR`) should be closed and non-empty; the photo-run folder `media/photos/YYYY_MM_DD_run_N/` should exist with images and its JSON label file (an empty run folder is auto-removed by `cleanup_photo_run_dir`).
7. Power down safely: stop the drive-motor pack, then the electronics. Disconnect the LiPo for storage.

## Stop condition (emergency)

If the car will not respond to the quit path while moving, use the controller kill switch / manual override immediately, then physically cut the drive-motor pack. Autonomy also self-stops on its own safety paths: `blocked_path` (front clearance under the emergency-stop distance) and AEB in gear D both command a hard brake.

## Evidence

- Clean teardown log with no errors
- Zero 2 W dashboard in shutdown state
- Closed non-empty CSV and a populated photo-run folder with its label JSON

## Related pages

- `runbooks/sync-day/sync-verification.md`
- `testing/field-testing/preflight-checklist.md`
- `runbooks/training-day/model-export.md`
