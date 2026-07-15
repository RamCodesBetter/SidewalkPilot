import RPi.GPIO as GPIO
import time

# Set up GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.OUT)

# Set up PWM on GPIO18 at 1000Hz
pwm = GPIO.PWM(21, 440)
pwm.start(100)  # 50% duty cycle

try:
    time.sleep(2)  # Play tone for 2 seconds
finally:
    pwm.stop()
    GPIO.cleanup()