# Failure Table

This page catalogs recorded field or bench symptoms and the project's current response. A symptom does not automatically establish one root cause, so the table separates observations from hypotheses where the available record is incomplete.

Failures are grouped by subsystem. "Implemented" means the code or hardware change exists; it does not by itself mean that a controlled field comparison proved the change solved every case.

## Model / Steering Failures

| Failure | Recorded symptom | Supported interpretation | Response / status |
|---|---|---|---|
| Near-center collapse | Some checkpoints predict near center across many inputs and miss turns | Straight-heavy labels and aggregate MAE can reward this behavior; no single cause is established for every checkpoint | Rank with Bal9, turn recall, confusion matrices, signed error, and field tests rather than MAE alone |
| Abrupt steering changes | Some model outputs or physical commands change in visibly discrete steps | Class-head transitions, temporal instability, mechanics, and command filtering are separate possible contributors | Runtime applies latest-result smoothing; Series 4 tests temporal targets/history. Neither change has a controlled physical smoothness result yet |
| Orange-light false steer | A historical field note records v3.1b steering incorrectly near an orange lamp at night | Lighting/color shift is a hypothesis consistent with the scene, not a proven sole cause | Night remains outside the current operating envelope; collect matched data before claiming a correction |
| Turn-vs-shadow observation | Some turn-eager checkpoints followed shadows; center-biased behavior missed turns | The combined turn-and-shadow condition was underrepresented in the reviewed data | v3.4 passed the July 13 shadow cases presented; more preserved route-level testing is still required |

## LiDAR / AEB Failures

| Failure | Recorded symptom | Supported interpretation | Response / status |
|---|---|---|---|
| LiDAR reads NONE / 000 | No scan points, so LiDAR cannot detect a center-corridor obstacle | Possible causes include wrong device/baud, a stopped scanner, disconnect, or another process owning the serial device | Check the CP2102 `/dev/ttyUSB0` path and 230400 baud; stop the car service before a raw serial test |
| Two serial readers | Garbage / dropped LiDAR frames | Raw test opened the port while the car service was also reading | Stop `sidewalkpilot-rpi-car.service` before any raw serial test |
| Transport moved | An old UART path no longer matched the attached sensor | LiDAR moved from GPIO UART (`/dev/ttyAMA2`) to USB CP2102 (`/dev/ttyUSB0`) | Runtime resolves the CP2102 by-id path in `lidar.py` and retries after disconnects; missing data is currently fail-open with respect to AEB |

LiDAR is a Youyeetoo FHL-LD19 at 230400 baud used for AEB, which arbitrates over the model.

## Sensor / Wiring Failures

| Failure | Recorded symptom | Supported interpretation | Response / status |
|---|---|---|---|
| GPS permission denied | Cannot open `/dev/ttyAMA0` | Serial console held the UART / group membership | Free the console on `ttyAMA0`; do not confuse GPS (`ttyAMA0`) with LiDAR |
| Left drift while centered | Car pulls left at speed with steering at 90 | Motor balance, linkage geometry, trim, payload, and surface are unresolved contributors | Keep motor scales, servo mapping, and IMU yaw correction separate; isolate one variable at a time |
| Direction-dependent steering return | Wheels do not return to the same physical center | Linkage, servo return, load, surface, and trim remain possible contributors | Observed with test utilities; IMU yaw-rate correction is implemented, but a controlled before/after field result is still needed |

## Dashboard / USB-Link Failures

| Failure | Recorded symptom | Supported interpretation | Response / status |
|---|---|---|---|
| `NO LINK` on display | Zero receiver alive but no recent packets | USB Ethernet ARP/carrier issue or car not sending | Check `usb0` carrier + ping both ways; keeper service recovers ARP |
| Carrier up but ping fails | `carrier=1`, ping/ARP still fail | Stale ARP on the USB gadget link | Restart keeper / run the documented USB hard reset |
| Wrong dashboard page rendered | Display shows the wrong page/field | A page/constant hardcoded as a literal in the packet serializer | Thread the constant through ALL layers (runtime -> `hub75_dashboard.py` -> `z2w_dashboard.py`); import, don't hardcode |
| USB enumerate fail (-110 / -62) | Zero will not enumerate over USB | The recorded failures were consistent with power/USB-link instability; the error code alone does not prove one cause | Use the working USB port and known power arrangement, then verify enumeration, carrier, ARP, and ping in order |

The "wrong page" case is a documented incident that cost ~2.5 hours: the real cause was a hardcoded literal in the serializer, found only by grepping the constant across every file. The lesson recorded here is to grep the value across all layers first, and prove rather than assume.

## Related pages

- `portfolio-evidence/claims-and-proof/reproducibility-claim.md`
- `publishing/reports.md`
- `exhibits/tables/test-matrix-table.md`
