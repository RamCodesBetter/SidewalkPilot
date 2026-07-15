# LiDAR Distance Regions

The LiDAR policy evaluates only points in the car-relative center corridor: `forward > 0` and `abs(lateral) <= 0.254 m`. The nearest qualifying forward point selects one longitudinal action.

| Nearest center point | Action | Maximum forward command |
|---:|---|---:|
| No point or `>= 1.65 m` | Normal | 100% reference |
| `1.65 m` down to `1.25 m` | Slow | Linear 100% to 60% reference |
| `1.25 m` down to `1.05 m` | Creep/hold | 60% reference |
| `<= 1.05 m` | Emergency brake | Zero throttle + hard brake |

## Reference and Physical Throttle

The car begins moving near 55% physical PWM. The LiDAR governor's reference throttle maps `0..100%` onto physical `55..100%` while preserving physical zero as stopped. Manual Xbox-trigger input is not passed through this mapping; it remains a direct physical command. Therefore:

```text
physical = 0.55 + reference * (1.00 - 0.55)
```

At 60% reference, physical PWM is `0.82`. Dashboard control values use the reference scale; photo/training labels retain the absolute physical command, so the same moment is labeled `0.82`. In manual mode, the trigger still has to cross the measured physical dead zone before the car moves.

## AEB Toggle

With AEB OFF, `evaluate(..., enabled=False)` reports telemetry but returns full throttle permission and no stop. With AEB ON, the same policy governs manual and autonomous forward driving. Reverse is not governed by the forward corridor.

## Display Rungs

The LiDAR page draws four colored horizontal rungs across the active center corridor plus two blue vertical guides. Side points remain visible for context but cannot change control or the `C` lane state.

## Verification

```bash
python3 code/test_files/lidar/test_lidar_center_aeb.py -v
python3 code/test_files/display/test_z2w_lidar_layout.py -v
```

An empty or stale scan cannot prove a clear corridor; sensor health must be checked independently before driving. See [AEB](aeb.md) and [Why LiDAR Does Not Steer](override-steering.md).
