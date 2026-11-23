#let facts = json("implementation-facts.json")
#let ink = rgb("193b38")
#let blue = rgb("235b83")
#let muted = rgb("57616b")
#let pale = rgb("edf4f3")
#set document(title: "SidewalkPilot 5.C: Mathematics and Computer Science", author: "SidewalkPilot project; AI-assisted technical guide")
#set page(paper: "us-letter", margin: (x: 0.68in, top: 0.65in, bottom: 0.65in),
  header: text(font: "DejaVu Sans", size: 8pt, fill: muted)[SIDEWALKPILOT / 5.C / IMPLEMENTATION GUIDE],
  footer: context align(right, text(font: "DejaVu Sans", size: 8pt, fill: muted)[21 NOV 2026 #h(12pt) #counter(page).display("1")]))
#set text(font: "DejaVu Serif", size: 10pt, lang: "en")
#set par(justify: false, leading: 0.55em)
#set heading(numbering: none)
#show heading.where(level: 1): set text(font: "DejaVu Sans", size: 21pt, weight: "bold", fill: ink)
#show heading.where(level: 2): set text(font: "DejaVu Sans", size: 12pt, weight: "bold", fill: blue)
#show heading.where(level: 3): set text(font: "DejaVu Sans", size: 10pt, weight: "bold", fill: ink)
#show raw: set text(font: "DejaVu Sans Mono", size: 8pt)
#show raw.where(block: true): block.with(fill: rgb("f2f4f6"), inset: 9pt, radius: 3pt, width: 100%)
#show math.equation: set text(font: "DejaVu Math TeX Gyre")
#set table(inset: 5pt, stroke: 0.4pt + rgb("cbd3d7"), align: left)
#let note(body) = block(width: 100%, inset: 10pt, fill: pale, stroke: (left: 2pt + ink), body)
#let tag(body) = text(font: "DejaVu Sans", size: 8pt, weight: "bold", fill: muted, body)
#let next(title, subtitle) = {
  pagebreak()
  heading(level: 1, title)
  text(font: "DejaVu Sans", size: 10pt, fill: muted, subtitle)
  v(8pt)
}
#let small(body) = text(size: 8.7pt, body)
#let stage(body) = block(width: 100%, inset: 4pt, fill: pale, align(center, body))

#tag[MATHEMATICS + COMPUTER SCIENCE]
= SidewalkPilot 5.C
#text(font: "DejaVu Sans", size: 15pt, fill: blue)[How the segmentation model actually works]

*ConvNeXt-Tiny encoder + custom U-Net-style decoder. Full FP32.*

This guide follows the code in the current `series-5` checkout. It explains what happens to an image, how a mask is predicted, how training changes weights, and what changes when the same network runs normally. Equations describe the implemented model, not a different architecture we might build later.

#note[*The central distinction:* inference computes a prediction using existing weights. Training computes a prediction, compares it with a target, differentiates the error, and updates those weights. A forward pass alone does not teach the model anything.]

== The two paths
*Training*

$ "image + target" arrow.r "prediction" arrow.r "loss" arrow.r "gradients" arrow.r "updated weights" $

*Normal inference*

$ "image" arrow.r "fixed trained weights" arrow.r "sidewalk/background mask" $

== What is fixed for this version?
#table(columns: (1.1fr, 2fr),
  [Model name], [*5.C*, an uppercase-letter beta],
  [Model input], [960 wide by 540 high; RGB; FP32],
  [Model output], [Two scores per pixel: background and sidewalk],
  [Encoder / decoder], [ConvNeXt-Tiny / three skip-fusion stages],
  [Trainable parameters], [28,855,298 (about 28.9 million)],
  [Initialization], [ImageNet encoder; newly initialized decoder],
  [Default batch / limit], [8 images / 20 epochs, with early stopping],
)

== Reading map
Pages 2-6 explain the network. Pages 7-13 explain data, loss, learning, and checkpoints. Pages 14-16 explain normal operation, evaluation, and practical limits. Pages 17-18 identify the code, verification, and references.

#small[*Status:* architecture and numerical checks are implemented. A short setup smoke test is not a completed 5.C experiment. This document does not launch training, claim final accuracy, or establish real-time Jetson performance. The data campaign and release still require quality checks.]

#next("1. The tensor map", "An image becomes feature maps, then a mask.")
== Mathematics view
A tensor is a multidimensional array. PyTorch image batches use $[N,C,H,W]$: batch size, channels, height, width. A feature channel is a learned response map, not a manually assigned object class. Here $N=8$ during default training and usually $N=1$ during inference.

#small[
#table(columns: (1.45fr, 1.3fr, 1.35fr),
  table.header([*Operation*], [*Output: C x H x W*], [*Role*]),
  [RGB input], [3 x 540 x 960], [Normalized image],
  [Stem: 4 x 4, stride 4], [96 x 135 x 240], [Initial features],
  [Stage 1: 3 blocks], [96 x 135 x 240], [Skip $E_1$],
  [Downsample + stage 2], [192 x 67 x 120], [3 blocks; skip $E_2$],
  [Downsample + stage 3], [384 x 33 x 60], [9 blocks; skip $E_3$],
  [Downsample + stage 4], [768 x 16 x 30], [3 blocks; deepest $E_4$],
  [Bottleneck projection], [256 x 16 x 30], [Decoder input],
  [Fuse with $E_3$], [128 x 33 x 60], [Decoder `up16`],
  [Fuse with $E_2$], [64 x 67 x 120], [Decoder `up8`],
  [Fuse with $E_1$], [32 x 135 x 240], [Decoder `up4`],
  [1 x 1 classifier], [2 x 135 x 240], [Two class logits],
  [Bilinear resize], [2 x 540 x 960], [Model return value],
)]

== Computer science view
The encoder saves four outputs from `features[1]`, `[3]`, `[5]`, and `[7]`. The decoder takes these in order from deepest to shallowest. `model(image)["out"]` returns a floating-point tensor, *not* a colored PNG or a list of steering commands.

The heights are deliberately *135, 67, 33, 16*, not rounded-up multiples. Unpadded stride-2 downsampling takes the floor. The decoder resizes to each skip's exact dimensions, so odd-sized feature maps still align.

#note[*Width versus height:* we say 960 x 540 for a picture, but write `[N, 3, 540, 960]` in code. Existing 1280 x 720 dataset images are resized for the network; the model's input size is not a claim about the camera's active capture configuration.]

#grid(columns: (1fr, 16pt, 1fr, 16pt, 1fr, 16pt, 1fr), align: center, row-gutter: 3pt,
  stage[$E_1$: 96 ch.], $arrow.r$, stage[$E_2$: 192 ch.], $arrow.r$, stage[$E_3$: 384 ch.], $arrow.r$, stage[$E_4$: 768 ch.],
  small[skip $arrow.b$], [], small[skip $arrow.b$], [], small[skip $arrow.b$], [], small[project $arrow.b$],
  stage[$D_1$: 32 ch.], $arrow.l$, stage[$D_2$: 64 ch.], $arrow.l$, stage[$D_3$: 128 ch.], $arrow.l$, stage[$D_4$: 256 ch.],
)
#small[Encoder flows right; decoder flows left. $D_1$ feeds the class head and output resize. Each skip is projected and concatenated, not simply added.]

#small[Evidence: the accompanying shape capture runs this exact network and records all listed shapes and dtypes. [C1, C2]]

#next("2. Pixels and convolution", "How numerical image features are made.")
== Input preparation
Images are converted to RGB, resized to 960 x 540 with bilinear interpolation, converted from bytes to FP32 values in $[0,1]$, then normalized channel by channel:

$ x_(c,h,w) = (I_(c,h,w)/255 - mu_c) / sigma_c $

$ mu=(0.485,0.456,0.406), quad sigma=(0.229,0.224,0.225). $

These are the normalization constants used with the ImageNet initialization. For example, a red value of 128 becomes approximately $(128/255-0.485)/0.229 = 0.074$. Values after normalization can be negative or above one. That is expected.

== What a convolution calculates
For dilation 1, a convolution output is a weighted sum over an image patch and its input channels:

$ Y_(o,h,w) = b_o + sum_(c,u,v) K_(o,c,u,v) X_(c,s h+u-p,s w+v-p). $

Here $K$ is a learned kernel, $b$ a bias, $s$ the stride, and $p$ padding. Out-of-bounds padded values are zero. PyTorch calls this convolution, although the stored kernel is applied as cross-correlation without flipping. Its spatial output size is

$ H' = floor((H+2p-k)/s)+1. $

For the stem, $k=s=4$, $p=0$, so $540$ becomes $135$. The first stride-2 downsample turns $135$ into $67$.

== Why learned filters matter
Early features can respond to local edges, contrast, or texture; later layers combine broader context. These are interpretations of learned representations, not hard-coded promises that a particular channel means "curb" or "shadow."

A standard convolution has $C_"out" C_"in" k^2$ kernel parameters, plus $C_"out"$ biases when enabled. Its approximate multiply-accumulate count is $H' W' C_"out" C_"in" k^2$ per image. Reusing the same kernel at every position is *weight sharing*.

== Computer science view
The code uses `nn.Conv2d`, not Python loops over pixels. PyTorch dispatches tensor operations to CPU or CUDA kernels. Automatic differentiation records enough of the computation to obtain gradients later; the programmer does not hand-write one derivative per weight.

#note[Training labels must *not* use bilinear resizing: mixing class IDs would create meaningless labels. Training masks use nearest-neighbor resizing; images and class scores may use bilinear resizing. [C3]]

#next("3. Inside ConvNeXt", "Tiny describes a model size, not the quality of its predictions.")
== The residual block
The four stages contain 3, 3, 9, and 3 blocks, at 96, 192, 384, and 768 channels. Within each block, with input $X$:

$ U = "DWConv"_(7 times 7)(X) $
$ V = "LN"(U), quad A=W_1 V+b_1, quad B="GELU"(A) $
$ R=W_2 B+b_2, quad Y=X+"DropPath"(gamma dot R). $

These channel-mixing equations apply independently at every spatial location. $W_1$ expands $C$ channels to $4C$; $W_2$ reduces them back to $C$. The learned scale $gamma$ has one value per channel. The input and residual have equal shapes, so they can be added. [R1, R2]

== What each operation does
*Depthwise convolution:* each channel gets its own 7 x 7 spatial kernel (`groups=C`). It uses $49C$ kernel parameters rather than $49C^2$ for a dense same-width convolution. Channel mixing happens in the later linear layers.

*Layer normalization:* at each spatial position, normalize across channels:

$ "LN"(u_c)=a_c (u_c-overline(u))/sqrt(v+epsilon)+b_c. $

$overline(u)$ and $v$ are that position's channel mean and population variance. $a_c,b_c$ are learned affine parameters; $epsilon=10^(-6)$ prevents division by zero.

*GELU:* a smooth nonlinear activation $"GELU"(a)=a Phi(a)$, where $Phi$ is the standard-normal cumulative distribution function. Without nonlinearities, stacking linear operations would have much less expressive power.

*Residual addition:* the block learns a change to $X$, rather than having to reconstruct all of $X$ from scratch. The identity route also supplies a direct path for gradients.

== Computer science view
Depthwise convolution uses NCHW tensors. The block temporarily permutes to NHWC for channel-wise LayerNorm and `nn.Linear`, then permutes back. These are layout changes, not image rotations.

During training, stochastic depth randomly drops a residual branch per sample. Block $j$ uses $p_j=0.1j/17$, for $j=0,...,17$; kept branches are scaled by $1/(1-p_j)$. In evaluation no branch is dropped. Layer scale initializes to $10^(-6)$ in a fresh encoder, but the default pretrained encoder loads its already-learned values.

#small[This encoder is a convolutional network, not a self-attention Transformer. LayerNorm uses the current input in both training and evaluation; it is not BatchNorm with running averages. [C1, R2]]

#next("4. The U-Net-style decoder", "Context comes up; spatial detail comes across.")
== Two different skip connections
Inside ConvNeXt, a *residual skip adds* a block's input to its output. Across the encoder and decoder, a *U-Net-style skip concatenates* a projected encoder feature map with an upsampled decoder map. These are different operations.

Let $E_1,...,E_4$ be the encoder outputs, and $P$ denote a learned 1 x 1 projection. The decoder begins with

$ D_4=P_4(E_4), quad 768 arrow.r 256 " channels". $

Each fusion block then computes

$ T_j="concat"("resize"(D_(j+1),"size"(E_j)),P_j(E_j)) $
$ D_j=F_j(T_j), quad j=3,2,1. $

$F_j$ is two repetitions of *3 x 3 convolution, GroupNorm, GELU*. The final scores are

$ Z="resize"(P_"head"(D_1),(540,960)). $

#table(columns: (1fr, 1fr, 1fr, 1fr),
  table.header([*Fusion*], [*Upsampled*], [*Skip projected*], [*Concat / out*]),
  [With $E_3$], [256 channels], [384 to 128], [384 / 128],
  [With $E_2$], [128 channels], [192 to 64], [192 / 64],
  [With $E_1$], [64 channels], [96 to 32], [96 / 32],
)

== GroupNorm and interpolation
GroupNorm divides the channels into *8 groups* per sample and normalizes within each group's channels and spatial positions, with learned per-channel scale and bias. Its epsilon is $10^(-5)$. It does not depend on batch running statistics. [C1]

Bilinear interpolation is a weighted blend of nearby values. With `align_corners=False`, an output coordinate $q$ corresponds approximately to $(q+0.5)n_"in"/n_"out"-0.5$ in the input, using edge handling at the boundaries. The interpolation itself has no learned weights.

== Computer science view
This is a *custom, compact U-Net-style decoder*, not an exact reproduction of the original U-Net paper. There are three fusion blocks, no transposed convolutions, and no full-resolution input skip. The two-class head operates at 135 x 240 before logits are enlarged. [C1, R3]

#note[Skip features can help recover boundaries, but upsampling cannot recreate information already lost. More decoder capacity does not automatically fix incorrect labels, missing curb edges, or driveway confusion.]

#next("5. Weights and FP32", "Architecture, initialization, and precision are separate choices.")
== What can learn?
Trainable parameters include convolution kernels, linear matrices, enabled biases, normalization affine parameters, and ConvNeXt layer scales. Interpolation, concatenation, and GELU do not have trainable weights of their own.

#table(columns: (1.4fr, 1fr, 1.6fr),
  table.header([*Part*], [*Parameters*], [*Default start*]),
  [Encoder], [27,818,592], [ImageNet-pretrained],
  [Decoder], [1,036,706], [New initialization],
  [Total], [28,855,298], [All trainable],
)

The ImageNet classification pooling/head is discarded. Its pretrained feature extractor is retained. *Both encoder and decoder train from the first update.* There is no implemented encoder-freeze warmup. The inherited BatchNorm handling does not freeze this LayerNorm-based encoder. [C1, C3]

== What full FP32 means here
An FP32 value uses 32 bits: a sign, an 8-bit exponent, and a 23-bit fraction, with an implicit leading bit for normal numbers. It is finite-precision arithmetic, not exact real-number mathematics. The current contract is:

- Parameters, normalized inputs, logits, gradients, and floating optimizer state use FP32.
- Autocast is disabled inside the forward pass. TF32 matrix-multiplication and convolution modes are disabled.
- Targets remain integer class IDs (`int64`); saved class masks are `uint8`. Integers do not become FP32 merely because the network uses FP32.
- The trainer's gradient scaler is disabled: no FP16 loss scaling is performed.

The model checks input and parameter dtypes and rejects incompatible values. Checkpoint loading also validates its architecture and floating parameter types. [C1, C2]

== Memory accounting
$ "weights bytes"=28,855,298 times 4=115,421,192. $

That is approximately *110.07 MiB* for weights alone. Weights, gradients, and AdamW's two moment arrays together are roughly four times that, or *440.30 MiB*. Activations, temporary tensors, CUDA workspaces, the optimizer step, and input batches require additional memory, often much more.

#note[FP32 is a numerical-format choice, not an architecture or an accuracy guarantee. A saved FP32 checkpoint does not prove an older training run used FP32 arithmetic. No reduced-precision deployment engine is built by this model factory.]

#next("6. Targets and data splits", "The model cannot learn a reliable boundary from unreliable supervision.")
== The three stored label values
#table(columns: (0.6fr, 1.1fr, 2.3fr),
  table.header([*ID*], [*Meaning*], [*Training treatment*]),
  [0], [Background], [Supervise as not-sidewalk],
  [1], [Sidewalk], [Supervise as sidewalk],
  [255], [Unknown / ignored], [No direct pixel loss],
)

The network still has *two* output channels. Ignore ID 255 is an annotation instruction, not a third predicted class. A positive-only reviewed mask establishes known sidewalk pixels but does not establish that all other pixels are background. Those other pixels must stay ignored unless separately verified.

*The project label policy* includes sidewalk cracks and cast shadows as part of the underlying sidewalk, and includes the sidewalk portion crossing a driveway. It excludes the actual driveway beyond the sidewalk corridor. Unclear boundaries need review rather than a forced confident label.

== Strong labels versus pseudo-labels
Reviewed binary references provide verified positive and negative supervision. Positive-only references and screened SAM-generated masks belong to the weaker supervision pool. SAM is a *label-generation tool*, not a component inside this ConvNeXt network. A mask passing automatic checks is still a pseudo-label, not established ground truth.

== The current development split
#table(columns: (1fr, 1fr, 1fr, 1fr),
  table.header([*Partition*], [*Date group*], [*Binary*], [*Partial*]),
  [Train], [July 2, 2026], [29], [218],
  [Validation], [July 12, 2026], [13], [105],
  [Test], [July 7, 2026], [5], [28],
)

These are *398 usable reviewed images*, before adding pseudo-labels; two of the 400 reviewed records were excluded. Grouping by acquisition day keeps those days separate. Nearby images are correlated, so a random frame-level split could make results look stronger than genuine generalization. Grouping does not prove the days contain independent routes.

#note[This is a development split, not the research plan's final 80/10/10 experiment and not an untouched final benchmark. Previously inspected test examples can no longer support an "unseen throughout development" claim. Labeling all 81k images must not mean training on the held-out images.]

#small[The full-run 5.C entry point requires a mixed-dataset manifest with at least 10,000 accepted pseudo-labels, except for a smoke run. That metadata gate and loader checks do not certify mask accuracy. The 10k target is not yet a completed quality-verified dataset. [C2-C5]]

#next("7. Batches and augmentation", "What one epoch actually contains.")
== Computer science view
The default batch has *8 images*: 4 strong binary references plus 4 weak examples. Weak examples can be positive-only references or screened pseudo-labeled images. Each pool is shuffled using the seed and epoch; a pool cycles when exhausted. The combined batch is also shuffled.

If $n_s$ and $n_w$ are the pool sizes, the default number of updates in one epoch is

$ T_"epoch"=max(ceil(n_s/4),ceil(n_w/4)). $

With 29 strong images, those same reviewed examples are visited repeatedly while the much larger weak pool is traversed. The final weak batch can also repeat a few entries. Therefore an epoch is not necessarily "every image exactly once." [C3, C4]

== Mathematics view: useful variation
Training applies paired horizontal flips to image and target with probability 0.5. It changes image brightness, contrast, and saturation, but *does not* apply these color changes to the class mask:

#table(columns: (1.35fr, 1fr, 1.65fr),
  table.header([*Transformation*], [*Range / chance*], [*Affects target?*]),
  [Horizontal flip], [50%], [Yes, same spatial flip],
  [Brightness factor], [0.8 to 1.2], [No],
  [Contrast factor], [0.85 to 1.15], [No],
  [Saturation factor], [0.9 to 1.1], [No],
  [Training resize], [960 x 540], [Yes, nearest neighbor],
)

The ranges above are uniformly sampled. This asks the model to produce similar semantic predictions under controlled appearance changes. It does not create genuinely new locations or repair incorrect supervision.

== A training step in plain language
1. Select the eight image/target pairs.
2. Read RGB images and corresponding class-ID masks.
3. Apply the paired spatial transformation and image-only color changes.
4. Normalize and stack images into `[8, 3, 540, 960]`.
5. Stack targets into `[8, 540, 960]`, and retain which images are strong.
6. Transfer tensors to the chosen device and run one optimizer update.

Validation has no random training augmentation. Its reference masks stay at their original resolution; predicted logits are resized to match them for evaluation.

#note[Repeated exposure changes optimization, not the count of independent observations. The paper should report unique images and acquisition groups separately from batches, epochs, and optimizer updates.]

#next("8. The implemented loss", "Two-class cross-entropy, background weighting, and weaker supervision.")
== Scores become probabilities
For image $n$, pixel $i$, and class $c in {0,1}$, the network produces logits $z_(n,i,c)$. Softmax defines

$ p_(n,i,c)=exp(z_(n,i,c))/(exp(z_(n,i,0))+exp(z_(n,i,1))). $

A logit is any real score, not a probability. Only relative scores matter. Cross-entropy for known target $y_(n,i)$ is $-ln(p_(n,i,y_(n,i)))$. PyTorch computes this stably from logits; do not apply softmax first when calling `cross_entropy`.

== Pixel weighting and image averaging
Define $a_(n,i)=2$ for known background, $1$ for known sidewalk, and $0$ for ignored pixels. Then the implemented per-image loss is

$ ell_n = (sum_i a_(n,i) [-ln(p_(n,i,y_(n,i)))]) / max(1,sum_i a_(n,i)). $

Ignored terms are omitted; no nonexistent class-255 probability is looked up. If $S$ is the set of valid strong images and $W$ the valid weak images:

$ L_s=1/abs(S) sum_(n in S) ell_n, quad L_w=1/abs(W) sum_(n in W) ell_n $
$ L=L_s+0.5 L_w. $

An empty group contributes differentiable zero. The training sampler normally supplies both. Group means are separate: this is *not* one unweighted mean across all pixels in all eight images. [C4]

== A two-pixel calculation
Suppose both pixels predict sidewalk probability 0.8. One is actually background; the other is sidewalk. Their image loss is

$ ell=(-2 ln(0.2)-ln(0.8))/3 approx 1.14734. $

The model is penalized strongly for the false sidewalk prediction. The class weighting discourages flooding, but does not prohibit it. The 0.5 group coefficient reduces the weak pool's contribution; it does not make a wrong pseudo-label correct.

#note[*Implemented:* weighted cross-entropy and separate strong/weak group means. *Not implemented here:* Dice loss, focal loss, a boundary loss, or a hard constraint that masks stay inside the sidewalk. Earlier plans for different losses are not descriptions of this trainer.]

#small[The companion numerical audit verifies this example and its logit gradients against the real `conservative_loss` function. [C4, R4]]

#next("9. Backpropagation", "How error at the mask reaches millions of weights.")
== Mathematics view
For a known pixel, differentiating the per-image loss with respect to logit $z_(n,i,c)$ gives

$ (partial ell_n)/(partial z_(n,i,c)) = a_(n,i)/D_n (p_(n,i,c)-bb(1)[c=y_(n,i)]), $

where $D_n=sum_i a_(n,i)$ and $bb(1)$ is 1 when its condition is true and 0 otherwise. For the total batch loss, multiply by $1/abs(S)$ for a strong image or $0.5/abs(W)$ for a weak one.

If the true class is sidewalk and sidewalk probability is too low, its logit derivative is negative. A small negative-gradient step tends to increase that logit. If the true class is background and sidewalk probability is high, the derivative instead pushes the sidewalk score down.

For a parameter $theta_j$, the chain rule connects that pixel error to earlier operations:

$ (partial L)/(partial theta_j)=sum_(n,i,c) (partial L)/(partial z_(n,i,c)) (partial z_(n,i,c))/(partial theta_j). $

Every path using that parameter contributes. Convolutional weight sharing means many positions contribute to the same kernel's gradient. At a residual addition, the incoming gradient flows into both branches; at concatenation, it splits into the corresponding channel slices. Bilinear resize redistributes gradients using its interpolation weights.

== Computer science view
`loss.backward()` traverses PyTorch's computation graph and accumulates derivatives in each parameter's `.grad`. It does *not* change the parameter values. `optimizer.step()` changes the weights later. `zero_grad(set_to_none=True)` clears the previous step's gradients so they are not accidentally accumulated.

During training, intermediate activations must be retained or recoverable for backward. This is a major reason training uses more memory than inference.

== Guardrails before the update
The trainer checks finite losses and gradients and clips the combined gradient's Euclidean norm:

$ g' = g min(1,1/(norm(g)_2+10^(-6))). $

This matches a maximum norm of 1 with a small denominator stabilizer. Clipping rescales the *whole gradient vector*; it is not clipping each weight or setting each derivative to the interval $[-1,1]$.

#note[Ignored pixels have zero direct supervised loss. Their surrounding image content can still influence predictions at known pixels through convolutions and normalization. "Ignored" does not mean the input image is erased there.]

#next("10. AdamW updates", "A worked example of a weight changing.")
== The optimizer's state
Let $g_t$ be the gradient after clipping. AdamW keeps a moving mean $m_t$ and moving squared-gradient mean $v_t$ for every parameter:

$ m_t=beta_1 m_(t-1)+(1-beta_1)g_t $
$ v_t=beta_2 v_(t-1)+(1-beta_2)g_t^2 $
$ hat(m)_t=m_t/(1-beta_1^t), quad hat(v)_t=v_t/(1-beta_2^t) $
$ theta_t=(1-eta_t lambda)theta_(t-1)-eta_t hat(m)_t/(sqrt(hat(v)_t)+epsilon). $

Operations are elementwise except the earlier global clipping. The defaults are $beta_1=0.9$, $beta_2=0.999$, $epsilon=10^(-8)$, and weight decay $lambda=10^(-4)$. Bias correction compensates for moment arrays starting at zero. Decoupled weight decay shrinks parameters separately from the loss gradient. [R5, R6]

The encoder starts at learning rate $10^(-4)$ and decoder at $10^(-3)$. Both use the same decay. There are no special bias/norm decay exclusions in the current optimizer groups.

== One pixel, one scalar weight
This is a teaching example, *not* a real complete network. Let input $x=2$, parameter $w=0.5$, logits $(z_0,z_1)=(0,w x)=(0,1)$, and target sidewalk:

$ p_1=exp(1)/(1+exp(1)) approx 0.731059 $
$ L=-ln(p_1) approx 0.313262 $
$ (partial L)/(partial w)=x(p_1-1) approx -0.537883. $

Clipping leaves this gradient unchanged because its magnitude is below 1. On the first AdamW step, $hat(m)=g$ and $hat(v)=g^2$. Using decoder learning rate 0.001:

$ w_"new"=0.5(1-0.001 times 0.0001)-0.001 (-0.537883)/(0.537883+10^(-8)) $
$ w_"new" approx 0.50099995. $

The weight increases, raising the sidewalk logit for this example. The captured FP32 execution gives approximately *#calc.round(facts.toy.updated_weight, digits: 8)*; slight differences in the last digits are rounding, not a different rule.

#note[AdamW is not simply "subtract learning rate times gradient." Its history and per-parameter normalization change the step. A real batch has many competing errors, so one update need not improve every individual image.]

#next("11. The training program", "The outer loop coordinates many small updates.")
== Computer science view
The following is explanatory pseudocode matching the main sequence. The real trainer also validates data, handles failures, writes files, and logs metrics.

```python
model = make_model(weights="imagenet").to(device).float()
optimizer = AdamW([
    {"params": model.backbone.parameters(), "lr": 1e-4},
    {"params": model.classifier.parameters(), "lr": 1e-3},
], weight_decay=1e-4)
scheduler = CosineAnnealingLR(optimizer, T_max=20)

for epoch in range(20):
    model.train()                    # stochastic depth ON
    sampler.epoch = epoch
    for images, targets, strong in training_batches:
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)["out"]  # FP32 forward
        loss = conservative_loss(logits, targets, strong)[0]
        require_finite(loss)
        loss.backward()             # compute gradients
        clip_grad_norm_(model.parameters(), 1.0)
        require_finite_gradients(model)
        optimizer.step()            # change parameters
    metrics = validate(model)       # no weight updates
    scheduler.step()                # once per epoch
    save_last_and_maybe_best(metrics)
    if five_epochs_without_better_sidewalk_iou:
        break
```

== Learning-rate schedule
With initial rate $eta_0$, the rate used at zero-indexed epoch $e$ is

$ eta(e)=eta_0/2 (1+cos(pi e/20)). $

At $e=0$ it is the initial rate; at $e=10$ it is half. The scheduler reaches zero after the twentieth epoch; that value is for a next epoch that is not run. There is no warmup or cosine restart in this configuration. [C3, R7]

== Validation is a different phase
After each epoch, binary validation references supply the checkpoint-selection metrics; partial references also supply known-sidewalk recall. Neither updates weights. A strict improvement in *sidewalk IoU* selects `best.pt`; otherwise the stale-epoch count increases. Training stops after five consecutive non-improving epochs or the 20-epoch limit. The loop does not automatically evaluate the held-out test partition.

#small[The base trainer retains a GradScaler interface, but it is disabled for 5.C. The pseudocode shows the equivalent ordinary FP32 operations rather than implying mixed precision is active.]

#next("12. State and reproducibility", "A model file is more than a model name.")
== Checkpoints
`best.pt` contains the best validation-IoU state; `last.pt` contains the latest saved epoch state. Atomic writes reduce the risk of leaving a partially replaced checkpoint if the process is interrupted.

#table(columns: (1.25fr, 2.5fr),
  table.header([*Saved item*], [*Why it matters*]),
  [Model state], [Learned encoder and decoder parameter tensors],
  [Configuration], [Architecture, input size, precision, initialization],
  [Optimizer state], [AdamW moments, update counters, parameter groups],
  [Scheduler state], [Where the learning-rate schedule has reached],
  [Epoch / history], [Progress, best IoU, stale count, logged results],
  [Dataset identities], [Hashes tying the run to its data and split],
  [Scaler state], [Disabled in FP32; not evidence of active AMP],
)

To resume training properly, restore the optimizer and scheduler as well as weights. Reloading only weights and starting fresh AdamW is a new optimization run, not an exact continuation.

== What resuming can and cannot do
The current resume path continues from the last *completed, saved epoch*, not the precise interrupted image or batch. Dataset/configuration checks protect against silently changing the experiment. The sampler is seeded by epoch. A seed helps reproducibility but does not guarantee bitwise-identical behavior across GPU types, PyTorch versions, or all execution settings.

Keep source version, environment versions, data hashes, class policy, random seeds, and the actual configuration with the run. A filename such as `5.C` alone cannot identify these choices.

== Local records and W&B
Local history, validation reports, status files, and checkpoints remain the primary run artifacts. W&B is a live view of metrics and approved metadata; it is not the optimizer and does not perform learning. A disconnected dashboard is not by itself proof that training stopped.

The established telemetry scope is losses, validation metrics, hyperparameters, split/dataset identities, and machine statistics. It excludes photos, masks, source code, and checkpoints. Obtain the appropriate full-run authorization before starting uploads; this document build uploads nothing to W&B.

#note[An offline record should distinguish "experiment completed," "smoke test completed," "interrupted," and "not started." Never promote the two-update setup smoke test into evidence of trained accuracy.]

#next("13. A normal prediction", "Same weights, no loss, no backward, no optimizer.")
== The runtime sequence
1. Load the matching architecture and checkpoint; validate configuration and FP32 tensors.
2. Call `model.eval()` and enter `torch.inference_mode()`.
3. Convert the camera/image input to RGB, resize, normalize, and make a batch of one.
4. Run encoder, decoder, and the two-channel output.
5. If needed, resize logits to the original image dimensions.
6. Take the winning class at each pixel and save or use the class-ID mask.

```python
model.eval()                        # stochastic depth OFF
with torch.inference_mode():        # no autograd graph
    x = preprocess_rgb(frame).unsqueeze(0).to(device)
    logits = model(x)["out"]        # [1, 2, 540, 960]
    logits = interpolate(
        logits, size=(original_height, original_width),
        mode="bilinear", align_corners=False)
    mask = logits.argmax(dim=1)[0].to(torch.uint8)
```

This is an inference pattern, not a complete runnable loader. Use the repository's checkpoint validation and preprocessing helpers rather than inventing different normalization.

== Mathematics view
$ hat(y)_i=arg max_(c in {0,1}) z_(i,c). $

Softmax does not change the winner, so it is optional when only class IDs are needed. For a probability display,

$ p_(i,1)=1/(1+exp(-(z_(i,1)-z_(i,0)))). $

The default rule selects the greater logit; it is not a special conservative threshold tuned to eliminate flooding. With two classes, exact ties resolve to the first index in `argmax`, background. Softmax scores are not automatically calibrated probabilities of correctness.

== What does not happen
There are no targets, supervised losses, gradient calculations, or optimizer updates. Repeated drives do not improve the model unless their data is later labeled and used in a separate training process. `eval()` changes module behavior but alone does not disable autograd; `inference_mode()` handles that.

#note[The classifier predicts pixels, not centimeters, degrees, steering, or throttle. Camera geometry, IMU/encoder measurements, planning, and safety control are separate downstream systems. The model currently has no temporal memory between frames.]

#next("14. Measuring performance", "Accuracy is measured against a reference, not a confidence score.")
== Count pixel outcomes
On *known reference pixels* only, treat sidewalk as positive: TP is correct sidewalk, FP is background predicted sidewalk, FN is missed sidewalk, and TN is correct background.

$ P="TP"/("TP"+"FP"), quad R="TP"/("TP"+"FN") $
$ F_1=(2 "TP")/(2 "TP"+"FP"+"FN"), quad "IoU"_s="TP"/("TP"+"FP"+"FN") $
$ "IoU"_b="TN"/("TN"+"FP"+"FN"), quad "mIoU"=("IoU"_s+"IoU"_b)/2. $

The mIoU expression assumes both class unions are nonzero. If a class has no union, its IoU is undefined and must be handled explicitly; do not fabricate a perfect score. The same care is required for other zero denominators.

== Interpret the metrics together
- *Precision* decreases when the mask floods into known background.
- *Recall* decreases when real sidewalk is omitted.
- *F1* balances precision and recall but is not a boundary-distance measure.
- *Sidewalk IoU* compares overlap with the union of the predicted and reference sidewalk.
- *mIoU* averages sidewalk and background IoU, rather than allowing one large class to dominate pixel accuracy.

For example, $"TP"=90$, $"FP"=10$, $"FN"=5$, and $"TN"=95$ give precision 90.00%, recall 94.74%, F1 92.31%, sidewalk IoU 85.71%, background IoU 86.36%, and mIoU 86.04%.

== Computer science view
For dataset metrics, sum confusion counts over the evaluated images and then calculate the metric. That is generally different from averaging every image's metric equally. Record which aggregation you report. Native-resolution references are compared against logits resized before taking class IDs. [C3]

The current trainer exposes precision, recall, F1, and the class IoUs; the comparison viewer derives mIoU. Best-checkpoint selection currently uses sidewalk IoU, not mIoU.

#note[A positive-only reference cannot establish false positives or verified background IoU. Its known-sidewalk recall is usable, but assigning all unmarked pixels to background creates an *assumption*, not ground truth. Some existing viewer comparisons use such provisional references; keep them separate from verified binary metrics.]

#small[Segmentation IoU does not measure sidewalk width or slope error. End-to-end physical accuracy still requires matched reference measurements, calibration, and separate MAE/RMSE analysis.]

#next("15. Why this architecture?", "What changed from 5.A and 5.B, and what is still unproven.")
== The naming confusion resolved
#table(columns: (1fr, 1.5fr, 1.5fr),
  table.header([*Role*], [*5.A / 5.B*], [*5.C*]),
  [Encoder], [MobileNetV3-Large], [ConvNeXt-Tiny],
  [Segmentation head], [LR-ASPP], [Custom U-Net-style decoder],
  [Parameters], [3,218,308], [28,855,298],
  [Recorded training precision], [BF16 mixed precision], [Full FP32 contract],
  [Floating checkpoint weights], [FP32], [FP32],
)

MobileNetV3 is an efficiency-oriented convolutional encoder using mobile-friendly blocks. LR-ASPP is its lightweight segmentation head. Neither is another name for U-Net or ConvNeXt. Historical 5.A/5.B artifacts remain their original architecture; this guide does not rename them. [R8]

== Why Tiny and U-Net-style fusion?
ConvNeXt-Tiny is the smallest standard ConvNeXt variant in the referenced family. It offers more representation capacity than the existing lightweight baseline while keeping the experiment smaller than larger ConvNeXt variants. "Tiny" still means millions of parameters.

The decoder combines deeper semantic context with finer encoder features, a reasonable design for sidewalk boundaries. This is an engineering rationale to test, not evidence that it must beat the smaller model. Compare models under controlled data, input size, and evaluation conditions to isolate architecture effects.

== Jetson feasibility needs measurement
The input resolution, encoder, decoder, FP32 arithmetic, framework, transfers, and preprocessing all affect runtime. More workstation GPU memory does not prove the model will fit the car's timing budget. This code has not established real-time FP32 ConvNeXt performance on the Jetson Orin Nano.

Benchmark end-to-end latency and sustained throughput on the actual device, including image capture and downstream work. Report warmup, power mode, peak memory, and variation in latency. A hypothetical 50 Hz loop has only 20 ms for *the entire loop*, not 20 ms per component.

#note[5.C is the first implemented ConvNeXt-Tiny/U-Net-style beta in this checkout. A future 5.D is not yet a trained version or a guarantee that every one of 81k masks is correct. Do not sacrifice held-out data or annotation quality to reach an image-count target.]

#next("16. Code and verification", "How to check this guide against the implementation.")
== Local source map
Paths below are relative to `code/ai_models_datasets/series_5/` in the repository. Trainers live here; supporting code and configs stay in `tools/`. Reusing A/B training code does not change the C model's architecture.

#small[
#table(columns: (0.4fr, 2.1fr, 2fr),
  table.header([*ID*], [*File*], [*Authority for*]),
  [C1], [`tools/models/convnext_tiny_unet.py`], [Encoder, decoder, FP32 checks],
  [C2], [`tools/configs/series_5_c_config.json` and `series_5_c_sidewalkpilot_trainer.py`], [5.C defaults, data-count gate, model wiring],
  [C3], [`series_5_a_sidewalkpilot_trainer.py`], [Shared data transforms, sampler, training, checkpoints, evaluation, prediction],
  [C4], [`series_5_b_sidewalkpilot_trainer.py`], [Screened batch composition and conservative loss],
  [C5], [`tools/filtering/pseudo_mask_filter.py` and `tools/datasets/pseudo_training_targets.py`], [Pseudo-label filtering and target preparation],
)]

== Reproducible document checks
`capture_facts.py` instantiates an untrained copy on CPU, hooks the encoder/decoder outputs, checks FP32 and the parameter count, and verifies the worked loss, gradient, and AdamW examples. It does *not* train or evaluate the research model. It stores its results in `implementation-facts.json`.

Captured environment: PyTorch *#facts.torch*; torchvision *#facts.torchvision*. Source hashes in the JSON identify the audited files. `build.py` rejects changes to those repository files until the facts are refreshed, compiles this Typst source, extracts text, and renders every PDF page for inspection.

```sh
# Run from this document's directory on this workstation.
/home/rsabavat/.gpu-env/bin/python capture_facts.py
/home/rsabavat/.venvs/sidewalkpilot-docs/bin/python build.py
```

The Typst source and its JSON companion can also be compiled with Typst directly. The Python verification/build scripts additionally require PyTorch/torchvision or the `typst` and `pymupdf` packages, respectively.

== Evidence boundaries
The earlier local two-update GPU smoke run verifies basic execution and saving, not learned generalization. Mathematical examples verify formulas, not mask quality. This guide is an AI-assisted explanation checked against local source; it is not a replacement for the researcher's notebook, approved research plan, or final experimental report.

#small[Safety-critical field operation still depends on the approved supervision and control system, not on a high segmentation metric. This document makes no new claim about operating permission.]

#next("17. References and vocabulary", "Primary sources; implementation takes precedence over generic examples.")
#set text(size: 9pt)
*R1.* Liu, Zhuang, et al. "A ConvNet for the 2020s." 2022.
#link("https://arxiv.org/abs/2201.03545")[arxiv.org/abs/2201.03545]

*R2.* PyTorch / torchvision 0.22. ConvNeXt implementation.
#link("https://docs.pytorch.org/vision/0.22/_modules/torchvision/models/convnext.html")[Versioned ConvNeXt source]

*R3.* Ronneberger, Olaf, Philipp Fischer, and Thomas Brox. "U-Net: Convolutional Networks for Biomedical Image Segmentation." 2015.
#link("https://arxiv.org/abs/1505.04597")[arxiv.org/abs/1505.04597]

*R4.* PyTorch v2.7.1. `cross_entropy` implementation and API contract.
#link("https://github.com/pytorch/pytorch/blob/v2.7.1/torch/nn/functional.py")[torch/nn/functional.py]

*R5.* PyTorch v2.7.1. AdamW implementation; inherited update implementation in Adam.
#link("https://github.com/pytorch/pytorch/blob/v2.7.1/torch/optim/adamw.py")[adamw.py] and
#link("https://github.com/pytorch/pytorch/blob/v2.7.1/torch/optim/adam.py")[adam.py]

*R6.* Loshchilov, Ilya, and Frank Hutter. "Decoupled Weight Decay Regularization." 2017; ICLR 2019.
#link("https://arxiv.org/abs/1711.05101")[arxiv.org/abs/1711.05101]

*R7.* PyTorch v2.7.1. `CosineAnnealingLR` implementation.
#link("https://github.com/pytorch/pytorch/blob/v2.7.1/torch/optim/lr_scheduler.py")[torch/optim/lr_scheduler.py]

*R8.* Howard, Andrew, et al. "Searching for MobileNetV3." 2019.
#link("https://arxiv.org/abs/1905.02244")[arxiv.org/abs/1905.02244]

== Compact vocabulary
#small[
#table(columns: (1fr, 3.4fr),
  [*Encoder*], [Transforms pixels into progressively coarser, richer features.],
  [*Decoder*], [Combines and enlarges features to make spatial predictions.],
  [*Logit*], [A class score before softmax; may be negative or positive.],
  [*Parameter*], [A number learned by the optimizer, such as a kernel weight.],
  [*Hyperparameter*], [A configured choice, such as learning rate or batch size.],
  [*Gradient*], [A local derivative describing how loss changes with a parameter.],
  [*Batch / step*], [A group of examples / one optimizer update using that group.],
  [*Epoch*], [One traversal defined by the sampler, possibly with repeats.],
  [*Inference*], [Applying existing weights without training updates.],
  [*Pseudo-label*], [A generated training target whose correctness is not guaranteed.],
)]

#small[Source consultation and implementation snapshot: 21 November 2026. Links are primary papers or versioned source; local hashes preserve which project code this document describes.]
