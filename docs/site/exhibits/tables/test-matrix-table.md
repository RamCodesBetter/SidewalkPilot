# Test Matrix Table

This page maps SidewalkPilot subsystems to available bench utilities. The matrix is an inventory, not proof that every test passed on the current hardware revision; dated outputs or field records provide that evidence.

All paths below are relative to `code/test_files/` and include their subsystem folder where applicable.

## Test Matrix

| Subsystem | Utility | What it verifies | Hardware touched |
|---|---|---|---|
| Steering | `steering/pca9685_servo_test.py` | PCA9685 drives the steering servo | Servo, PCA9685 |
| Steering | `steering/calibrate_servo.py` | Center/endpoint calibration | Servo |
| Steering | `steering/model_steering_test.py` | Model-to-steering bench response | Camera, model, optionally servo |
| LiDAR | `lidar/lidar_viewer.py` | Live scan visualization and point stream | FHL-LD19 LiDAR |
| LiDAR policy | `test_lidar_center_aeb.py` | Center-corridor slowdown/stop policy | none in unit-test mode |
| Camera | `camera/test_camera_preview.py` | Picamera2 capture/preview | RPi Camera Module 3 Wide |
| Camera | `camera/test_camera_flip.py` | Mounted orientation | Camera |
| Display | `display/hub75_rgbmatrix_test.py` | HUB75 panel bring-up | Waveshare LED matrix |
| Display policy | `test_z2w_lidar_layout.py` | Dashboard LiDAR layout rendering | none in layout-test mode |
| Sensors | `sensors/bn880_test.py` | BN880 GPS and compass reads | GPS/compass |
| Sensors | `sensors/hall_sensor_test.py` | Hall speed pulses | Hall sensor |
| IMU | `imu_yaw_test.py` | Yaw axis/sign/filter output | XIAO MG24 Sense |
| Controller | `controller/xbox_test.py` | Xbox axes/buttons through pygame | Xbox controller |
| Navigation | `navigation/geojson_to_graph.py` | Build a route graph from GeoJSON | none |
| Navigation | `navigation/astar_nav.py` | A* pathfinding over a graph | none |
| Models | `evaluate_sidewalkpilot_models.py` | Common 46-checkpoint JSON/PDF evaluation | evaluation GPU |
| Series 4 | `test_series_4_common.py`, `test_jetson_series4_runtime.py` | Temporal contracts and runtime decoding | CPU/CUDA depending on invocation |
| Setup | `setup/setup_and_verify.sh` | Environment checks | depends on selected checks |

## Verification Standard

Each utility isolates one subsystem, prints observable output, and touches only the hardware it names. For any motion test, restrain or lift the wheels first and keep the controller ready for immediate takeover.

| Class of test | Passing signal | Safety gate |
|---|---|---|
| Servo / steering | Servo reaches commanded angle; center matches 90 deg logical | Wheels off ground for range tests |
| LiDAR | Non-zero point count, plausible clearances | Car service stopped to avoid two readers |
| Camera | Frame captured at expected resolution/orientation | none |
| Motion (autonomous) | Correct steering/throttle response to scene | Typed `go` + kill switch required |
| Display / sensors | Expected pattern / plausible reading | none |

## Coverage Notes

| Area | Status |
|---|---|
| Per-subsystem bench utilities | Present for steering, LiDAR, camera, display, sensors, controller, navigation, data |
| IMU yaw-rate steering | Firmware, verifier, reader, and live `straight`-mode controller implemented; controlled field validation still required |
| Series 3 INT8/TensorRT throughput test on Jon | Planned / not-yet-measured |
| End-to-end field autonomy metrics from CSV logs | Planned (compute from runtime CSV logs, store on Jon) |

## Related pages

- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
