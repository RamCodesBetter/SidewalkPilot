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

Sign convention (from imu_steering_calibrate.py data): low servo = LEFT = +yaw,
high servo = RIGHT = -yaw. To correct a left drift (measured yaw too positive) we
INCREASE the servo angle (steer right) -> error = measured - target, added to servo.
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

    def __init__(self, port="/dev/ttyAMA3", baud=115200, axis=2, median=5, ema=0.3):
        self.port = port
        self.baud = baud
        self.axis = axis
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
                    raw = float(parts[self.axis])
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
                 curvature_coeffs=(0.0,),
                 straight_band_deg=5.0, min_speed_mps=0.2,
                 center_deg=90.0, actuation_range_deg=180.0):
        self.mode = mode
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.curv_coeffs = tuple(curvature_coeffs)   # curvature(x) quartic, ascending powers
        self.straight_band = straight_band_deg
        self.min_speed = min_speed_mps
        self.center = center_deg
        self.range = actuation_range_deg
        self._integral = 0.0
        self._prev_error = None
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
        measured_yaw_dps: filtered yaw rate (+ = left). speed_mps: forward speed.
        allow: external gate (autonomous-or-active-steering, no AEB/override/fault).
        Returns the logical angle to send to the servo."""
        # Disengaged -> exact passthrough so "off" is a true revert.
        if self.mode == "off" or not allow or speed_mps < self.min_speed:
            self.reset()
            return commanded_deg

        # FEED-FORWARD (F): start from the calibrated open-loop angle, PID only trims.
        if self.mode == "straight":
            # only hold near center; let real turns pass through untouched
            if abs(commanded_deg - self.center) > self.straight_band:
                self.reset()
                return commanded_deg
            target_yaw = 0.0
            ff_servo = self.ff_center                                   # ~109 = straight
        else:  # "full" -- shift the stick into the calibrated frame, read target off curvature(x)
            ff_servo = _clamp(commanded_deg + (self.ff_center - self.center), 0.0, self.range)
            target_yaw = self._curvature(ff_servo) * speed_mps          # deg/s the car should rotate

        error = measured_yaw_dps - target_yaw          # + = too far left -> raise servo (steer right)
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
