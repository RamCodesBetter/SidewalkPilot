# Logging Settings

This page documents the CSV logging constants in `code/controller/current/rc_car_app/config.py` and how `code/controller/current/rc_car_app/logging_utils.py` writes each row. "Logs" here means the runtime CSV files, not stdout prints.

## How it works

`config.py` builds the log path and the header list; `logging_utils.py` opens the file and writes one row per interval.

| Constant | Value | Meaning |
|---|---|---|
| `LOG_DIR` | `~/logs` by default, or `RC_CAR_LOG_DIR` | Directory the CSV is written to; created on import |
| `CSV_FILENAME` | `log_YYYYMMDD_HHMMSS.csv` | One file per run, timestamped at process start |
| `LOG_INTERVAL_SEC` | `0.1` | Nominal interval between rows (10 Hz) |
| `CSV_HEADERS` | 46-column list | Column order for the row writer |

`PROJECT_ROOT` is resolved relative to `config.py` (four levels up). `PHOTO_DIR` therefore defaults to the repository's `media/photos/`, while `LOG_DIR` independently defaults to `~/logs`; a service or shell can set `RC_CAR_LOG_DIR` to another location. Both directories are created with `os.makedirs(..., exist_ok=True)` at import. The filename is stamped once at startup with `datetime.now().strftime('%Y%m%d_%H%M%S')`, so restarting the car starts a new file.

`init_csv_logger()` opens the file in append mode and writes the header row only if the file is empty (`csv_file.tell() == 0`), then prints `CSV logging initialized: <path>`. `log_data_to_csv()` assembles one row from `state`, `metrics`, and the sampled `cpu_percent` / `memory_percent` / `cpu_temp`, writes it, and `flush()`es immediately so a crash or power cut keeps the last completed row. After writing, it clears the one-shot event flags (`event_shift_up`, `event_shift_down`, `event_cc_increase`, `event_cc_decrease`) so each button press logs exactly once.

The 46 columns cover timestamps, autonomy/cruise state, PRND and quit events, steer/brake/gas, speed (max recall, average, current, motor PWM), gear, cruise target, the four LiDAR distances plus determined direction, target heading, stop reason, CPU/memory/temperature, LiDAR point count, time since last hall pulse, AEB enabled/triggered, PID output, LiDAR best heading/confidence/forward clearance, and camera-analysis fields. Average speed is derived inside the writer from `metrics.total_distance_cm`, not stored in state.

## Why this choice

One timestamped file per run keeps field sessions separate and makes it easy to pull a single drive for analysis. The nominal 10 Hz interval and per-row `flush()` trade a little I/O for durability. CSV is the primary local run record when initialization and writes succeed; it is not guaranteed if the process cannot open or write the file. Deriving average speed and clearing event flags in the writer keeps the main loop from having to manage logging concerns.

## Failure symptom

If the file cannot be opened, `init_csv_logger()` prints `Error initializing CSV logger: ...` and returns `(None, None)`; `log_data_to_csv()` then no-ops because `csv_writer` is falsy, so the car keeps driving but produces no log. A per-row write failure prints `Error writing to CSV: ...` but does not stop the loop. If `CSV_HEADERS` and the row list in `logging_utils.py` ever drift out of sync, columns silently misalign — the two must be kept the same length and order.

## Related pages

- `runtime-code/runtime-loop.md`
- `code-reference/runtime-modules.md`
- `testing/bench-tests/overview.md`
