# Build Timeline

This timeline is organized by engineering phase because many early experiments were iterative rather than formal releases. Dates are included only where the project record supports them.

## Phase 1: Build A Driveable Research Car

The project began by turning an Ackermann-steering RC chassis into a software-controlled platform. The Raspberry Pi took ownership of motor direction, PWM throttle, PCA9685 servo control, camera capture, controller input, and cleanup.

This phase established the non-negotiable baseline: manual driving had to remain available while every later autonomy feature was added.

## Phase 2: Learn Steering From Images

Series 1 created the first end-to-end image-to-steering pipeline. A compact CNN accepted 200x66 images and regressed a steering command. Field photos and their steering corrections became the training source, and regular plus `b` checkpoints began to preserve final-epoch and best-validation behavior separately.

The achievement was not a perfect model. It was proving the complete loop from human driving, to labels, to GPU training, to a physical autonomous run.

## Phase 3: Refine Data And Preprocessing

Series 2 retained direct steering regression while exploring cleaner data, corrections, steering ranges, and lighting preprocessing. HSV/CLAHE variants tested whether fixed contrast enhancement could protect the model from difficult exposure.

The lesson was that preprocessing can help one condition while changing useful visual cues elsewhere. Raw imagery plus training-time augmentation remained important.

## Phase 4: Split The Work Across Three Computers

The system grew into three managers:

- the Raspberry Pi 5 for hardware and final control;
- the Jetson Orin Nano for model inference;
- the Zero 2 W for the external dashboard.

Dedicated Ethernet kept Jetson inference offline. A USB network carried dashboard telemetry. This split made the architecture more capable, but it also introduced real transport, boot-order, service, and stale-data problems that had to be engineered rather than assumed away.

## Phase 5: Series 3 And The Shadow Problem

Series 3 increased input resolution to 320x180 and roughly doubled model capacity. v3.0 retained a simpler output contract. v3.1 and later introduced the 19-value hybrid head so the model could choose a coarse steering class before predicting a class-local offset.

Harsh diagonal tree shadows became the defining failure. Earlier models sometimes followed a dark shadow edge as if it were the edge of the sidewalk. The training pipeline added stronger lighting and synthetic-shadow augmentation, while evaluation expanded beyond mean error to balanced nine-class and turn metrics.

## Phase 6: Steering Mechanics And Calibration

Physical steering did not behave like an ideal 0-to-180-degree mechanism. The chassis showed asymmetric return behavior, load effects, and hysteresis. Bench tools stepped the servo through known commands; controller-driven trim tools exposed center offsets; wheel geometry was plotted and fitted to compare left and right behavior.

The project separated **absolute servo commands**, which describe what hardware receives, from **reference steering values**, which preserve a clean 0-to-180 model and display convention. Current runtime calibration uses a `+12D` center trim.

## Phase 7: LiDAR From Detection To Bounded Braking

LiDAR integration went through USB disconnects, UART experiments, motor-enable wiring, packet parsing, and dashboard visualization. A multi-lane swerve-through design was implemented and then removed.

The removal was a safety decision. Obstacle points alone do not reveal the safe sidewalk boundary, so choosing left or right could steer into grass, a curb, or an unseen object. The current system uses one center corridor and only changes longitudinal motion: clear, slow, hold, or emergency brake.

## Phase 8: Make The Dashboard Link Recoverable

The Zero 2 W dashboard experienced boot-order problems, `NO LINK` states, damaged-port enumeration failures, and intermittent USB networking. Permanent NetworkManager profiles and a USB link-keeper service were added on both computers. The production design now uses USB-only telemetry at fixed `192.168.10.1/24` and `192.168.10.2/24` addresses, with no Wi-Fi fallback.

The dashboard was simplified to one Waveshare 64x32 HUB75 display. Obsolete MAX7219 and photo-count pages were removed from the current runtime and documentation.

## July 13, 2026: v3.4 Field Selection

Four recent models were compared on the physical car in shadow cases and normal left/right turns:

- v3.4 completed every shadow case presented and ranked first;
- v3.4b was slightly worse;
- v3.3 was worse than v3.2;
- v3.3b was much worse than v3.2b.

The exact route, weather, takeover count, and clip identifiers were not preserved in the test record, so this remains an honest qualitative field verdict rather than a fully instrumented benchmark.

## July 14, 2026: Remove Powered-Off-Jetson Lag

Manual steering and the dashboard had been running smoothly for several seconds, pausing briefly, then resuming. A direct controller test was instantaneous, which ruled out Bluetooth as the main cause.

The runtime audit found blocking work in the control path, especially repeated network waits to an offline Jetson, photo-directory scans, and temperature subprocesses. Jetson communication moved to a background worker with latest-frame semantics; dashboard sending remained asynchronous; recurring file and subprocess work left the loop. Physical testing with the Jetson powered off confirmed that the delay was gone.

## Next Phase: Series 4 Research

Series 4 is still a design study. The current question is whether a causal history of steering commands, paired with the image, can improve temporal consistency without leaking future information into runtime inputs. No Series 4 model has been trained or promoted.

The current production state is maintained in [Current Status](current-status.md).
