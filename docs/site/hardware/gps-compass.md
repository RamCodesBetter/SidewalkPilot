# GPS / Compass Hardware

The BN880 board combines a GPS receiver with an HMC5883L-compatible magnetometer. The
current navigation runtime consumes GPS fixes from the UART. Compass reading is available
in a separate bench utility but is not integrated into the live route manager, so the docs
do not claim live compass-based heading control.

## Parts (Amazon)

- [BN880 GPS Module with HMC5883L](https://www.amazon.com/Geekstory-Navigation-Raspberry-Aircraft-Controller/dp/B078Y6323W/ref=sr_1_1?crid=11E0TMTZNTPEW&dib=eyJ2IjoiMSJ9.lSbdcLk7wwVdqd53Tw4NBuhT5XOMygBLYjY5jVspVPybtMQnA99WVMzlC8_j1CsvxaRKx9XgN4b5KhVveSR54WHJXFKDf-iSPapWIcQiyH9-y83yzg35qv0hw8mFAJUm77b6UdN6iObi31usEx_kxlhn1T4N6mwRMHrsJDZyzOC4VNrgW0DFn5dgvd_WWVI1Lj2s5GA4lpd3i1fh87ub_s61VfXUxDszRuTKBCONfbmSEGUbaNXu12K-tYs8_KeCrONdNbG_udvGQhSviQtwh0I2iYEQ8g5IoFeHLi-VTx0.msDaC2RQmowR-0TLZyxZ9b-i7OEqQv7YDCqyOlhrigg&dib_tag=se&keywords=bn880&qid=1779579754&s=electronics&sprefix=bn880%2Celectronics%2C188&sr=1-1&th=1) — $33.98

## How it works

- `navigation.py` opens the GPS on `/dev/ttyAMA0` at `9600` baud and reads NMEA sentences
  line by line (`GPS_PORT`, `GPS_BAUD`).
- Parsed fixes can be passed to the route manager and snapped to a graph vertex in
  `trossachs_nav_graph.json`. The A* planner routes over that graph and divides the route
  into AI and manual segments with crosswalk handoffs.
- `code/test_files/sensors/bn880_test.py` can read the magnetometer over I2C for bench verification.
  That test path is separate from `navigation.py`.

## Why this choice

- The BN880 packages GPS and compass hardware on one board, which keeps the physical sensor
  assembly compact even though the current runtime uses only the GPS path.
- UART at 9600 baud is the standard, low-overhead interface for NMEA GPS and does not
  compete with the higher-rate LiDAR or camera buses.

## Verify before a run

- Bench test: `code/test_files/sensors/bn880_test.py` reads the module and prints fixes and
  compass data.
- Failure symptoms: **permission denied on `/dev/ttyAMA0`** can mean the serial console,
  device permissions, or another process owns the port. Do not confuse this port with the
  LiDAR: GPS is `/dev/ttyAMA0`; the LiDAR uses a CP2102 UART-to-USB Adapter.

## Related pages

- `hardware/build-overview.md`
- `testing/bench-tests/overview.md`
- `runtime-code/hardware/hardware-class.md`
