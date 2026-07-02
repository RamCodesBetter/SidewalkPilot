"""yaw_pid.py — closed-loop steering from the MG24 IMU yaw rate.

Two pieces:
  * ImuReader      — background thread that reads the MG24 gyro CSV on a serial
                     port (default /dev/ttyAMA3), filters the yaw axis, exposes
                     the latest filtered yaw rate (deg/s, + = turning LEFT).
  * YawController  — turns a commanded logical steering angle (0..180) into the
                     angle to ACTUALLY send, by closing a PID loop on yaw rate.

Modes (set STEERING_YAW_PID_MODE in config):
  "off"      -> passthrough: returns the commanded angle unchanged (exact baseline).
  "straight" -> only acts near center: holds yaw=0 when you command ~90; turns pass through.
  "full"     -> always acts: maps (commanded-90) to a target yaw rate (via the measured
                curvature slope x speed) and drives the servo to track it on straights AND turns.

Sign convention: with the runtime yaw sign, measured yaw + = RIGHT rotation, - = LEFT.
Standard PID error = target - measured: a LEFT drift (measured negative) yields a
POSITIVE error -> INCREASE the servo (steer right) to counter it; a RIGHT drift yields
a negative error -> steer left. Negative feedback: the correction always OPPOSES the yaw.
"""

import collections
import threading
import time

try:
    import serial  # pyserial
except ImportError:  # pragma: no cover - runtime import guard
    serial = None


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class ImuReader:
    """Background reader for the MG24 gyro stream `gx,gy,gz` (deg/s, bias-corrected
    by the firmware). Mirrors the LidarParser/GpsReader thread pattern."""

    def __init__(self, port="/dev/ttyAMA3", baud=115200, axis=2, sign=1.0, median=5, ema=0.3):
        self.port = port
        self.baud = baud
        self.axis = axis
        self.sign = float(sign)   # flips raw gyro so the controller sees + = LEFT
        self._median_n = max(1, int(median))
        self._ema_a = float(ema)
        self._med = collections.deque(maxlen=self._median_n)
        self._ema = 0.0
        self._yaw = 0.0
        self._bias = 0.0          # residual gyro zero-offset, learned while stopped
        self._ok = False
        self._last_rx = 0.0
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def start(self):
        if serial is None:
            print("IMU disabled: pyserial unavailable.")
            return False
        if self.running:
            return True
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.2)
        except Exception as exc:
            print(f"IMU disabled: failed to open {self.port}: {exc}")
            self.running = False
            return
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        while self.running:
            try:
                line = ser.readline().decode("utf-8", "ignore").strip()
                if not line or line == "READY" or line.startswith("ERR"):
                    continue
                parts = line.split(",")
                if len(parts) != 3:
                    continue
                try:
                    raw = float(parts[self.axis]) * self.sign
                except (ValueError, IndexError):
                    continue
                self._med.append(raw)
                s = sorted(self._med)
                m = s[len(s) // 2]
                self._ema = self._ema_a * m + (1.0 - self._ema_a) * self._ema
                with self.lock:
                    self._yaw = self._ema
                    self._ok = True
                    self._last_rx = time.time()
            except Exception:
                time.sleep(0.02)
        try:
            ser.close()
        except Exception:
            pass

    def get_yaw(self):
        """Latest filtered yaw rate (deg/s), residual-bias corrected. + = LEFT."""
        with self.lock:
            return self._yaw - self._bias

    def note_stationary(self):
        """Call each loop while the car is KNOWN to be stopped: the true yaw is 0,
        so slowly pull the bias toward the current reading. Cancels the residual
        gyro zero-offset (e.g. the -2.2 dps the firmware bias-cal left behind) WITHOUT
        a deadband, so small real turn rates still come through while driving."""
        with self.lock:
            self._bias = 0.98 * self._bias + 0.02 * self._yaw

    def is_fresh(self, max_age_sec=0.5):
        with self.lock:
            return self._ok and (time.time() - self._last_rx) < max_age_sec


class YawController:
    """PID on yaw rate. compute() returns the logical servo angle to actually send."""

    def __init__(self, mode="off", kp=0.0, ki=0.0, kd=0.0,
                 curvature_coeffs=(0.0,), f_left_bump_deg=0.0,
                 straight_band_deg=5.0, min_speed_mps=0.2,
                 center_deg=90.0, actuation_range_deg=180.0,
                 side_dwell_sec=0.12):
        self.mode = mode
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.curv_coeffs = tuple(curvature_coeffs)   # curvature(x) quartic, ascending powers
        self.f_left_bump = f_left_bump_deg           # added to F when last steer was LEFT (hysteresis)
        self.side_dwell_sec = side_dwell_sec         # stick must dwell on a side this long to count (anti-flick)
        self.straight_band = straight_band_deg
        self.min_speed = min_speed_mps
        self.center = center_deg
        self.range = actuation_range_deg
        self._integral = 0.0
        self._prev_error = None
        self._last_side = 1           # +1 = last steered right, -1 = left (wheel seating)
        self._cand_side = 0           # side currently being held, pending the dwell
        self._cand_dwell = 0.0        # seconds the candidate side has persisted
        self.engaged = False          # for telemetry / dashboard
        self.last_target_yaw = 0.0
        self.last_correction = 0.0
        # F = the open-loop straight angle = where curvature(x) crosses 0 (~109).
        self.ff_center = self._solve_center()

    def _curvature(self, x):
        """Predicted curvature (deg/m) at servo angle x, from the calib quartic."""
        y = 0.0
        for i, c in enumerate(self.curv_coeffs):
            y += c * (x ** i)
        return y

    def _solve_center(self):
        """Root of curvature(x)=0 in [0, range] -> the feed-forward straight angle."""
        step = 0.5
        prev_x = 0.0
        prev_y = self._curvature(prev_x)
        x = step
        while x <= self.range:
            y = self._curvature(x)
            if (prev_y <= 0.0 <= y) or (y <= 0.0 <= prev_y):
                return prev_x if y == prev_y else prev_x + (0.0 - prev_y) * (x - prev_x) / (y - prev_y)
            prev_x, prev_y = x, y
            x += step
        return self.center   # no root in range -> fall back to geometric center

    def reset(self):
        self._integral = 0.0
        self._prev_error = None
        self.engaged = False
        self.last_correction = 0.0

    def compute(self, commanded_deg, measured_yaw_dps, speed_mps, dt, allow=True):
        """commanded_deg: model/joystick logical target (0..180).
        measured_yaw_dps: filtered yaw rate (+ = right). speed_mps: forward speed.
        allow: external gate (autonomous-or-active-steering, no AEB/override/fault).
        Returns the logical angle to send to the servo."""
        # Off / reverse / lidar-override -> exact passthrough (no F at all).
        if self.mode == "off" or not allow:
            self.reset()
            return commanded_deg

        # Remember which way we last steered (wheel seating) for the hysteresis F.
        # Persists across the straight hold + brief stops; only a real turn changes it.
        # A side must DWELL past side_dwell_sec before it counts, so a flick / spring-back
        # that briefly overshoots center to the far side can't flip _last_side (which
        # would apply the wrong F and read 109<->119 backwards on release).
        if commanded_deg > self.center + self.straight_band:
            side = 1                # right
        elif commanded_deg < self.center - self.straight_band:
            side = -1               # left
        else:
            side = 0                # near center: keep whatever we last committed
        if side == 0:
            self._cand_side = 0
            self._cand_dwell = 0.0
        else:
            if side == self._cand_side:
                self._cand_dwell += max(0.0, dt)
            else:
                self._cand_side = side
                self._cand_dwell = 0.0
            if self._cand_dwell >= self.side_dwell_sec:
                self._last_side = side

        # FEED-FORWARD (F): start from the calibrated open-loop angle, PID only trims.
        if self.mode == "straight":
            # only hold near center; let real turns pass through untouched
            if abs(commanded_deg - self.center) > self.straight_band:
                self.reset()
                return commanded_deg
            target_yaw = 0.0
            # right keeps the curvature root (~109); left bumps up to the higher
            # left-approach center (~119) to cancel the hysteresis.
            ff_servo = self.ff_center + (self.f_left_bump if self._last_side < 0 else 0.0)
        else:  # "full" -- shift the stick into the calibrated frame, read target off curvature(x)
            ff_servo = _clamp(commanded_deg + (self.ff_center - self.center), 0.0, self.range)
            target_yaw = self._curvature(ff_servo) * speed_mps          # deg/s the car should rotate

        # Below the engage speed: PRE-POSITION the wheels at F (so there's no left
        # lurch on launch) but DON'T run the PID -- yaw is meaningless near-standstill,
        # and the integral must not wind while stopped.
        if speed_mps < self.min_speed:
            self.reset()
            self.last_target_yaw = target_yaw
            return _clamp(ff_servo, 0.0, self.range)

        error = target_yaw - measured_yaw_dps          # + = yawing left of target -> raise servo (steer right)
        self._integral = self._integral + error * dt   # NO clamp -- infinite control
        if self._prev_error is None or dt <= 0.0:
            deriv = 0.0
        else:
            deriv = (error - self._prev_error) / dt
        self._prev_error = error

        out = self.kp * error + self.ki * self._integral + self.kd * deriv  # PID trim (no clamp)
        self.engaged = True
        self.last_target_yaw = target_yaw
        self.last_correction = out
        return _clamp(ff_servo + out, 0.0, self.range)
