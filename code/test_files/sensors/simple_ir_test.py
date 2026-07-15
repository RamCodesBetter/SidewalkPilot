#!/usr/bin/env python3
from gpiozero import DigitalInputDevice
import time
import RPi.GPIO as GPIO # Using RPi.GPIO for cleanup robustness

# --- CONFIGURATION ---
IR_SENSOR_PIN = 27  # <<< IMPORTANT: Make sure this matches the GPIO pin your IR sensor's OUT is connected to

print("--- IR Sensor Test Script ---")
print(f"Reading from GPIO pin: {IR_SENSOR_PIN}")
print("Expected behavior after calibration:")
print(" - No object in front: Sensor LED OFF, Script output: Value 1 (HIGH)")
print(" - Object in front:   Sensor LED ON,  Script output: Value 0 (LOW)")
print("Press Ctrl+C to exit.")
print("---------------------------------")

# Use BCM pin numbering for gpiozero compatibility if mixing with RPi.GPIO
# gpiozero uses BCM by default.
# GPIO.setmode(GPIO.BCM) # This line is not strictly needed if only using gpiozero

try:
    # Initialize the IR sensor pin as an input.
    # pull_up=True is generally safe. If the sensor actively drives HIGH, it's fine.
    # If the sensor's HIGH state is open-drain, pull_up=True is necessary.
    # Given the documentation "Digital HIGH output", it likely actively drives high.
    ir_sensor = DigitalInputDevice(IR_SENSOR_PIN, pull_up=True)
    
    print("Sensor initialized. Starting readings in 2 seconds...")
    time.sleep(2) # Give a moment before starting loop

    while True:
        sensor_value = ir_sensor.value
        if sensor_value == 0:
            print(f"Timestamp: {time.time():.2f} - Sensor Value: {sensor_value} (Object DETECTED)")
        else:
            print(f"Timestamp: {time.time():.2f} - Sensor Value: {sensor_value} (No Object)")
        time.sleep(0.5)  # Read every 0.5 seconds

except KeyboardInterrupt:
    print("\nExiting script due to Ctrl+C.")
except Exception as e:
    print(f"\nAn error occurred: {e}")
finally:
    print("Cleaning up GPIO...")
    if 'ir_sensor' in locals() and ir_sensor:
        ir_sensor.close()
        print(f"GPIO {IR_SENSOR_PIN} closed (via gpiozero).")
    # Fallback cleanup using RPi.GPIO if direct gpiozero close isn't enough or for general cleanup
    # This is more for robustness in a standalone script.
    # In your main app, gpiozero's close() on each device in the finally block is usually sufficient.
    try:
        GPIO.cleanup(IR_SENSOR_PIN) # Clean up the specific pin
        print(f"GPIO {IR_SENSOR_PIN} cleaned up (via RPi.GPIO).")
    except Exception as e:
        # print(f"Note: RPi.GPIO cleanup for pin {IR_SENSOR_PIN} might show error if not set up by RPi.GPIO: {e}")
        pass # It's okay if this fails if RPi.GPIO wasn't used to set up the pin
    print("Script finished.")

