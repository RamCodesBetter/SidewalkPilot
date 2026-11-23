#set page(paper: "us-letter", margin: 0.8in, footer: context [SidewalkPilot / code defense #h(1fr) #counter(page).display()])
#set text(size: 11pt)
#set par(leading: 0.65em)
#let q(t) = block(inset: 8pt, width: 100%, fill: rgb("#eef4f1"))[*Defend this:* #t]
#let chapter(n,t) = { text(size: 10pt, fill: rgb("#27604e"), weight: "bold", n); v(4pt); text(size: 23pt, weight: "bold", t); v(8pt) }
#chapter("01 / BEFORE THE PAPER", "Start with a claim you could disprove")
This is a workbook for explaining code you can inspect, not a judge's script. Start with chapters 2–5 before writing Methods or Results; use chapters 6–7 for the robot and oral defense. The existing 5.C math guide is the longer derivation companion. Study snapshot: Series 5 commit #raw("4211a96").

#q[Your paper says the network measures accessibility. Which exact output is in centimeters?]
*Answer check:* None of the two mask logits is in centimeters. C/E predict a pixel class. Width needs calibrated geometry, a physical definition of clear space and matched reference measurements. Cost savings need timed, comparable surveys. Never present the research plan as an observed result.

*Paper evidence ledger.* For each numerical claim, record: definition and units; dataset/split; exact metric code; artifact and checkpoint; important limitation. For example, “validation sidewalk IoU against SAM 3 masks” and “width MAE against a laser” have different targets, denominators and units. Never substitute one for the other.

*Protocol while we code.* Before a consequential edit: predict the tensor shape, safety branch or failure. After: inspect one function, run one discriminating test, explain what the observation rules out. Label what you designed, what AI implemented, and what you personally verified. Keep one unanswered question; do not interrupt every small edit with a quiz.

*Exit test:* Draw two paths from memory: photo → logits → mask; photo + calibration + metric reference → width error. Mark each arrow implemented, tested, or only proposed. Back each “tested” arrow with an artifact.

#pagebreak()
#chapter("02 / LABELS AND SPLITS", "Why two prompts can agree and still be wrong")
#q[Both prompts agree at approximately 99.8%. Why can the saved mask still miss most of the relevant continuation? What code would you inspect before lowering a threshold?]
Read #raw("run_single_corridor_campaign.py") (Detector.predict and instance), #raw("pseudo_mask_filter.py") (filter_masks), then #raw("campaign10k.py") (build and allocate), under Series 5 tools.

*Trace:* RGB photo → image features reused across text prompts → instance proposals → confidence and near-camera selection → prompt agreement → intersection and boundary trimming → indexed PNG. The near slab can be one connected region with a convincing score. Agreement is between two model outputs, not agreement with the physical sidewalk. Comparing raw proposals with the saved mask distinguishes missing proposals from bad selection or trimming.

*Specific evidence:* Review frame 6: the near slab passed; a broader fallback proposal existed but scored about 0.461, below the 0.55 selection cutoff. This is evidence about one frame, not a justification for expanding every mask. The original targets for 1, 3 and 6 remained in training by student decision. Label 255 is unknown, not a third class. SHA-256 establishes file identity, not annotation quality.

*Split challenge:* Why can different JPEG hashes leak information? Two neighboring frames may differ by a few pixels. C/E group neighboring accepted frames from one run within 0.5 s or perceptual hash distances at most four bits, transitively. Even A similar to B and B similar to C can bind A to C. Whole groups are assigned to exact sizes, not split to meet a quota. All 30 inspected frames are in training. Both holdouts still come from the same July 2 collection; this does not prove generalization to a different neighborhood.

*Do:* Locate one ID in the campaign and its assigned partition. Explain why 8,000 + 1,000 + 1,000 is the cohort size, not 10,000 human-verified labels. The final 1,000 must not guide checkpoint or threshold selection.

#pagebreak()
#chapter("03 / ARCHITECTURE", "Trace one tensor through ConvNeXt and U-Net")
#q[Why does a 1 × 1 convolution have 66 parameters here? If the input height is 540, why would doubling a decoder feature height fail at one skip connection?]
Read #raw("tools/models/convnext_tiny_unet.py"): ConvNeXtEncoder.forward, SkipBlock.forward, UNetDecoder.forward. Predict these shapes before looking:

#table(columns: (2fr, 1fr, 2fr), inset: 4pt,
[*Stage*],[*Channels*],[*Height × width*],
[RGB / PyTorch NCHW],[3],[540 × 960],
[Encoder skips, strides 4 and 8],[96; 192],[135 × 240; 67 × 120],
[Encoder skips, strides 16 and 32],[384; 768],[33 × 60; 16 × 30],
[Bottleneck],[256],[16 × 30],
[Decoder fusion outputs],[128; 64; 32],[33 × 60; 67 × 120; 135 × 240],
[Head; resized scores],[2; 2],[135 × 240; 540 × 960])

*Answer check:* A skip supplies higher-resolution features that contain localization information discarded by downsampling. The decoder resizes to the actual skip dimensions (16 doubled is 32, not 33), projects skip channels, concatenates along channels, then fuses with convolutions, GroupNorm and GELU. Concatenating is not adding. The head learns a separate weighted sum of 32 features for each of two classes, plus two biases: $2 times 32+2=66$. The same parameters are reused everywhere. A 1 × 1 head does not mean its features only saw one input pixel.

*Follow-up:* What if you resized class IDs bilinearly? Class IDs are categories, not continuous measurements. Use nearest neighbor for target masks; interpolate continuous scores before argmax for prediction. The network returns the tensor under the dictionary key #raw("out"), not a PNG. Encoding a decided mask as runs is lossless for IDs, not for original scores.

*Do:* Run #raw("trace_lab.py") on CPU. First draw the expected shapes for a 65 × 97 synthetic input. Predict whether the decoder will return 64 × 96 or 65 × 97, and find the line that settles it.

#pagebreak()
#chapter("04 / OPTIMIZATION", "Trace a gradient, not just a loss curve")
#q[A pixel marked 255 has zero direct loss. Can it still affect a weight update? Can a frozen encoder still change the decoder's weights?]
Read #raw("segmentation_losses.py"), #raw("series_5_a_sidewalkpilot_trainer.py") (train), and the C/E entry points. For usable pixels $i$, the per-image focal objective is
$ F = (sum_i w_i (1-p_i)^(1.5) (-ln p_i)) / (sum_i w_i). $
Here $p_i$ is the probability assigned to the target class, not always the sidewalk probability. Background has weight 2, sidewalk 1. The trainer averages per-image values, not all pixels globally. In this campaign every image is weak supervision; total loss is half the weak focal mean. Dice and strong focal are inactive. Zero on those charts is not perfect accuracy.

*Gradient answer:* Ignore removes a loss term at that output coordinate. The corresponding input pixels can still influence neighboring supervised logits through the receptive field. Do not confuse a gradient with respect to an output logit with a gradient with respect to the input image. Argmax would discard the confidence information needed by this loss; it is not used for training gradients.

*Freeze answer:* Frozen features remain decoder inputs. Decoder weights can receive gradients without gradients being computed for encoder weights. C updates both immediately. E freezes the encoder parameters and switches the encoder to evaluation mode for epochs 1–2; at epoch 3 the same encoder is unfrozen. Decoder parameters and optimizer history are not reset. Eval mode alone does not freeze weights. AdamW uses gradient moments and decoupled weight decay; gradient clipping precedes the update. FP32 is numeric precision, not an architecture.

*Do:* In the synthetic lab, inspect the ignored logit's gradient and compare encoder and head tensors before/after optimizer.step. The lab compresses two phases into two steps; it does not simulate two training epochs or prove accuracy. In the real run: 8,000 / 8 = 1,000 optimization steps per epoch, up to 20 epochs, patience 5. Explain why a falling batch loss alone cannot choose a release.

#pagebreak()
#chapter("05 / RESULTS", "Defend the denominator and the checkpoint")
#q[Your model predicts sidewalk almost everywhere. How can recall look excellent while the mask floods driveways? Which checkpoint would you pick?]
On known pixels only: sidewalk precision $= "TP"/("TP"+"FP")$; recall $= "TP"/("TP"+"FN")$; IoU $= "TP"/("TP"+"FP"+"FN")$. For an example with TP=90, FP=30, FN=10, TN=70, work out precision, recall, sidewalk IoU and background IoU before reading on.

*Answer check:* Precision = 75%; recall = 90%; sidewalk IoU = 90/130; background IoU = 70/110. Binary mean IoU is the arithmetic mean of those two IoUs, not accuracy. Unknown pixels do not become TN. An undefined ratio is not zero. Pooling pixel counts and then dividing is different from averaging per-image ratios. A large near-camera slab can dominate area IoU even when the distant edge is visibly wrong.

*Checkpoint drill:* Suppose epochs A/B have sidewalk IoU 91.0%/90.3% and precision 93%/96%, with all other epochs worse on IoU and ineligible for smart selection. Best-IoU selects A. Smart selects B because it is within one percentage point and has higher precision. The unsuffixed file is the last completed epoch, not necessarily either one. Boundary F1 uses matched edges within two reference pixels; it is reported separately. Read #raw("checkpoint_names.py") and #raw("boundary_metrics.py").

*Paper gate:* Specify which class, aggregation, tolerance, reference provenance and partition you used. A comparison of C/E on the same split tests the warmup change for this setup; one seed does not isolate its effect in all settings. The 30-frame variety review was selected for diversity; its acceptance rate is not an unbiased corpus accuracy estimate. Do not quote the planned maximum epochs as completed epochs.

*Independent exercise:* From one completed validation report recompute precision from counts. Compare the result with history and note the epoch. If there is no completed report yet, label this exercise pending rather than inventing a number.

#pagebreak()
#chapter("06 / ROBOT SYSTEMS", "From a camera timestamp to an actuator")
#q[A Jetson result just arrived. Why might it already be too old to steer? Why can't you drop the C/E checkpoint into the old steering decoder?]
Under #raw("code/controller/current/rc_car_app/"), trace #raw("vision.py"), #raw("jetson_client.py"), #raw("jetson_inference_server.py"), #raw("runtime.py") and #raw("hardware.py"). Draw capture → submission → inference → returned sample → command arbitration → servo. Separately draw IMU, LiDAR and manual inputs; place display and logging outside the learned model.

*Contract check:* Historical models do not all have the same output. The legacy decoder distinguishes scalar steering, two-control outputs, hybrid bucket logits and offsets, and the Series 4 horizon contract. S4 takes horizon zero from an 18-value vector per horizon; the selected bucket and its offset yield an angle. A two-channel spatial logit tensor means none of these things. You need segmentation-aware interfaces and verified geometry/planning; a changed filename is not integration.

*Time check:* In AsyncJetsonSteeringClient.get_latest_sample, find model-version, generation and age checks. A recently received answer can still correspond to an old capture. Distinguish result age from capture-to-result latency. Explain why an unbounded FIFO of frames can maintain throughput while latency grows, and why a monotonic clock matters for elapsed time.

*Safety check, offline only:* Read #raw("lidar.py"), #raw("lidar_avoidance.py"), #raw("yaw_pid.py") and #raw("test_manual_brake_takeover.py"). Trace how “no fresh measurement” differs from “fresh measurement, clear path.” In #raw("hardware.py") locate normalized steering, mechanical center trim and servo bounds. Predict what a sign error would do. For logging, trace InterruptionClipRecorder.update: what is captured around a takeover, and what cannot be inferred about its cause from a clip alone?

*Do:* In #raw("code/test_files/controller/"), read #raw("test_async_jetson_client.py") and follow one simulated stale-result case if present; identify the relevant assertions or design the missing case. Use mocks or recorded inputs, not a moving vehicle.

#pagebreak()
#chapter("07 / MEASUREMENT AND DEFENSE", "What a sidewalk mask cannot tell you")
#q[Two masks have identical IoU. Can they give different sidewalk widths at the same station? Can the IMU distinguish pavement slope from acceleration during a turn?]
*Width:* Yes. IoU pools area; a boundary error at the measurement cross-section can change width disproportionately. A monocular pixel gives a ray, not a unique distance. For a calibrated ray from camera center $C$ in direction $r$, intersect ground plane $n dot X+d=0$: $X=C+t r$, $t=-(n dot C+d)/(n dot r)$. The denominator approaching zero makes far-away estimates sensitive to pitch. Camera intrinsics, distortion, height/orientation and the local ground model matter. Two inferred edges must correspond to the same physical cross-section. This is a derivation to validate, not a claim that the production path already implements it.

*Slope and distance:* Running and cross slope use different sidewalk-aligned axes. Body roll is not automatically cross slope. Sensor bias, mount alignment, turns, bumps and vehicle acceleration can contaminate estimates. Wheel pulses times calibrated distance per pulse estimate path length; slip and steering introduce error. In the paper state units (degrees or percent grade), calibration source, station matching tolerance and which unavailable values remain missing.

*Field design:* Three passes on the same route estimate repeatability there, not three independent neighborhoods. Compare paired errors at matched stations; report feature-specific MAE, RMSE, counts, and coverage. Include supervision and verification in labor. Extra upfront cost divided by positive recurring savings per mile estimates break-even miles. No positive savings means no positive savings-based break-even. Use the approved plan and actual field records for claims; the workbook is not an authorization.

*Final oral drill:* Have someone pick one failed mask or stale sample. In 90 seconds name the module, input, invariant, plausible failure, and one test that could falsify your diagnosis. Then answer “What did you do? What did AI do? What evidence changed your mind?” One honest unknown plus a precise experiment is a better defense than a memorized claim.
