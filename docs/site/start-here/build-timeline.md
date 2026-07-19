# Build Timeline

This timeline is organized by engineering phase because many early experiments were iterative rather than formal releases. Exact dates are included only where the project record supports them.

## February-March 2025: Raspberry Pi Pico Alarm Clock

Before SidewalkPilot, I built an alarm clock around a Raspberry Pi Pico, bright RGB LEDs, a buzzer, and an RFID reader. The RFID card stayed in the bathroom, so silencing the 6:00 a.m. alarm required getting out of bed and scanning the card. Finding an Orange Pi in my dad's desk had first made me curious about single-board computers, and the Pico project gave me a smaller place to begin.

## April-July 2025: SidewalkPilot Begins

I started SidewalkPilot at the beginning of April 2025. I considered roads, curbs, and indoor robots before choosing sidewalks. Roads were unsafe for an RC-scale vehicle around full-size traffic. Curbs were narrow, visually ambiguous autonomy corridors. An indoor robot did not match the road-like "mini Tesla" project I wanted to build. Sidewalks offered repeated structure and a practical road-like autonomy problem at RC-car scale.

The first platform was much smaller and simpler than the current car. It used a Raspberry Pi 5, LiDAR, one motor controller, one small MAX7219 display, lights, indicators, a horn, and basic controls. The early software used a graphical interface before I replaced it with an Xbox controller. The first challenge was simply making the car drive reliably while preserving manual control as a fallback.

Without a dedicated Servo Controller, steering jittered and did not return reliably to straight. Adding the PCA9685 Servo Controller gave the steering servo a stable PWM source. LiDAR wall-following then became the first autonomous behavior and worked over approximately 2-3 meters. I removed it because the actual goal was camera-based self-driving, not following a wall.

By July 2025, the basic drivable car and its early autonomous-control foundation existed.

## August 2025-January 2026: Project Break

Development paused after the first platform. Work resumed in February 2026.

## February-March 2026: Hardware and Software Expansion

The project expanded to include camera capture, labeling, motor control, steering calibration, LiDAR processing, GPS and navigation work, telemetry, and safety behavior. The design also began growing from one small computer toward separate inference, control, and display roles.

Mechanical steering alignment and linkage slop became persistent problems. A physically misaligned steering mechanism delayed serious photo collection by roughly 2.5 weeks. During this broader development period, the car also completed an early approximately 0.5-mile physical autonomy run with five interventions, or roughly 0.1 miles per intervention. The exact date and complete run record were not preserved, so that result is historical context rather than a formal benchmark.

## April 2026: Learn Steering from Images

Series 1 created the first end-to-end image-to-steering pipeline. A compact CNN accepted 200x66 images and regressed a steering command. The Series 1/2 training dataset combined approximately 2,000-3,000 real field images with 50,000 CARLA-generated images from several randomized maps. Steering corrections supplied revised labels, while regular plus `b` models preserved final-epoch and validation-selected behavior separately.

The achievement was not a perfect model. It was proving the complete loop from human driving, to labels, to GPU training, to a physical autonomous run.

## Late April-May 2026: Refine Data and Preprocessing

Later Series 1 models and Series 2 retained direct steering regression while exploring cleaner data, corrections, steering ranges, and lighting preprocessing. HSV/CLAHE variants tested whether fixed contrast enhancement could protect the model from difficult exposure.

The lesson was that preprocessing can help one condition while changing useful visual cues elsewhere. Raw imagery plus training-time augmentation remained important.

## 2026: Split the Work Across Three Computers

The system grew into three managers:

- The Jetson Orin Nano for model inference;
- The Raspberry Pi 5 for hardware and final control;
- The Zero 2 W for the external dashboard.

Dedicated Ethernet kept Jetson Orin Nano inference offline. A USB network carried dashboard telemetry. This split made the architecture more capable, but it also introduced real transport, boot-order, service, and stale-data problems that had to be engineered rather than assumed away.

## 2026: Series 3 and the Shadow Problem

Series 3 increased input resolution to 320x180 and roughly doubled model capacity. v3.0 retained a simpler output contract. v3.1 and later introduced the 19-value hybrid head so the model could choose a coarse steering class before predicting a class-local offset.

Harsh diagonal tree shadows became the defining failure. Earlier models sometimes followed a dark shadow edge as if it were the edge of the sidewalk. The training pipeline added stronger lighting and synthetic-shadow augmentation, while evaluation expanded beyond mean error to balanced nine-class and turn metrics.

## 2026: Steering Mechanics and Calibration

Physical steering did not behave like an ideal 0-to-180-degree mechanism. The chassis showed asymmetric return behavior, load effects, and hysteresis. Bench tools stepped the servo through known commands; controller-driven trim tools exposed center offsets; wheel geometry was plotted and fitted to compare left and right behavior.

The project separated **logical steering targets**, which preserve a clean 0-to-180 model and display convention, from **calibrated physical servo commands**, which include the hardware mapping and trim. Current runtime calibration uses a `+17°` center trim.

## 2026: LiDAR from Detection to Bounded Braking

LiDAR integration went through USB disconnects, UART experiments, motor-enable wiring, packet parsing, and dashboard visualization. A multi-lane swerve-through design was implemented and then removed.

The removal was a safety decision. Obstacle points alone do not reveal the safe sidewalk boundary, so choosing left or right could steer into grass, a curb, or an unseen object. The current system uses one center corridor and only changes longitudinal motion: clear, slow, hold, or emergency brake.

## 2026: Make the Dashboard Link Recoverable

The Zero 2 W dashboard experienced boot-order problems, `NO LINK` states, damaged-port enumeration failures, and intermittent USB networking. Permanent NetworkManager profiles and a USB link-keeper service were added on both computers. The current design uses USB-only telemetry at fixed `192.168.10.1/24` and `192.168.10.2/24` addresses, with no Wi-Fi fallback.

The dashboard was simplified to one Waveshare 64x32 HUB75 display. Obsolete MAX7219 and photo-count pages were removed from the current runtime and documentation.

## July 13, 2026: v3.4 Field Selection

Four recent models were compared on the physical car in shadow cases and normal left and right turns:

- v3.4 completed every shadow case presented and ranked first;
- v3.4b was slightly worse;
- v3.3 was worse than v3.2;
- v3.3b was much worse than v3.2b.

The exact route, weather, takeover count, and clip identifiers were not preserved in the test record, so this remains an honest qualitative field verdict rather than a fully instrumented benchmark.

## July 14, 2026: Remove Powered-Off Jetson Orin Nano Lag

Manual steering and the dashboard had been running smoothly for several seconds, pausing briefly, then resuming. A direct controller test was instantaneous, which ruled out Bluetooth as the main cause.

The runtime audit found blocking work in the control path, especially repeated network waits to an offline Jetson Orin Nano, photo-directory scans, and temperature subprocesses. Jetson Orin Nano communication moved to a background worker with latest-frame semantics; dashboard sending remained asynchronous; recurring file and subprocess work left the loop. In one physical retest with the Jetson Orin Nano powered off, the previously observed periodic pauses were absent. A long-duration latency trace is still an evidence gap.

## July 14, 2026: Series 4 Temporal Experiments

The first Series 4 implementation compares three temporal contracts on the unchanged 81,237-image Series 3/4 dataset and the same deterministic split procedure:

- PC uses the image plus previous steering targets to predict the current target;
- CF uses the image to predict current and future targets;
- PCF combines previous-target inputs with current/future supervision.

The three 25-epoch W&B runs completed and produced six final/validation-selected models: `4.0p/4.0r`, `4.0f/4.0g`, and `4.0a/4.0c`. Each trainer exported a valid 320x180 ONNX graph. The live runtime was then extended to validate each model's signature, carry three causal steering targets in a versioned Raspberry Pi 5–Jetson Orin Nano request, and decode the current 18-value steering horizon.

All 46 checkpoints through Series 4.0 were re-evaluated on one frozen 6,952-frame Series 3/4 challenge subset. This common test made the offline comparison more informative than comparing each family on a different image distribution.

## July 2026: Series 4 Field Test and v4.1 Corrections

All six v4.0 models were driven. Image-only v4.0f was viable but mixed against v3.4, v4.0g was worse, and the PC/PCF models repeatedly echoed earlier steering predictions. v3.4 therefore remained the field-selected baseline.

The next three 25-epoch runs retained the PC, CF, and PCF contracts but changed the history representation, loss terms, history perturbations, and checkpoint selection to address that failure. They produced six v4.1 models. The common report was regenerated for all 52 checkpoints. The v4.1 models are evaluated offline but are not yet integrated into the live selector or physically tested.

The current deployed research state is maintained in [Current Status](current-status.md).
