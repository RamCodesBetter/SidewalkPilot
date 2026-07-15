# Field Logs

Every controller run writes a timestamped CSV under `~/logs` by default. `LOG_INTERVAL_SEC = 0.1`, so the nominal logging rate is 10 Hz, plus shutdown handling.

The 46-column schema is defined by `CSV_HEADERS` in `config.py` and must remain aligned with `logging_utils.log_data_to_csv()`. It includes:

- Control and gear state;
- Steering, throttle, brake, motor PWM, and speed;
- LiDAR distances, clearance, AEB state, and stop reason;
- Camera/model confidence and steering fields;
- System utilization/temperature;
- Autonomy intervention fields; and
- The dashboard payload.

Logs are shipped to Jetson Orin Nano on clean shutdown when passwordless SSH and the link are available; transfer failure keeps the files locally.

## Review Rule

A CSV is stronger than memory but does not explain every physical event by itself. Pair it with the matching video, model version, route, lighting, AEB/IMU state, and intervention notes.
