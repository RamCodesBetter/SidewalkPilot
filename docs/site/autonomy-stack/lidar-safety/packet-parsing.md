# Packet Parsing

This page documents how the raw byte stream from the LiDAR is turned into distance points.
The parser lives in `code/controller/current/rc_car_app/lidar.py` (class
`LidarParser`) and runs on its own daemon thread, keeping normal serial reads and
reconnect attempts outside the main control loop.

## How it works

The LiDAR is a Youyeetoo FHL-LD19 read at `BAUD_RATE = 230400`. It emits fixed-length
frames of `PACKET_LENGTH = 47` bytes, each carrying `MEASUREMENT_POINTS_PER_PACKET = 12`
distance measurements. The reader thread (`_read_data_once`) does the following:

1. **Buffer and sync.** It appends whatever bytes are waiting on the serial port to an
   internal buffer, then searches for the frame header byte `0x54`. Any garbage before the
   header is discarded so the parser can re-sync after a dropped byte. The second byte must
   be `0x2C` (the LD19's length/type marker); if not, the parser advances one byte and
   retries.
2. **Unpack a frame.** From the 47-byte packet it reads the start angle and end angle (each
   a little-endian `uint16` in hundredths of a degree, so it divides by 100). If the end
   angle wraps below the start angle it adds 360 degrees so the interpolation stays
   monotonic.
3. **Interpolate 12 points.** The 36 data bytes between the angles are read three bytes at a
   time: a little-endian `uint16` distance in millimeters plus a one-byte confidence. Each
   point's angle is linearly interpolated across the packet's angular span
   (`angle_step = (end_angle - start_angle) / 11`), wrapped into 0–360 degrees. A point is
   marked `is_valid` only when its raw distance is non-zero.
4. **Assemble a full scan.** Points accumulate under a lock into `current_scan_points`. Once
   more than 500 points have been gathered (roughly a full revolution), the batch is
   promoted to `last_full_scan_points`, timestamped, and a fresh scan begins.

Each parsed point is a `LidarPoint(angle_deg, distance_mm, confidence)`. It can compute its
Cartesian `(x, y)` from polar coordinates on demand (`x = d·sin θ`, `y = d·cos θ`), which is
what the dashboard LiDAR view uses.

## Why this choice

Frame-header search lets the parser recover alignment after partial reads or stray bytes.
Publishing after more than 500 accumulated points gives downstream code a larger rolling
scan, but the point threshold alone does not prove uniform 360-degree coverage or sensor
health. Struct-unpacking errors on malformed packets are caught and logged rather than
propagated through that parsing step.

## Consumers

`get_latest_scan()` returns a copy of the most recent full scan, or an empty list if the
newest scan is older than `SCAN_STALE_SEC = 1.0` second — so stale data is treated as "no
scan," which is safer than acting on old readings. The runtime calls this once per loop and
feeds the points into `determine_turn_direction()` and the override side-picker.

## Key constants

| Constant | Value | Meaning |
|---|---|---|
| `BAUD_RATE` | 230400 | LD19 serial speed |
| `PACKET_LENGTH` | 47 | Bytes per frame |
| `MEASUREMENT_POINTS_PER_PACKET` | 12 | Points per frame |
| header / marker | `0x54` / `0x2C` | Frame start + length-type byte |
| `SCAN_STALE_SEC` | 1.0 | A scan older than this is dropped |

Confidence filtering (`confidence >= 150`) happens later, in the consumers, not in the
parser itself.

## Related pages

- `autonomy-stack/lidar-safety/object-clustering.md`
- `autonomy-stack/lidar-safety/clearance-and-heading-scoring.md`
- `autonomy-stack/lidar-safety/aeb.md`
