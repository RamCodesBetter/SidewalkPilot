# Build Timeline

This timeline is organized by engineering phase because many early experiments were iterative rather than formal releases. The project began in early April 2025 after a smaller Raspberry Pi Pico project. Exact dates are included only where the project record supports them.

## Phase 1: Build a Drivable Research Car

The project began by turning an Ackermann-steering RC chassis into a software-controlled platform. The Raspberry Pi 5 took ownership of motor direction, PWM throttle, PCA9685 servo control, camera capture, controller input, and cleanup.

This phase established the non-negotiable baseline: manual driving had to remain available while every later autonomy feature was added.

## Phase 2: Learn Steering from Images

Series 1 created the first end-to-end image-to-steering pipeline. A compact CNN accepted 200x66 images and regressed a steering command. Field photos and their steering corrections became the training source, and regular plus `b` checkpoints began to preserve final-epoch and best-validation behavior separately.

The achievement was not a perfect model. It was proving the complete loop from human driving, to labels, to GPU training, to a physical autonomous run.

## Phase 3: Refine Data and Preprocessing

Series 2 retained direct steering regression while exploring cleaner data, corrections, steering ranges, and lighting preprocessing. HSV/CLAHE variants tested whether fixed contrast enhancement could protect the model from difficult exposure.

The lesson was that preprocessing can help one condition while changing useful visual cues elsewhere. Raw imagery plus training-time augmentation remained important.

## Phase 4: Split the Work Across Three Computers

The system grew into three managers:

- The Jetson Orin Nano for model inference;
- The Raspberry Pi 5 for hardware and final control;
- The Zero 2 W for the external dashboard.

Dedicated Ethernet kept Jetson Orin Nano inference offline. A USB network carried dashboard telemetry. This split made the architecture more capable, but it also introduced real transport, boot-order, service, and stale-data problems that had to be engineered rather than assumed away.

## Phase 5: Series 3 and the Shadow Problem

Series 3 increased input resolution to 320x180 and roughly doubled model capacity. v3.0 retained a simpler output contract. v3.1 and later introduced the 19-value hybrid head so the model could choose a coarse steering class before predicting a class-local offset.

Harsh diagonal tree shadows became the defining failure. Earlier models sometimes followed a dark shadow edge as if it were the edge of the sidewalk. The training pipeline added stronger lighting and synthetic-shadow augmentation, while evaluation expanded beyond mean error to balanced nine-class and turn metrics.

## Phase 6: Steering Mechanics and Calibration

Physical steering did not behave like an ideal 0-to-180-degree mechanism. The chassis showed asymmetric return behavior, load effects, and hysteresis. Bench tools stepped the servo through known commands; controller-driven trim tools exposed center offsets; wheel geometry was plotted and fitted to compare left and right behavior.

The project separated **absolute servo commands**, which describe what hardware receives, from **reference steering values**, which preserve a clean 0-to-180 model and display convention. Current runtime calibration uses a `+12D` center trim.

## Phase 7: LiDAR from Detection to Bounded Braking

LiDAR integration went through USB disconnects, UART experiments, motor-enable wiring, packet parsing, and dashboard visualization. A multi-lane swerve-through design was implemented and then removed.

The removal was a safety decision. Obstacle points alone do not reveal the safe sidewalk boundary, so choosing left or right could steer into grass, a curb, or an unseen object. The current system uses one center corridor and only changes longitudinal motion: clear, slow, hold, or emergency brake.

## Phase 8: Make the Dashboard Link Recoverable

The Zero 2 W dashboard experienced boot-order problems, `NO LINK` states, damaged-port enumeration failures, and intermittent USB networking. Permanent NetworkManager profiles and a USB link-keeper service were added on both computers. The current design uses USB-only telemetry at fixed `192.168.10.1/24` and `192.168.10.2/24` addresses, with no Wi-Fi fallback.

The dashboard was simplified to one Waveshare 64x32 HUB75 display. Obsolete MAX7219 and photo-count pages were removed from the current runtime and documentation.

## July 13, 2026: v3.4 Field Selection

Four recent models were compared on the physical car in shadow cases and normal left/right turns:

- v3.4 completed every shadow case presented and ranked first;
- v3.4b was slightly worse;
- v3.3 was worse than v3.2;
- v3.3b was much worse than v3.2b.

The exact route, weather, takeover count, and clip identifiers were not preserved in the test record, so this remains an honest qualitative field verdict rather than a fully instrumented benchmark.

## July 14, 2026: Remove Powered-Off Jetson Orin Nano Lag

Manual steering and the dashboard had been running smoothly for several seconds, pausing briefly, then resuming. A direct controller test was instantaneous, which ruled out Bluetooth as the main cause.

The runtime audit found blocking work in the control path, especially repeated network waits to an offline Jetson Orin Nano, photo-directory scans, and temperature subprocesses. Jetson Orin Nano communication moved to a background worker with latest-frame semantics; dashboard sending remained asynchronous; recurring file and subprocess work left the loop. In one physical retest with the Jetson Orin Nano powered off, the previously observed periodic pauses were absent. A long-duration latency trace is still an evidence gap.

## July 14, 2026: Series 4 Temporal Experiments

The first Series 4 implementation compares three temporal contracts on the unchanged 81,237-image Series 3 dataset and the same deterministic split procedure:

- PC uses the image plus previous steering targets to predict the current target;
- CF uses the image to predict current and future targets;
- PCF combines previous-target inputs with current/future supervision.

The three 25-epoch W&B runs completed and produced six final/best artifacts: `4.0p/4.0r`, `4.0f/4.0g`, and `4.0a/4.0c`. Each trainer exported a valid 320x180 ONNX graph. The live Jetson Orin Nano server was then extended to inspect each model's signature, maintain causal history for PC/PCF, decode 18-value steering horizons, and preserve the existing Raspberry Pi 5–Jetson Orin Nano wire protocol.

All 46 Series 1 through Series 4 checkpoints were re-evaluated on one frozen 6,952-frame Series 3/4 challenge subset. This common test makes the offline comparison more informative than comparing each family on a different image distribution. Series 4 remains experimental until physical-car testing; v3.4 remains the field-selected baseline.

The current deployed research state is maintained in [Current Status](current-status.md).
