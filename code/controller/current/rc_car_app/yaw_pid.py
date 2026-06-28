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
        """Latest filtered yaw rate (deg/s). 0.0 until the first sample."""
        with self.lock:
            return self._yaw

    def is_fresh(self, max_age_sec=0.5):
        with self.lock:
            return self._ok and (time.time() - self._last_rx) < max_age_sec


class YawController:
    """PID on yaw rate. compute() returns the logical servo angle to actually send."""

    def __init__(self, mode="off", kp=0.30, ki=0.05, kd=0.02,
                 ff_shift_deg=20.0, turn_gain_curv_per_deg=-0.66,
                 out_clamp_deg=25.0, integral_clamp=200.0,
                 straight_band_deg=20.0, min_speed_mps=0.2,
                 center_deg=90.0, actuation_range_deg=180.0):
        self.mode = mode
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.ff_shift = ff_shift_deg
        self.turn_gain = turn_gain_curv_per_deg
        self.out_clamp = out_clamp_deg
        self.i_clamp = integral_clamp
        self.straight_band = straight_band_deg
        self.min_speed = min_speed_mps
        self.center = center_deg
        self.range = actuation_range_deg
        self._integral = 0.0
        self._prev_error = None
        self.engaged = False          # for telemetry / dashboard
        self.last_target_yaw = 0.0
        self.last_correction = 0.0

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

        if self.mode == "straight":
            # only hold near center; let real turns pass through untouched
            if abs(commanded_deg - self.center) > self.straight_band:
                self.reset()
                return commanded_deg
            target_yaw = 0.0
            ff = self.center + self.ff_shift
        else:  # "full"
            target_curv = self.turn_gain * (commanded_deg - self.center)   # deg/m (sign in turn_gain)
            target_yaw = target_curv * speed_mps                            # deg/s
            ff = commanded_deg + self.ff_shift

        error = measured_yaw_dps - target_yaw          # + = too far left -> raise servo (steer right)
        self._integral = _clamp(self._integral + error * dt, -self.i_clamp, self.i_clamp)
        if self._prev_error is None or dt <= 0.0:
            deriv = 0.0
        else:
            deriv = (error - self._prev_error) / dt
        self._prev_error = error

        out = _clamp(self.kp * error + self.ki * self._integral + self.kd * deriv,
                     -self.out_clamp, self.out_clamp)
        self.engaged = True
        self.last_target_yaw = target_yaw
        self.last_correction = out
        return _clamp(ff + out, 0.0, self.range)
