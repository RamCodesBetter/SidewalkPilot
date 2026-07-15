# IMU Verifier

The IMU verifier is the bench check for the Seeed XIAO MG24 6-axis IMU used by the live yaw-control path. It confirms which gyro axis is yaw, checks its sign, and exposes filter behavior before the runtime is allowed to use that signal. It runs the checked-in `code/test_files/imu_yaw_test.py`.

## How it works

- It reads the MG24's gyro CSV stream (`gx,gy,gz` in deg/s) off a serial port and shows the raw three axes alongside a filtered yaw value, so I can (a) confirm the yaw axis and (b) tune the filter.
- The filter chain applied to the yaw axis is the same one the steering PID will reuse:
  1. Median-of-N — kills isolated spikes (a lone `20` among `0,1,2` is ignored).
  2. EMA low-pass — smooths small jitter: `ema = a*median + (1-a)*ema`.
  3. Soft deadband — subtracts the threshold so values below it read `0` and values just above read near-zero (e.g. `3.5 -> 0.0`, `3.6 -> 0.1`); being continuous, it avoids `0 <-> threshold` edge chatter.
- Defaults: `--baud 115200`, `--axis 2` (yaw = Z; `0=X`, `1=Y`, `2=Z`), `--median 5`, `--ema 0.3`, `--deadband 3.5` deg/s. If no `--port` is given it auto-scans `/dev/ttyACM*` and `/dev/ttyUSB*`; for the GPIO UART you pass the port explicitly. It prints the raw `X/Y/Z` and the filtered yaw live, and the correct verification is: hold the sensor still and the filtered yaw should sit at `0`.

## Command

Run on the Pi 5 (IMU is on the GPIO UART `/dev/ttyAMA3`, Pi GPIO8/9):

```bash
python3 code/test_files/imu_yaw_test.py --port /dev/ttyAMA3
# tune: pick the yaw axis and filter
python3 code/test_files/imu_yaw_test.py --port /dev/ttyAMA3 --axis 2 --median 5 --ema 0.3 --deadband 2.0
```

## Pass / warn / fail

- Pass: rotating the car left/right moves exactly one axis strongly and with a consistent sign; held still, the filtered yaw sits at `0`.
- Warn: the filtered yaw drifts off zero at rest — raise the deadband or lower the EMA alpha, and note the residual.
- Fail: no stream on the port, or yaw doesn't respond to rotation — fix the UART/wiring (`/dev/ttyAMA3`, GPIO8/9) before trusting any downstream yaw-rate work.

## Why it matters

- This is the gate before closed-loop yaw-rate steering: it locks down the yaw axis and sign and hands the tuned median/EMA/deadband constants straight to the PID, so the controller and the verifier filter identically.
- Status: the firmware, verifier, runtime reader, and `YawController` are checked in. The default runtime mode is `straight`; field validation remains separate from implementation.

## Related pages

- `hardware/imu.md`
- `autonomy-stack/camera-steering/yaw-rate-pid.md`
- `testing/bench-tests/overview.md`
