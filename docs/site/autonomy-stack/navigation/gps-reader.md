# GPS Reader

The GPS reader is how SidewalkPilot knows where it is on the map. It reads the BN880
GPS module over serial and parses NMEA into a lat/lon fix that the navigation manager
uses to localize the car onto the graph. It is the `GpsReader` class in
`code/controller/current/rc_car_app/navigation.py`.

## How it works

- The BN880 is on `/dev/ttyAMA0` at `9600` baud (`GPS_PORT` / `GPS_BAUD`).
- `GpsReader.start()` spins up a **daemon background thread**, so the main control loop does
  not directly wait for each serial read. If `pyserial` is unavailable, GPS is disabled
  and navigation still runs (just without a fix).
- The thread reads lines and only parses ones starting with `$GPGGA` or `$GNGGA`.
  `parse_nmea_gga()` converts the NMEA degree-minute format to decimal degrees
  (handling S/W hemispheres as negative) and extracts fix status, satellite count,
  and altitude, stamping `updated_at`.
- Shared state (`lat`, `lon`, `fix`, `sats`, `alt`) is guarded by a `threading.Lock`;
  the runtime pulls a snapshot with `get_state()` each tick.
- The runtime feeds that state into `NavigationManager.update()`, which finds the
  nearest graph node (`nearest_node()`) and the closest point on the active path
  (`closest_path_index()`). It then calls `set_start_from_gps()` so a valid fix can update
  the route start rather than requiring a typed-in start.
- When a fix is invalid (`fix=False` or missing coords), `update()` passes `None` for
  lat/lon so downstream logic simply treats the car as un-localized rather than
  jumping to (0, 0).

## Why this choice

- A locked background thread is the standard way to read a slow 9600-baud serial
  device without stalling a real-time loop that also drives motors and steering.
- Filtering to GGA sentences keeps parsing simple and gives exactly the fields
  navigation needs (position, fix, satellites, altitude).
- Auto-filling the route start reduces operator entry when a valid fix and graph match are
  available; invalid or coarse fixes still limit localization.

## Known constraints / notes

- GPS shares the Raspberry Pi 5's UART budget; a past issue was the serial console holding
  `/dev/ttyAMA0`. The console must be freed for GPS to open the port (see the GPS
  reboot-survival work in the runtime notes).
- Consumer GPS accuracy is coarse relative to sidewalk width, so GPS is used for
  route-level localization and segment handoff, **not** for fine steering — that is
  the camera model's job.

## Related pages

- `autonomy-stack/navigation/compass-heading.md`
- `autonomy-stack/navigation/house-snapping.md`
- `hardware/gps-compass.md`
