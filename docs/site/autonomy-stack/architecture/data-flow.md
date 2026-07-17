# Control Architecture and Runtime Data Flow

SidewalkPilot separates AI inference, hardware ownership, display, and safety so network or
inference waits cannot directly stall actuator control. The Jetson Orin Nano is the AI brain;
the Raspberry Pi 5 turns its fresh predictions into safety-checked physical commands.

<figure class="project-diagram">
  <div class="project-diagram__viewport">
    <a href="../../../assets/diagrams/runtime-control.svg">
      <img src="../../../assets/diagrams/runtime-control.svg" alt="SidewalkPilot runtime and control flow, showing parallel inputs, Raspberry Pi 5 arbitration, separate steering and motor paths, and telemetry outputs">
    </a>
  </div>
  <figcaption>
    Runtime and control flow. Open the <a href="../../../assets/diagrams/runtime-control.svg">full-size SVG</a>
    or the <a href="../../../assets/diagrams/runtime-control.drawio">editable draw.io source</a>.
  </figcaption>
</figure>

## Jetson Orin Nano: AI Brain

Jetson Orin Nano receives the newest camera frame and requested model version over the private
Ethernet link at `10.42.0.2:8770`. It runs the current Series 3/4 model on the GPU and returns
steering, unused model throttle, temperatures, inference timing, and nine hybrid-bucket
probabilities. Current v3.4 and Series 4 autonomous steering require a fresh result from this
path. The Jetson Orin Nano does not command GPIO directly.

## Raspberry Pi 5: Hardware and Safety Controller

The Raspberry Pi 5 is the only computer that writes steering, motor, and brake hardware. It
reads the Xbox controller, sensors, and latest Jetson Orin Nano result, then applies gear, manual
takeover, AEB, model freshness, yaw correction, and servo limits.

## Zero 2 W

The Zero 2 W receives JSON telemetry at `192.168.10.2:8765` over USB Ethernet and renders the HUB75 panel. Dashboard failure does not stop the Raspberry Pi 5 control loop. Linked shutdown is explicit application behavior, not control authority.

## Safety Arbitration

1. Quit/manual takeover and gear state define whether motion is permitted.
2. Servo/model freshness faults can stop motion.
3. With AEB enabled, center-corridor emergency occupancy hard-brakes.
4. LiDAR slowdown caps requested forward throttle.
5. Camera/Jetson Orin Nano provides autonomous steering only.
6. Manual or autonomous throttle reaches motor mapping only after these gates.

LiDAR does not select a path or output steering. Side returns are telemetry because empty space beside an obstacle is not proof of sidewalk.

## Timing Boundary

Camera, LiDAR, GPS, IMU, Jetson Orin Nano transport, dashboard transport, photo writes, and
telemetry use background workers. Each worker keeps its latest available result in memory,
and the 60 Hz runtime loop reads those values without waiting for the device or network.
See [Runtime Loop](../../runtime-code/runtime-loop.md) for ownership and stall diagnostics.

## Runtime States

The final command depends on several independent states:

| State | Values and behavior |
|---|---|
| Gear | `P` applies brake, `R` allows manual reverse without the forward LiDAR rule, `N` commands no motor output, and `D` permits forward manual, cruise, or autonomous control |
| Drive mode | `MAN` for manual, `CC` for cruise control, and `ATO` for camera autonomy |
| Model | The selected version can change at runtime; autonomous control requires a fresh result from that same version |
| LiDAR/AEB | Independent toggle that can cap or stop forward motion in manual or autonomous Drive |
| Navigation | Route segments request `AUTO` on sidewalks and `MNUL` at crossings, while the operator remains responsible for takeover |

The former LiDAR steering mode is gone. LiDAR state is represented by center clearance, throttle cap, emergency state, AEB state, and dashboard alerts rather than a second steering command. Series 4 history resets on model changes, reconnects, and other discontinuities.

## Failure Boundaries

| Failure | Current response | Important limit |
|---|---|---|
| Jetson Orin Nano unavailable, stale, or wrong model | Reject autonomous result and request a stop | Manual control still depends on a healthy Raspberry Pi 5 process and controller path |
| LiDAR serial disconnect or stale scan | Retry in a background thread and expose missing telemetry | Missing returns are not proof of a clear path; LiDAR loss is not fail-closed |
| Center obstacle at or inside 1.05 m with AEB enabled | Zero throttle and request full braking in forward drive | Stopping distance depends on speed, payload, surface, power, and sensor coverage |
| Servo write fault | Force braking and zero throttle | Requires the write path to detect the fault |
| Dashboard link failure | Keep the driving loop running and show link failure when the receiver is alive | The operator loses dashboard observability |
| Human takeover or quit | Cancel autonomy or begin shutdown | No worst-case end-to-end takeover latency is claimed |

Sensor health is therefore an operating gate. In particular, a reconnecting LiDAR reader keeps the control loop responsive but does not preserve obstacle coverage while scans are absent.
