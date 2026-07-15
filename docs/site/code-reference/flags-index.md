# Flags and Overrides Index

## Car Runtime

The live `rc_car.py` intentionally has no command-line model flag. Run `car`, then select the model on the dashboard model page. Startup can be overridden with:

| Environment variable | Purpose | Default |
|---|---|---|
| `RC_CAR_STEERING_MODEL` | Initial model name | `3.4` |
| `RC_CAR_STEERING_MODEL_PATH` | Explicit local early-model checkpoint | unset |
| `RC_CAR_STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG` | Hardware reference left limit | current config value |
| `RC_CAR_STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG` | Hardware reference right limit | current config value |
| `RC_CAR_STEERING_SERVO_CENTER_OFFSET` | Hardware center calibration | current `+12D` mapping |

Jon host/port, dashboard transport, sensor ports, AEB thresholds, and controller mappings are defined in `rc_car_app/config.py`. Treat the source as authoritative because deployment units can override environment values.

## Trainer Flags

The Series 3 trainer and three Series 4 wrappers expose their current arguments through `--help`. Common controls include dataset roots, epochs, batch size, learning rate, augmentation probabilities, throttle-loss weight for Series 3, temporal history/future steps for Series 4, output names, W&B mode, and `--keep-pth`.

Do not copy an old command without recording:

- Git commit;
- Dataset snapshot;
- Train/validation split identity;
- Full command line;
- Random seed;
- W&B run ID;
- Artifact SHA-256.

## Evaluator Flags

`code/test_files/models/evaluate_sidewalkpilot_models.py --help` is the source of truth. The current report run uses CUDA and a batch size selected for the evaluation GPU. It writes both JSON and PDF artifacts.

See [Training Command Setup](../runbooks/training-day/command-setup.md) and [Model Selection](../runbooks/field-test-day/model-selection.md).
