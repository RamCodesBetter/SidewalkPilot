# Turn Penalty State

Turn Penalty State explains why the A* router searches over `(previous node, current node)` pairs instead of single nodes, and how that lets it charge a cost for sharp bends. The logic lives in `code/controller/current/rc_car_app/navigation.py` (`turn_amount`, `turn_penalty`, and the state tuple inside `astar`).

## How it works

A plain shortest-path search only knows *where it is*, so it cannot tell whether arriving at a node continued straight or hooked a hard turn. SidewalkPilot makes the search state a `(prev_id, current_id)` tuple, so at every expansion it knows the three points `prev -> current -> next` and can measure the bend between them.

- **Turn magnitude.** `turn_amount(prev, current, next)` takes the geographic `bearing` of the incoming leg (`prev -> current`) and the outgoing leg (`current -> next`), then returns `abs((after - before + 540) % 360 - 180)`. The `+540 ... % 360 - 180` wrap folds the difference into `[0, 180]` degrees so a left and right turn of the same sharpness cost the same, and there is no discontinuity at the 0/360 seam.
- **Penalty ladder.** `turn_penalty` converts that angle into extra cost added to `g` for that leg. It returns `0` for the first hop (no `prev`) and for gentle changes, then steps up for sharper turns:

  | Turn magnitude (deg) | Added cost |
  |---|---|
  | `< 25` | `0` |
  | `25 - 45` | `3` |
  | `45 - 90` | `10` |
  | `90 - 135` | `24` |
  | `>= 135` | `44` |

- **Where it enters the search.** Inside `astar`, the neighbor cost is `new_cost = cost_so_far[state] + step_cost + turn_penalty(nodes, prev_id, current, nxt)`. The penalty is part of `g` (the accumulated real cost), never part of the heuristic `h`, so A* stays admissible and optimal.

| Concept field | Value in this project |
|---|---|
| Input | Three node coordinates `prev`, `current`, `next` (lat/lon) |
| Intermediate | `turn_amount` in degrees, folded to `[0, 180]` |
| Output | Additive path cost in the same metre-scale units as edge cost |
| Runtime use | `turn_penalty` called per neighbor inside `astar` in `navigation.py` |
| State carrier | `(prev_id, current_id)` tuple used as the A* node key |

## Why this choice

Two routes can be nearly the same length but very different to drive: one runs straight down a sidewalk, the other zig-zags across corners and crossings. Because the penalty is expressed in the same units as distance, a `>= 135` degree switchback costs the router an extra 44 "metres," so a slightly longer but smoother path wins. That produces routes an Ackermann car can actually follow, and keeps the preference visible and tunable in one small table instead of hidden inside the model. Encoding it as search state (rather than post-processing the path) means the optimal path already accounts for turns rather than being patched afterward.

## Worked example

Suppose the router is at node C having come from B, and is deciding whether to go to D or E:

- `B -> C -> D` turns 20 deg. `turn_penalty = 0`. If leg `C -> D` is 30 m, its `g` contribution is `30 + 0 = 30`.
- `B -> C -> E` turns 100 deg (a hard corner). `turn_penalty = 24`. If leg `C -> E` is only 22 m, its `g` contribution is `22 + 24 = 46`.

Even though `C -> E` is physically shorter, the router prefers `C -> D` because the sharp corner is charged 24 extra units. If E were instead reached by a 55 deg turn, its penalty would drop to 10, and `22 + 10 = 32` would make the two routes nearly tied, which is the intended smooth-vs-short trade.

## What can go wrong

- **State blow-up.** Keying on `(prev, current)` multiplies the state space by node degree. On the Trossachs graph this is fine, but on a very dense graph it would grow memory and search time.
- **Angle wrap bug.** If the `+540 ... % 360 - 180` fold were dropped, turns near the 0/360 bearing seam would be mis-measured (for example a 350 deg vs 10 deg pair should be a 20 deg turn, not 340). The fold is what keeps that correct.
- **Penalty mis-scaling.** Because the penalty is in metre units, changing edge distances without revisiting the ladder could make turns feel too cheap or too expensive relative to distance.

## Related pages

- `research-and-math/machine-learning/regression-framing.md`
- `ai-and-models/training-pipeline/overview.md`
- `autonomy-stack/navigation/overview.md`
