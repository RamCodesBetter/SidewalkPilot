// Standalone companion. Compile with: typst compile sidewalkpilot-layer-shapes.typ
#let ink = rgb("193b38")
#let blue = rgb("235b83")
#let muted = rgb("57616b")
#set document(title: "SidewalkPilot: One Neuron, One Layer", author: "SidewalkPilot project; AI-assisted explanation")
#set page(paper: "us-letter", margin: (x: 0.68in, top: 0.65in, bottom: 0.65in),
  header: text(size: 8pt, fill: muted)[SIDEWALKPILOT / MATRIX SHAPES],
  footer: context align(right, text(size: 8pt, fill: muted)[22 NOV 2026 #h(12pt) #counter(page).display("1")]))
#set text(font: "New Computer Modern", size: 11pt, lang: "en")
#show math.equation: set text(font: "New Computer Modern Math")
#set par(leading: 0.52em, spacing: 0.65em)
#set heading(numbering: none)
#show heading.where(level: 1): set text(size: 21pt, fill: ink)
#show heading.where(level: 2): set text(size: 12pt, fill: blue)
#show raw: set text(size: 9pt)
#set table(inset: (x: 6pt, y: 5pt), stroke: none, align: left)
#let note(body) = block(width: 100%, inset: 9pt, fill: rgb("edf4f3"), body)

= One neuron, one layer
*The neuron equation is one entry of a larger tensor calculation.*

== 1. Compute all outputs together
A fully connected layer takes 128 input features and produces 64 outputs for each example. Process a *batch of 8 examples* together. In PyTorch's row-per-example convention:

#table(columns: (0.55fr, 0.9fr, 2.2fr),
  table.hline(stroke: 0.6pt + ink),
  table.header([*Tensor*], [*Shape*], [*Meaning*]),
  table.hline(stroke: 0.4pt + muted),
  [$X$], [$8 times 128$], [One row per example; one column per input feature.],
  [$W$], [$64 times 128$], [One row of learned weights per output neuron.],
  [$b$], [$64$], [One learned bias per output neuron.],
  [$Z$], [$8 times 64$], [One row per example; one column per output neuron.],
  table.hline(stroke: 0.4pt + muted),
)

$ Z = X W^upright(T) + b $

$ underbrace(X, 8 times 128) quad dot quad underbrace(W^upright(T), 128 times 64)
  = underbrace(X W^upright(T), 8 times 64) $

The superscript $upright(T)$ means *transpose*: swap rows and columns, not raise entries to a power. The inner sizes (128 and 128) must match; the outer sizes (8 and 64) give the result's shape. Matrix multiplication is *not* entry-by-entry multiplication.

The stored bias has shape `[64]`. It is *broadcast* across the batch: each row receives the same 64 biases. Broadcasting does not create eight separately learned bias vectors.

== 2. Zoom into one neuron for one example
$ Z_(n,j) = sum_(i=1)^128 X_(n,i) W_(j,i) + b_j $

Here $n$ selects one of the 8 examples; $j$ selects one of the 64 output neurons; $i$ runs over the 128 input features. Multiply the matching input/weight entries, sum the 128 products, and add that neuron's bias *once*.

This layer has $64 times 128 + 64 = 8,256$ learned parameters, regardless of batch size. The batch does not mix different examples together in this operation.

== 3. Apply the activation to the whole tensor
$ A = "GELU"(Z), quad A_(n,j) = "GELU"(Z_(n,j)) $

$A$ still has shape $8 times 64$. One tensor operation applies GELU independently to every entry. The weighted sum mixes features; the activation transforms each resulting number. Efficient kernels handle many operations together, not one Python call per neuron.

#note[*Why do some books write $z=W x+b$?* They use one example as a column: $x$ is $128 times 1$, so $W x$ is $64 times 1$. Our batched convention stores examples as rows, giving $Z=X W^upright(T)+b$. These express the same weighted sums.]

#pagebreak()
= Trace a small example
*Two examples, two input features, two output neurons.*

== 4. Matrix multiplication and bias, with numbers
$ X = mat(0.2, 0.8; 1, 0), quad
  W = mat(1.5, -0.5; -1, 1), quad
  b = mat(0.3, -0.1). $

Here the two rows of $X$ are two different examples. We display $b$ as a row to show how it is added; PyTorch stores it as a one-dimensional vector of length 2.

$ W^upright(T) = mat(1.5, -1; -0.5, 1), quad
  X W^upright(T) = mat(-0.1, 0.6; 1.5, -1) $

$ Z = underbrace(mat(-0.1, 0.6; 1.5, -1), "weighted sums")
  + underbrace(mat(0.3, -0.1; 0.3, -0.1), "same bias on each row")
  = mat(0.2, 0.5; 1.8, -1.1). $

For example, the first entry is $Z_(1,1)=0.2(1.5)+0.8(-0.5)+0.3=0.2$. The second example uses the *same* weights and biases, but its different inputs produce $[1.8,-1.1]$.

Applying GELU entry by entry gives approximately:

$ A = "GELU"(Z) approx mat(0.1159, 0.3457; 1.7353, -0.1492). $

GELU changes the values, not the $2 times 2$ shape. It adds no learned weights or biases of its own. The numerical values here are illustrative, not measurements of the trained SidewalkPilot model.

== 5. How this appears in 5.C's convolutional head
A convolutional layer keeps spatial axes. Before 5.C's final $1 times 1$ head, the feature tensor has 32 channels. The head produces two logits per spatial position:

$ underbrace([N,32,135,240], "batch, channels, height, width")
  arrow.r^("1 x 1 head")
  underbrace([N,2,135,240], "background and sidewalk scores") $

At each location $(h,w)$ in example $n$, the head applies a small dense transformation:

$ Z_(n,o,h,w) = sum_(c=1)^32 K_(o,c,1,1) F_(n,c,h,w) + b_o. $

$F$ is the input feature tensor, $K$ the kernel, $c$ the input-channel index, and $o$ one of the two output-channel indices. This formula uses one-based indices; code uses zero-based indices. The stored weights have shape `[2, 32, 1, 1]`, plus two biases: *66 parameters shared across every position and every example*.

The $1 times 1$ head mixes channels at one position, not neighboring positions. Earlier $3 times 3$ convolutions also combine neighboring positions. A convolution is therefore not generally just multiplication of the raw image matrix by one small matrix.

#note[*Important:* the final head returns raw logits, with *no GELU after the head*. 5.C then resizes the two logit maps to $540 times 960$. GELU is used inside its hidden encoder/decoder blocks.]

#text(size: 8.5pt, fill: muted)[
Code anchor: `series_5/tools/models/convnext_tiny_unet.py` (`UNetDecoder.head`). Shapes match the architecture guide. Companion source is standalone Typst with native mathematical typesetting.
]
