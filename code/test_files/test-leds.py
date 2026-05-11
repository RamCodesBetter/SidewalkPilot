import RPi.GPIO as GPIO
import time

# Set up GPIO
GPIO.setmode(GPIO.BCM)
led_pins = [4, 17, 18, 26]
for pin in led_pins:
    GPIO.setup(pin, GPIO.OUT)

# Blink LEDs
try:
    while True:
        for pin in led_pins:
            GPIO.output(pin, True)
            time.sleep(0.5)
            GPIO.output(pin, False)
except KeyboardInterrupt:
    GPIO.cleanup()