# Steering Trim Tuner

The steering trim tuner is the windowless, SSH-friendly utility I use to measure and set the steering center without launching the whole runtime. It drives only the steering servo — never the motors — so I can jog the wheels to true straight over an SSH session and read off the trim angle, then decide whether a constant needs to change. It lives at `code/test_files/steering_trim_tuner.py`.

## How it works

- It runs headless: it sets `SDL_VIDEODRIVER=dummy` so pygame reads the Xbox controller without opening any window, which is what makes it usable purely over SSH.
- It imports the runtime's PCA9685 address, frequency, channel, pulse range, and actuation range, then drives the servo directly through Adafruit `ServoKit`. It does **not** apply the runtime's reference-limit mapping or existing center trim; its printed angle is a raw calibration observation used to propose a trim.
- The D-pad nudges the servo angle by the trim step and the tool prints the current angle after each change. Defaults: start angle `90.0` degrees (logical center), trim step `1.0` degree, min angle `0.0`, max angle `180.0`, all clamped. Controller buttons: `RESET` = button `1` (recenter to start angle), `PRINT` = button `0` (print current trim), `QUIT` = button `15`.
- CLI flags let you override `--start`, `--step`, `--min-angle`, and `--max-angle`.

## Command

Run on the Pi 5 over SSH, Xbox controller connected, wheels off the ground:

```bash
python3 code/test_files/steering_trim_tuner.py
# custom start and finer step:
python3 code/test_files/steering_trim_tuner.py --start 90 --step 0.5
```

D-pad to jog the wheels straight, button `0` to print the trim, button `1` to reset, button `15` to quit.

## Why it matters

- It isolates trim from everything else. Trim, hysteresis, and left/right asymmetry get characterized here with a repeatable tool instead of being guessed at mid-drive or hidden inside runtime code.
- It keeps the logical convention separate from physical compensation: the tool measures a raw servo angle, while the runtime and saved labels continue to use logical `0..180` steering.
- Important caution: bench work observed direction-dependent return behavior, so the approach direction matters when interpreting one center reading. This tool does not determine whether a moving car's drift comes from steering geometry, motor balance, weight, surface slope, or another factor.

## Related pages

- `engineering-process/design-decisions/motor-imbalance-vs-steering-trim.md`
- `autonomy-stack/camera-steering/steering-hysteresis.md`
- `hardware/steering-servo.md`
