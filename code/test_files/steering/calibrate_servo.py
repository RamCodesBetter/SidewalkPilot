import pygame
import time
import sys

try:
    import board
    import busio
    from adafruit_servokit import ServoKit
except Exception:
    board = None
    busio = None
    ServoKit = None

try:
    from gpiozero import Servo
except Exception:
    Servo = None

# --- GPIO SETUP ---
# Ensure this matches the pin used for your steering servo in rc_car copy.py
STEERING_SERVO_PIN = 12
USE_PCA9685_SERVO = True
PCA9685_I2C_ADDRESS = 0x40
PCA9685_SERVO_CHANNEL = 0
PCA9685_FREQUENCY_HZ = 50
SERVO_MIN_PULSE_US = 1000
SERVO_MAX_PULSE_US = 2000
SERVO_ACTUATION_RANGE_DEG = 180

# --- SERVO CALIBRATION SETTINGS ---
# Initial offset. You will adjust this with A and D keys.
servo_center_offset = 0.0
# The amount     to adjust the servo position by with each key press
ADJUSTMENT_STEP = 0.01

# --- PYGAME INITIALIZATION ---
pygame.init()
pygame.display.set_mode((300, 100)) # Create a small window for event processing
pygame.display.set_caption("Servo Calibration")

print("Servo Calibration Tool")
print("Press 'A' to increase servo offset (+0.001)")
print("Press 'D' to decrease servo offset (-0.001)")
print("Press 'Q' to quit")
print("-" * 30)

# --- SERVO INITIALIZATION ---
class DummyServo:
    def __init__(self, *args, **kwargs):
        self.value = 0.0

    def close(self):
        pass


class PCA9685CalServo:
    def __init__(self, address, channel, frequency_hz, min_pulse_us, max_pulse_us, actuation_range_deg):
        if ServoKit is None or busio is None or board is None:
            raise RuntimeError("PCA9685 servo dependencies are unavailable")
        self._i2c = busio.I2C(board.SCL, board.SDA)
        self._kit = ServoKit(channels=16, i2c=self._i2c, address=address, frequency=frequency_hz)
        self._servo = self._kit.servo[channel]
        self._servo.set_pulse_width_range(min_pulse_us, max_pulse_us)
        self._servo.actuation_range = actuation_range_deg
        self.value = 0.0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, raw_value):
        self._value = max(-1.0, min(1.0, float(raw_value)))
        self._servo.angle = ((self._value + 1.0) / 2.0) * self._servo.actuation_range

    def close(self):
        try:
            self._servo.angle = None
        except Exception:
            pass


servo = None
try:
    if USE_PCA9685_SERVO:
        servo = PCA9685CalServo(
            address=PCA9685_I2C_ADDRESS,
            channel=PCA9685_SERVO_CHANNEL,
            frequency_hz=PCA9685_FREQUENCY_HZ,
            min_pulse_us=SERVO_MIN_PULSE_US,
            max_pulse_us=SERVO_MAX_PULSE_US,
            actuation_range_deg=SERVO_ACTUATION_RANGE_DEG,
        )
        print(f"Servo initialized on PCA9685 0x{PCA9685_I2C_ADDRESS:02x} channel {PCA9685_SERVO_CHANNEL}.")
    else:
        if Servo is None:
            raise RuntimeError("gpiozero Servo is unavailable")
        servo = Servo(
            STEERING_SERVO_PIN,
            min_pulse_width=SERVO_MIN_PULSE_US / 1_000_000.0,
            max_pulse_width=SERVO_MAX_PULSE_US / 1_000_000.0,
            frame_width=20 / 1000,
        )
        print(f"Servo initialized on pin {STEERING_SERVO_PIN}.")
    # Set the servo to the initial offset
    servo.value = servo_center_offset
except Exception as e:
    print(f"Error initializing servo: {e}. Please ensure GPIO is available and correctly wired.")
    print("Running in simulation mode (no physical servo control).")
    servo = DummyServo() # Use a dummy servo if GPIO fails

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_a:
                servo_center_offset += ADJUSTMENT_STEP
                # Clamp the value between -1 and 1, which are the valid servo ranges
                servo_center_offset = max(-1.0, min(1.0, servo_center_offset))
                if servo:
                    servo.value = servo_center_offset
                print(f"Servo Offset: {servo_center_offset:.4f}")
            elif event.key == pygame.K_d:
                servo_center_offset -= ADJUSTMENT_STEP
                # Clamp the value between -1 and 1
                servo_center_offset = max(-1.0, min(1.0, servo_center_offset))
                if servo:
                    servo.value = servo_center_offset
                print(f"Servo Offset: {servo_center_offset:.4f}")
            elif event.key == pygame.K_q:
                running = False

    time.sleep(0.01) # Small delay to prevent busy-waiting

print("-" * 30)
print(f"Final Servo Offset found: {servo_center_offset:.4f}")
print("Exiting servo calibration tool.")

# --- CLEANUP ---
if servo:
    try:
        servo.value = 0 # Attempt to center the servo before closing
        time.sleep(0.05) # Give it a moment to move
        servo.close()
        print("Servo closed.")
    except Exception as e:
        print(f"Error during servo cleanup: {e}")

pygame.quit()
sys.exit(0)
