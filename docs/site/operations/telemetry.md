# Telemetry and Observability

Where the numbers go: training metrics to Weights & Biases, durable driving telemetry to CSV, optional live driving telemetry to a local InfluxDB instance, and glanceable state to the Zero 2 W dashboard. These paths answer different questions and do not depend on one another.

## How It Works

The current system has four telemetry paths:

- **Training -> Weights & Biases.** Series 3/4 trainers log step and epoch telemetry to W&B. Six completed Series 4 runs cover the 4.0 and 4.1 PC, CF, and PCF comparisons.
- **Driving -> CSV.** The runtime writes one CSV log per launch under `~/logs` by default. `LOG_INTERVAL_SEC = 0.1`, so the nominal rate is 10 rows per second. The 46 columns are defined by `CSV_HEADERS` in `config.py`.
- **Driving -> optional local InfluxDB.** `InfluxLogger` is enabled only when `~/.influxdb.json` exists and contains a token. When enabled, the main loop queues measurements to a worker that writes to InfluxDB 2.x. When the file is absent or invalid, the logger prints that it is disabled and becomes a no-op.
- **Driving -> Zero 2 W dashboard.** The Raspberry Pi 5 sends latest-value UDP telemetry over the private USB Ethernet link. This view is real-time only and is not a durable log.

CSV is the primary local run record, but it still depends on successful process startup and disk writes. InfluxDB is optional and must not be cited as evidence for a run unless the startup log contains `[influx] logging run ...` and the expected points are present.

## Why It Matters

- Training and driving telemetry answer different questions and have different retention needs, so they use different backends. Mixing them would bury per-run driving signals under training noise.
- CSV logging does not require network connectivity and remains portable for later analysis.
- Optional InfluxDB writes are non-blocking: a full queue or failed write drops telemetry instead of stalling the 50 Hz control loop.
- CSV headers and row construction are kept in one checked-in schema. A completed file records sampled software state at nominal 10 Hz; it is not a hardware-synchronized ground-truth trace.

## Planned and Not Yet Final

- Autonomy field metrics such as interventions per distance have not yet been standardized. Do not quote them without a named CSV, route, model, and calculation method.
- Phone-facing training/system dashboards via Grafana Cloud are a later, intentionally under-built idea — not the current path.

## Related Pages

- [Offline Evaluation](../model-evaluation/offline-evaluation/overview.md)
- [Troubleshooting](troubleshooting.md)
- [Dashboard Sender](../runtime-code/dashboard/sender.md)
