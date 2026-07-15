# Test Files

`code/test_files/` contains standalone bench, calibration, data, evaluation, and
setup utilities. Hardware and navigation utilities are grouped into subsystem
folders; cross-cutting dataset, model-evaluation, and controller experiments remain
at the directory root.

## Main utilities

| Area | Checked-in files | Purpose |
|---|---|---|
| Steering | `steering/pca9685_servo_test.py`, `steering/calibrate_servo.py`, `steering/model_steering_test.py`, `steering_trim_tuner.py`, `servo_step_controller.py` | Servo motion, center calibration, and model-to-steering checks |
| LiDAR | `lidar/lidar_viewer.py`, `lidar_uart_test.py`, `lidar_avoidance_sim.py`, `test_lidar_center_aeb.py` | Raw transport, visualization, policy simulation, and center-corridor tests |
| Camera/data | `camera/test_camera_preview.py`, `camera/test_camera_flip.py`, `photo_run_to_dataset.py`, `check_dataset_frames.py`, `camera/preview_series3_augmentations.py` | Capture, orientation, dataset conversion/audit, and augmentation preview |
| Display | `display/hub75_rgbmatrix_test.py`, `display/display_panel_test.py`, `test_z2w_lidar_layout.py` | HUB75 bring-up and dashboard layout checks |
| Sensors/input | `sensors/bn880_test.py`, `sensors/hall_sensor_test.py`, `imu_yaw_test.py`, `controller/xbox_test.py` | GPS/compass, wheel speed, IMU, and controller checks |
| Navigation | `navigation/geojson_to_graph.py`, `navigation/astar_nav.py`, `navigation/generate_printable_map.py` | Route-graph generation, A* testing, and map output |
| Models | `evaluate_sidewalkpilot_models.py`, `test_series_4_common.py`, `test_jetson_series4_runtime.py`, `clip_bucket_analyzer.py` | Cross-model report, Series 4 contracts/runtime, and clip diagnosis |
| Setup | `setup/setup_and_verify.sh`, `install_usb_dashboard_link.sh` | Environment checks and USB dashboard link installation |

This is an inventory of available tools, not evidence that every utility passed
on the current hardware revision. Test records must preserve the command, device,
result, and date separately.

## Support assets

GeoJSON files, navigation graphs, the route-planner HTML, and
`house_stop_overrides.json` live under `code/test_files/navigation/`.
`mg24_yaw_firmware/` and `hsv_clahe_comparisons/` are checked-in supporting
subdirectories. Local generated caches or reports are not part of the published
repository merely because they appear in a working copy.

## Verification

```bash
cd /home/rsabavat/rc_car_code
python -m py_compile code/test_files/steering/pca9685_servo_test.py
bash -n code/test_files/setup/setup_and_verify.sh
```

Hardware-moving utilities require the car to be restrained, drive power managed,
and an independent way to cut power.

## Related pages

- [Runtime Modules](runtime-modules.md)
- [Training Modules](training-modules.md)
- [Bench Tests](../testing/bench-tests/overview.md)
