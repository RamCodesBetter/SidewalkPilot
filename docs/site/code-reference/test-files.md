# Test Files

`code/test_files/` contains standalone bench, calibration, data, evaluation, and
setup utilities. Checked-in utilities are grouped by the subsystem or workflow they
exercise; the directory root contains folders rather than a second unsorted tool list.

## Main utilities

| Area | Checked-in files | Purpose |
|---|---|---|
| Steering | `steering/pca9685_servo_test.py`, `steering/calibrate_servo.py`, `steering/steering_trim_tuner.py`, `steering/servo_step_controller.py`, `steering/ff_calibrate.py`, `steering/imu_steering_calibrate.py`, `steering/pid_autotune.py` | Servo motion, centering, feed-forward measurement, IMU steering calibration, and yaw-control tuning |
| LiDAR | `lidar/lidar_viewer.py`, `lidar/lidar_uart_test.py`, `lidar/lidar_avoidance_sim.py`, `lidar/test_lidar_center_aeb.py` | Raw transport, visualization, policy simulation, and center-corridor tests |
| Camera | `camera/test_camera_preview.py`, `camera/test_camera_flip.py`, `camera/preview_series3_augmentations.py`, `camera/preview_shadow_augmentations.py` | Capture, orientation, and augmentation preview |
| Data and logs | `data/photo_run_to_dataset.py`, `data/check_dataset_frames.py`, `data/dataset_cosine_similarity.py`, `data/dataset_clusters.py`, `data/dataset_scene_tags.py`, `data/takeover_log_report.py` | Dataset assembly/audit, scene analysis, and CSV takeover reporting |
| Display | `display/hub75_rgbmatrix_test.py`, `display/display_panel_test.py`, `display/test_z2w_lidar_layout.py` | HUB75 bring-up and dashboard layout checks |
| Sensors | `sensors/bn880_test.py`, `sensors/hall_sensor_test.py`, `sensors/imu_yaw_test.py` | GPS/compass, wheel speed, and IMU stream checks |
| Controller | `controller/xbox_test.py`, `controller/joystick_velocity_test.py`, `controller/flick_detector_test.py`, `controller/test_async_jetson_client.py` | Input-device behavior and non-blocking Jetson Orin Nano client checks |
| Navigation | `navigation/geojson_to_graph.py`, `navigation/astar_nav.py`, `navigation/generate_printable_map.py` | Route-graph generation, A* testing, and map output |
| Models | `models/evaluate_sidewalkpilot_models.py`, `models/test_series_4_common.py`, `models/test_jetson_series4_runtime.py`, `models/clip_bucket_analyzer.py` | Cross-model report, Series 4 contracts/runtime, and clip diagnosis |
| Setup | `setup/setup_and_verify.sh`, `setup/install_usb_dashboard_link.sh` | Environment checks and USB dashboard link installation |

This is an inventory of available tools, not evidence that every utility passed
on the current hardware revision. Test records must preserve the command, device,
result, and date separately.

## Support assets

GeoJSON files, navigation graphs, the route-planner HTML, and
`house_stop_overrides.json` live under `code/test_files/navigation/`.
`mg24_yaw_firmware/` and `camera/hsv_clahe_comparisons/` are checked-in supporting
directories. Local generated caches or reports under `data/` are not part of the
published repository merely because they appear in a working copy.

## Verification

```bash
cd /home/rsabavat/rc_car_code
python -m py_compile code/test_files/steering/pca9685_servo_test.py
bash -n code/test_files/setup/setup_and_verify.sh
```

Hardware-moving utilities require the car to be restrained, drive power managed,
and an independent way to cut power.

## Related pages

- [Repository Reference](file-index.md)
- [Training Pipeline](../ai-and-models/training-pipeline/overview.md)
- [Bench Tests](../testing/bench-tests/overview.md)
