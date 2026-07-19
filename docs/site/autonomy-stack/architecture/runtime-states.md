# Runtime States

The current runtime combines gear, drive mode, navigation state, AEB state, and selected model state.

## Gear

- `P`: throttle zero, brake applied.
- `R`: manual reverse; the forward AEB stop rule is excluded.
- `N`: motor command zero without the Park brake state.
- `D`: manual, cruise-control, or autonomous forward operation.

## Drive Mode

`get_dashboard_drive_mode()` reports:

- `ATO` when autonomous mode is active;
- `CC` when cruise control is active; and
- `MAN` otherwise.

The former `LDR` steering-override mode is not part of the current arbitration because LiDAR no longer changes steering. LiDAR state is instead visible through its throttle cap, center occupancy, emergency flag, AEB status, and alerts.

## Model and Safety State

The selected steering version can change from the dashboard. A model change invalidates prior inference results; PC/PCF requests carry the Raspberry Pi 5 client's latest three target values. Autonomous control requires a fresh result for the selected version. LiDAR/AEB is an independent toggle and, when enabled, can cap forward throttle or request braking in either manual or autonomous Drive.

Navigation can still request automatic or manual route segments, but the operator remains responsible for road crossings and immediate takeover.
