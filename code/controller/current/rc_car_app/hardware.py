#!/usr/bin/python3
import errno
import time

from gpiozero import PWMOutputDevice, DigitalInputDevice, DigitalOutputDevice, Servo
try:
    from gpiozero.pins.lgpio import LGPIOFactory
except Exception:
    LGPIOFactory = None

try:
    import board
    import busio
    from adafruit_servokit import ServoKit
except Exception:
    board = None
    busio = None
    ServoKit = None

from .config import (
    ENABLE_HALL_SENSOR,
    HALL_SENSOR_GPIO_PIN,
    LIDAR_MOTOR_ENABLE_GPIO_PIN,
    MOTOR_LEFT_BWD_PIN,
    MOTOR_LEFT_FWD_PIN,
    MOTOR_RIGHT_BWD_PIN,
    MOTOR_RIGHT_FWD_PIN,
    PCA9685_FREQUENCY_HZ,
    PCA9685_I2C_ADDRESS,
    PCA9685_SERVO_CHANNEL,
    STEERING_SERVO_ACTUATION_RANGE_DEG,
    STEERING_SERVO_CENTER_OFFSET,
    STEERING_SERVO_CENTER_PRELOAD,
    STEERING_SERVO_CENTER_PRELOAD_WINDOW,
    STEERING_SERVO_MAX_PULSE_US,
    STEERING_SERVO_MIN_PULSE_US,
    STEERING_SERVO_PIN,
    STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG,
    STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG,
    USE_PCA9685_SERVO,
)


class DummyPWM:
    def __init__(self, *args, **kwargs):
        self.value = 0.0

    def close(self):
        pass


class DummyDigitalInput:
    def __init__(self, *args, **kwargs):
        self.value = 0
        self.when_activated = None
        self.when_deactivated = None

    def close(self):
        pass


class DummyDigitalOutput:
    def __init__(self, *args, **kwargs):
        self.value = 0

    def on(self):
        self.value = 1

    def off(self):
        self.value = 0

    def close(self):
        pass


class DummyServo:
    def __init__(self, *args, **kwargs):
        self.value = 0.0

    def close(self):
        pass


def logical_to_reference_steering_degrees(logical_angle_deg: float, actuation_range_deg: float) -> float:
    actuation_range = max(1.0, float(actuation_range_deg))
    center_angle = actuation_range / 2.0
    logical = max(0.0, min(actuation_range, float(logical_angle_deg)))
    left_limit = max(0.0, min(center_angle, float(STEERING_SERVO_REFERENCE_LEFT_LIMIT_DEG)))
    right_limit = max(center_angle, min(actuation_range, float(STEERING_SERVO_REFERENCE_RIGHT_LIMIT_DEG)))
    if logical <= center_angle:
        left_ratio = (center_angle - logical) / center_angle
        return center_angle - (left_ratio * (center_angle - left_limit))
    right_ratio = (logical - center_angle) / center_angle
    return center_angle + (right_ratio * (right_limit - center_angle))


def apply_steering_center_trim_degrees(
    logical_angle_deg: float,
    actuation_range_deg: float,
    center_offset: float,
    center_preload: float,
    center_preload_window: float,
) -> float:
    actuation_range = max(1.0, float(actuation_range_deg))
    center_angle = actuation_range / 2.0
    logical = max(0.0, min(actuation_range, float(logical_angle_deg)))
    centered = (logical - center_angle) / center_angle
    adjusted = logical_to_reference_steering_degrees(logical, actuation_range)
    adjusted += max(-1.0, min(1.0, center_offset)) * center_angle
    preload_window = max(0.0, float(center_preload_window))
    if preload_window > 0.0 and abs(centered) < preload_window:
        preload_scale = 1.0 - (abs(centered) / preload_window)
        adjusted += max(-1.0, min(1.0, center_preload)) * center_angle * preload_scale
    return max(0.0, min(actuation_range, adjusted))


class CenteredServoAdapter:
    def __init__(
        self,
        servo,
        center_offset: float = 0.0,
        center_preload: float = 0.0,
        center_preload_window: float = 0.0,
    ):
        self._servo = servo
        self._actuation_range_deg = float(STEERING_SERVO_ACTUATION_RANGE_DEG)
        self._center_offset = max(-1.0, min(1.0, center_offset))
        self._center_preload = max(-1.0, min(1.0, center_preload))
        self._center_preload_window = max(0.0, float(center_preload_window))
        self._value = self._actuation_range_deg / 2.0
        self.value = self._value

    @property
    def value(self):
        return self._value

    def set_center_offset(self, center_offset: float):
        self._center_offset = max(-1.0, min(1.0, float(center_offset)))
        self.value = self._value

    @value.setter
    def value(self, raw_value):
        clamped = max(0.0, min(self._actuation_range_deg, float(raw_value)))
        adjusted = apply_steering_center_trim_degrees(
            clamped,
            self._actuation_range_deg,
            self._center_offset,
            self._center_preload,
            self._center_preload_window,
        )
        self._servo.value = ((adjusted / self._actuation_range_deg) * 2.0) - 1.0
        self._value = clamped

    def close(self):
        self._servo.close()


class PCA9685SteeringServo:
    def __init__(
        self,
        channel: int,
        address: int,
        frequency_hz: int,
        min_pulse_us: int,
        max_pulse_us: int,
        actuation_range_deg: int,
        center_offset: float = 0.0,
        center_preload: float = 0.0,
        center_preload_window: float = 0.0,
    ):
        if ServoKit is None or busio is None or board is None:
            raise RuntimeError("PCA9685 servo dependencies are unavailable")
        self._i2c = busio.I2C(board.SCL, board.SDA)
        self._kit = ServoKit(channels=16, i2c=self._i2c, address=address, frequency=frequency_hz)
        self._servo = self._kit.servo[channel]
        self._servo.set_pulse_width_range(min_pulse_us, max_pulse_us)
        self._servo.actuation_range = actuation_range_deg
        self._center_offset = max(-1.0, min(1.0, center_offset))
        self._center_preload = max(-1.0, min(1.0, center_preload))
        self._center_preload_window = max(0.0, float(center_preload_window))
        self._value = self._servo.actuation_range / 2.0
        self.value = self._value

    @property
    def value(self):
        return self._value

    def set_center_offset(self, center_offset: float):
        self._center_offset = max(-1.0, min(1.0, float(center_offset)))
        self.value = self._value

    @value.setter
    def value(self, raw_value):
        clamped = max(0.0, min(float(self._servo.actuation_range), float(raw_value)))
        angle = apply_steering_center_trim_degrees(
            clamped,
            self._servo.actuation_range,
            self._center_offset,
            self._center_preload,
            self._center_preload_window,
        )
        self._servo.angle = angle
        self._value = clamped

    def close(self):
        try:
            self._servo.angle = None
        except Exception:
            pass


class Hardware:
    def __init__(self, pulse_callback):
        self.gpio_initialized = False
        self.pin_factory = None
        self.steering_servo = DummyServo()
        self.motor_left_fwd = DummyPWM()
        self.motor_left_bwd = DummyPWM()
        self.motor_right_fwd = DummyPWM()
        self.motor_right_bwd = DummyPWM()
        self.hall_sensor = DummyDigitalInput()
        self.lidar_motor_enable = DummyDigitalOutput()
        try:
            if USE_PCA9685_SERVO:
                self.steering_servo = self._init_device(
                    "PCA9685 steering servo",
                    PCA9685_SERVO_CHANNEL,
                    lambda: PCA9685SteeringServo(
                        channel=PCA9685_SERVO_CHANNEL,
                        address=PCA9685_I2C_ADDRESS,
                        frequency_hz=PCA9685_FREQUENCY_HZ,
                        min_pulse_us=STEERING_SERVO_MIN_PULSE_US,
                        max_pulse_us=STEERING_SERVO_MAX_PULSE_US,
                        actuation_range_deg=STEERING_SERVO_ACTUATION_RANGE_DEG,
                        center_offset=STEERING_SERVO_CENTER_OFFSET,
                        center_preload=STEERING_SERVO_CENTER_PRELOAD,
                        center_preload_window=STEERING_SERVO_CENTER_PRELOAD_WINDOW,
                    ),
                )
                print(
                    f"Using PCA9685 steering servo at 0x{PCA9685_I2C_ADDRESS:02x}, channel {PCA9685_SERVO_CHANNEL}."
                )
            else:
                if LGPIOFactory is not None:
                    try:
                        self.pin_factory = LGPIOFactory()
                        print("Using lgpio pin factory for servo PWM.")
                    except Exception as e:
                        print(f"lgpio unavailable, falling back to default PWM: {e}")

                servo_kwargs = {
                    "pin": STEERING_SERVO_PIN,
                    "min_pulse_width": STEERING_SERVO_MIN_PULSE_US / 1_000_000.0,
                    "max_pulse_width": STEERING_SERVO_MAX_PULSE_US / 1_000_000.0,
                    "frame_width": 20 / 1000,
                }
                if self.pin_factory is not None:
                    servo_kwargs["pin_factory"] = self.pin_factory
                self.steering_servo = self._init_device(
                    "steering servo",
                    STEERING_SERVO_PIN,
                    lambda: CenteredServoAdapter(
                        Servo(**servo_kwargs),
                        center_offset=STEERING_SERVO_CENTER_OFFSET,
                        center_preload=STEERING_SERVO_CENTER_PRELOAD,
                        center_preload_window=STEERING_SERVO_CENTER_PRELOAD_WINDOW,
                    ),
                )
            self.motor_left_fwd = self._init_pwm("left motor forward", MOTOR_LEFT_FWD_PIN)
            self.motor_left_bwd = self._init_pwm("left motor backward", MOTOR_LEFT_BWD_PIN)
            self.motor_right_fwd = self._init_pwm("right motor forward", MOTOR_RIGHT_FWD_PIN)
            self.motor_right_bwd = self._init_pwm("right motor backward", MOTOR_RIGHT_BWD_PIN)
            self.lidar_motor_enable = self._init_device(
                "LiDAR motor enable",
                f"GPIO {LIDAR_MOTOR_ENABLE_GPIO_PIN}",
                lambda: DigitalOutputDevice(LIDAR_MOTOR_ENABLE_GPIO_PIN, active_high=True, initial_value=True),
            )
            self.lidar_motor_enable.on()
            print(f"LiDAR motor enable set high on GPIO {LIDAR_MOTOR_ENABLE_GPIO_PIN}.")

            if ENABLE_HALL_SENSOR:
                self.hall_sensor = self._init_device(
                    "hall sensor",
                    HALL_SENSOR_GPIO_PIN,
                    lambda: DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True),
                )
                self.hall_sensor.when_activated = pulse_callback
                self.hall_sensor.when_deactivated = pulse_callback
            else:
                self.hall_sensor = DummyDigitalInput()

            self.gpio_initialized = True
            print("GPIO devices initialized successfully.")
        except Exception as e:
            print(f"Error initializing GPIO: {e}. Running in simulation mode.")
            self.cleanup()
            self.steering_servo = DummyServo()
            self.motor_left_fwd = DummyPWM()
            self.motor_left_bwd = DummyPWM()
            self.motor_right_fwd = DummyPWM()
            self.motor_right_bwd = DummyPWM()
            self.hall_sensor = DummyDigitalInput()
            self.lidar_motor_enable = DummyDigitalOutput()

    def _init_device(self, label, pin, factory):
        last_exc = None
        for attempt in range(4):
            try:
                return factory()
            except Exception as exc:
                last_exc = exc
                is_temporarily_busy = (
                    getattr(exc, "errno", None) == errno.EAGAIN
                    or "Resource temporarily unavailable" in str(exc)
                )
                if not is_temporarily_busy or attempt == 3:
                    break
                time.sleep(0.25)
        raise RuntimeError(f"{label} on {pin} failed: {last_exc}") from last_exc

    def _init_pwm(self, label, pin):
        return self._init_device(
            label,
            f"GPIO {pin}",
            lambda: PWMOutputDevice(pin, frequency=1000, initial_value=0),
        )

    def cleanup(self):
        for device in [
            self.motor_left_fwd,
            self.motor_left_bwd,
            self.motor_right_fwd,
            self.motor_right_bwd,
        ]:
            try:
                device.value = 0
                device.close()
            except Exception:
                pass
        for device in [self.hall_sensor]:
            try:
                device.close()
            except Exception:
                pass
        try:
            self.lidar_motor_enable.off()
            self.lidar_motor_enable.close()
        except Exception:
            pass
        try:
            self.steering_servo.value = STEERING_SERVO_ACTUATION_RANGE_DEG / 2.0
            time.sleep(0.05)
            self.steering_servo.close()
        except Exception:
            pass
