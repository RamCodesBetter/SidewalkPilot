#!/usr/bin/env python3

from gpiozero import DigitalInputDevice
import time
import signal
import sys

# --- Configuration ---
HALL_SENSOR_GPIO_PIN = 24 # The GPIO pin you connected E1A to

pulse_count = 0
last_state = 0 # To detect rising/falling edge, depending on sensor behavior

def sensor_changed_state():
    """Callback function for when the sensor state changes."""
    global pulse_count
    pulse_count += 1
    # print(f"Pulse detected! Total pulses: {pulse_count}") # Uncomment for verbose debugging

def cleanup_gpio(signum, frame):
    """Graceful shutdown for GPIO."""
    print("\nCleaning up GPIO...")
    if 'hall_sensor' in globals() and hasattr(hall_sensor, 'close'):
        hall_sensor.close()
    print("GPIO cleaned up. Exiting.")
    sys.exit(0)

# Register signal handler for graceful exit on Ctrl+C
signal.signal(signal.SIGINT, cleanup_gpio)

print(f"Initializing Hall sensor on GPIO {HALL_SENSOR_GPIO_PIN}...")
try:
    # Use pull_up=True if the sensor pulls the line low when active (common)
    # If your sensor is active-high, you might need pull_up=False or no pull_up
    hall_sensor = DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True)
    print(f"Hall sensor initialized. Current state: {hall_sensor.value}")

    # Attach the callback function to both rising and falling edges
    # Some sensors give one pulse per change, others multiple. We'll count all.
    hall_sensor.when_activated = sensor_changed_state # Detects change from high to low (if pull_up)
    hall_sensor.when_deactivated = sensor_changed_state # Detects change from low to high (if pull_up)

    print("\n--- Calibration Instructions ---")
    print("MODE 1 - Pulses per revolution:")
    print("  Lift a rear wheel, spin it exactly one full revolution.")
    print("MODE 2 - ODO calibration:")
    print("  Roll the car exactly 1 meter on the ground, then press Enter.")
    print("--------------------------------")

    mode = input("Enter mode (1=revolution, 2=odo): ").strip()
    pulse_count = 0

    if mode == "2":
        import math
        diameter = input("Wheel diameter in cm (default 7.0): ").strip()
        diameter = float(diameter) if diameter else 7.0
        input("Position car at start mark. Press Enter, roll EXACTLY 1 meter, then press Enter again...")
        pulse_count = 0
        input("Rolling... press Enter when at 1 meter mark.")
        pulses_per_rev = pulse_count / (100.0 / (math.pi * diameter))
        print(f"\nPulses counted over 1m: {pulse_count}")
        print(f"Calculated PULSES_PER_REVOLUTION = {pulses_per_rev:.1f}")
        print(f"\nUpdate config.py:")
        print(f"  WHEEL_DIAMETER_CM = {diameter}")
        print(f"  PULSES_PER_REVOLUTION = {pulses_per_rev:.1f}")
    else:
        input("Press Enter to start counting one full revolution...")
        pulse_count = 0
        print("\nSpin wheel exactly one revolution. Press Ctrl+C when done.")

    print("\nCounting pulses... Press Ctrl+C when done or to exit.")

    # Keep the script running until interrupted
    while True:
        print(f"\rCurrent pulses: {pulse_count} ", end="", flush=True)
        time.sleep(0.1) # Small delay to prevent high CPU usage

except Exception as e:
    print(f"Error initializing Hall sensor: {e}")
    print("Please ensure the sensor is correctly wired to GPIO 24 and gpiozero is installed.")
    print("Exiting.")
    sys.exit(1)

