# Controller Mapping

The car is driven and fully operated from an **Xbox Wireless Controller** over `pygame`.
This page is the single source of truth for every button, trigger, stick, and D-pad action.

## How it works

`runtime.py` reads `pygame` joystick events every loop (`pygame.event.get()`) and
dispatches axis, button, and hat (D-pad) events to driving, gearing, autonomy, photo
capture, navigation, turn signals, and dashboard paging. Every button and axis index is
a named constant in `config.py`, so the physical layout and the dispatch code stay in
sync. The values below are read straight from `config.py` and the event handler in
`run()`.

## Controller map (image)

![Controller map](../exhibits/media/RC_Car_Controls_xbox.png)

## Sticks and triggers

| Physical input | pygame axis | Constant | Action |
|---|---|---|---|
| Left stick X | `0` | `STEERING_AXIS` | Steering; deadzone `abs(v) < 0.10` snaps to center |
| Right stick Y | `3` | `DASHBOARD_PAGE_AXIS` | Dashboard: move page up/down (threshold `0.65`) |
| Right stick X | `2` | `DASHBOARD_PAGE_HORIZONTAL_AXIS` | Dashboard: move page column left/right (threshold `0.65`) |
| Right trigger | `4` | `THROTTLE_AXIS` | Throttle (normalized to `0..1`) |
| Left trigger | `5` | `BRAKE_AXIS` | Brake (`brake` engages above `0.1`) |

Qualifying manual steering, throttle, or brake input while autonomy is on calls the cancel
path when that input is processed by the Pi loop. A timed worst-case override latency has
not yet been measured.

## Buttons

Indices below are the `config.py` constants; the physical Xbox label is the mapping
observed on this controller.

| Physical button | pygame index | Constant | Action |
|---|---|---|---|
| A | `0` | `AUTONOMY_TOGGLE_BUTTON` | Toggle autonomous driving (forces gear D on) |
| B | `1` | `PHOTO_BUTTON` | Take a single photo (`take_photo`) |
| Menu | `11` | `AUTO_PHOTO_BUTTON` | Toggle continuous run capture at the configured 10 fps while moving |
| View | `10` | `HAZARD_BUTTON` | Toggle hazard lights |
| — | `4` | `CRUISE_TOGGLE_BUTTONS` | Cruise-control toggle (only in gear D) |
| LB | `6` | `SHIFT_DOWN_BUTTON` | Shift down (P←R←N←D) |
| RB | `7` | `SHIFT_UP_BUTTON` | Shift up (P→R→N→D) |
| RSB (right stick click) | `14` | `AEB_TOGGLE_BUTTON` | Toggle Automatic Emergency Braking |
| X | `3` | `NAV_SELECT_BUTTON` | Jump to NAVIGATE page (page 5); advance/confirm entry; start or cancel a route |
| Share | `15` | `QUIT_BUTTON` | Quit (sets shutdown flag) |

## D-pad (hat)

| Input | Action |
|---|---|
| D-pad ← / → | Left / right turn indicator toggle; on the NAVIGATE page (5) it also moves the entry cursor |
| D-pad ↑ / ↓ | Context action: edit the nav entry on page 5, cycle the steering model on page 2, or adjust cruise target speed / dashboard brightness elsewhere. Holding repeats after `DPAD_SCROLL_REPEAT_START_SEC` (0.6 s) at `DPAD_SCROLL_REPEAT_INTERVAL_SEC` (0.22 s) |

## Notes

- These are the indices as they exist in the code today. If `config.py` button constants
  change, this table is the place to re-verify against `run()`'s event handler.
- Physical labels (A/B/X/Y) reflect how this Xbox controller enumerates under pygame on
  the Pi; the code keys off the numeric index, not the label.

## Related pages

- `runtime-code/runtime-loop.md`
- `runtime-code/prnd-gears.md`
- `runtime-code/config/build-flags.md`
