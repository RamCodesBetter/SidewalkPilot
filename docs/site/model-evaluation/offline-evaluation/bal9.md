# Bal9

Bal9 is the macro-average exact recall across the nine steering classes. It gives each class equal influence even when the dataset contains very different numbers of examples per class.

## Calculation

For class `i`:

```text
recall_i = correctly predicted examples whose target is class i
           ----------------------------------------------------
                    all examples whose target is class i
```

Then:

```text
Bal9 = 100 * (recall_HL + recall_L + recall_L+ + recall_SL
              + recall_ST + recall_SR + recall_R + recall_R+ + recall_HR) / 9
```

Only nonempty classes are averaged if an evaluation set is missing a class. The current challenge set contains all nine.

## Example

Suppose the nine recalls are:

```text
40%, 30%, 20%, 50%, 80%, 60%, 25%, 15%, 10%
```

Their sum is 330%; `330 / 9 = 36.7%`, so Bal9 is 36.7%.

This is not overall exact accuracy. If ST contains thousands of frames and HL contains tens, each still contributes exactly one ninth of Bal9. A model cannot earn a high Bal9 by predicting the majority class repeatedly.

## Related Metrics

- **ST exact:** recall of the ST class only, targets from 85 to 95 degrees.
- **Turn exact:** micro-averaged exact-bucket recall over every non-ST target.
- **Turn +/-1:** micro recall over non-ST targets where the predicted class may match or be one adjacent class away.

Bal9 is macro-averaged; turn metrics are micro-averaged over turn samples. Reading both shows whether capability is broadly distributed and whether the model handles turns in aggregate.

## Interpretation

`4.0p` currently leads the common report at 34.5%. That does not mean it is 34.5% “accurate at driving.” It means the average exact recall across nine discrete steering buckets is 34.5% on this challenge set. Continuous within-bucket offset error, closed-loop stability, and field behavior remain separate questions.
