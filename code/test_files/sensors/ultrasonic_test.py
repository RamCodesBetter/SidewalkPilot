#!/usr/bin/python3
"""
HC-SR04 Ultrasonic Sensor Test Script
Test your HC-SR04 sensor connection and functionality before integrating with RC car code.

Hardware Connections:
- VCC → 5V (Pin 2 or 4)
- GND → Ground (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
- Trig → GPIO 23 (Pin 16)
- ultrasonic_echo → GPIO 22 (Pin 15)
"""

import time
import statistics
from gpiozero import DigitalOutputDevice, DigitalInputDevice

# GPIO Pin Configuration
ultrasonic_trig_PIN = 5
ultrasonic_echo_PIN = 6

print("HC-SR04 Ultrasonic Sensor Test")
print("=" * 40)
print(f"ultrasonic_trig Pin: GPIO {ultrasonic_trig_PIN} (Physical Pin 16)")
print(f"ultrasonic_echo Pin: GPIO {ultrasonic_echo_PIN} (Physical Pin 15)")
print("=" * 40)

try:
    # Initialize GPIO devices
    ultrasonic_trig = DigitalOutputDevice(ultrasonic_trig_PIN, initial_value=False)
    ultrasonic_echo = DigitalInputDevice(ultrasonic_echo_PIN, pull_up=False)
    print("✓ GPIO devices initialized successfully")
    
    def read_distance():
        """
        Read distance from HC-SR04 sensor.
        Returns distance in centimeters or None if reading failed.
        """
        try:
            # Ensure ultrasonic_trig is low
            ultrasonic_trig.value = False
            time.sleep(0.00002)  # 20 microseconds
            
            # Send 10 microsecond ultrasonic_trig pulse
            ultrasonic_trig.value = True
            time.sleep(0.00001)  # 10 microseconds
            ultrasonic_trig.value = False
            
            # Measure ultrasonic_echo pulse duration with timeout
            timeout_start = time.time()
            timeout_duration = 0.5  # 500ms timeout
            
            # Wait for ultrasonic_echo to go high (start of pulse)
            while not ultrasonic_echo.value:
                if time.time() - timeout_start > timeout_duration:
                    return None, "Timeout waiting for ultrasonic_echo high"
            
            pulse_start = time.time()
            
            # Wait for ultrasonic_echo to go low (end of pulse)
            while ultrasonic_echo.value:
                if time.time() - timeout_start > timeout_duration:
                    return None, "Timeout waiting for ultrasonic_echo low"
            
            pulse_end = time.time()
            
            # Calculate distance
            pulse_duration = pulse_end - pulse_start
            # Speed of sound = 343 m/s = 34300 cm/s
            # Distance = (pulse_duration * speed_of_sound) / 2
            distance_cm = (pulse_duration * 34300) / 2
            
            # Validate distance (HC-SR04 range is typically 2-400cm)
            if 2.0 <= distance_cm <= 400.0:
                return distance_cm, "OK"
            else:
                return distance_cm, f"Out of range (2-400cm)"
                
        except Exception as e:
            return None, f"Exception: {e}"
    
    def test_single_reading():
        """Test a single distance reading"""
        print("\n--- Single Reading Test ---")
        distance, status = read_distance()
        if distance is not None:
            print(f"Distance: {distance:.2f} cm - Status: {status}")
        else:
            print(f"Reading failed - Error: {status}")
        return distance, status
    
    def test_multiple_readings(num_readings=10):
        """Test multiple readings and show statistics"""
        print(f"\n--- Multiple Readings Test ({num_readings} readings) ---")
        distances = []
        failed_count = 0
        
        for i in range(num_readings):
            print(f"Reading {i+1:2d}/{num_readings}: ", end="", flush=True)
            distance, status = read_distance()
            
            if distance is not None and status == "OK":
                distances.append(distance)
                print(f"{distance:6.2f} cm - {status}")
            else:
                failed_count += 1
                print(f"FAILED - {status}")
            
            time.sleep(0.1)  # 100ms between readings
        
        # Statistics
        if distances:
            print(f"\n--- Statistics ({len(distances)} valid readings) ---")
            print(f"Average:    {statistics.mean(distances):6.2f} cm")
            print(f"Minimum:    {min(distances):6.2f} cm")
            print(f"Maximum:    {max(distances):6.2f} cm")
            if len(distances) > 1:
                print(f"Std Dev:    {statistics.stdev(distances):6.2f} cm")
            print(f"Failed:     {failed_count}/{num_readings} readings")
        else:
            print("No valid readings obtained!")
    
    def test_continuous_monitoring():
        """Continuous monitoring mode"""
        print("\n--- Continuous Monitoring Mode ---")
        print("Press Ctrl+C to stop")
        print("Distance | Status")
        print("-" * 25)
        
        try:
            while True:
                distance, status = read_distance()
                current_time = time.strftime("%H:%M:%S")
                
                if distance is not None:
                    # Visual bar for distance (scale: 0-100cm)
                    bar_length = min(int(distance / 2), 50)  # Max 50 chars
                    bar = "█" * bar_length
                    print(f"{current_time} | {distance:6.2f} cm | {bar}")
                else:
                    print(f"{current_time} | FAILED     | {status}")
                
                time.sleep(0.2)  # 200ms between readings
                
        except KeyboardInterrupt:
            print("\nContinuous monitoring stopped.")
    
    def test_autonomous_driving_simulation():
        """Simulate autonomous driving logic"""
        print("\n--- Autonomous Driving Simulation ---")
        print("Target: 20cm ± 2cm (18-22cm acceptable range)")
        print("Press Ctrl+C to stop")
        
        target_distance = 20.0
        tolerance = 2.0
        
        try:
            while True:
                distance, status = read_distance()
                current_time = time.strftime("%H:%M:%S")
                
                if distance is not None and status == "OK":
                    error = distance - target_distance
                    
                    if abs(error) <= tolerance:
                        action = "STRAIGHT"
                        symbol = "↑"
                    elif error > tolerance:
                        # Too far from wall, steer right
                        action = f"STEER RIGHT ({abs(error):.1f}cm too far)"
                        symbol = "→"
                    else:
                        # Too close to wall, steer left
                        action = f"STEER LEFT ({abs(error):.1f}cm too close)"
                        symbol = "←"
                    
                    print(f"{current_time} | {distance:6.2f}cm | {symbol} {action}")
                else:
                    print(f"{current_time} | SENSOR FAIL | ? Use last known direction")
                
                time.sleep(0.3)  # 300ms between readings
                
        except KeyboardInterrupt:
            print("\nAutonomous simulation stopped.")
    
    # Main test menu
    while True:
        print("\n" + "=" * 50)
        print("HC-SR04 ULTRASONIC SENSOR TEST MENU")
        print("=" * 50)
        print("1. Single reading test")
        print("2. Multiple readings test (10 readings)")
        print("3. Multiple readings test (50 readings)")
        print("4. Continuous monitoring")
        print("5. Autonomous driving simulation")
        print("6. Exit")
        print("-" * 50)
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == "1":
            test_single_reading()
            
        elif choice == "2":
            test_multiple_readings(10)
            
        elif choice == "3":
            test_multiple_readings(50)
            
        elif choice == "4":
            test_continuous_monitoring()
            
        elif choice == "5":
            test_autonomous_driving_simulation()
            
        elif choice == "6":
            print("Exiting test program...")
            break
            
        else:
            print("Invalid choice! Please enter 1-6.")

except Exception as e:
    print(f"✗ Error initializing GPIO: {e}")
    print("\nTroubleshooting:")
    print("1. Check if you're running as root (sudo)")
    print("2. Verify GPIO pin connections")
    print("3. Make sure gpiozero is installed: sudo apt install python3-gpiozero")

finally:
    # Cleanup
    try:
        ultrasonic_trig.close()
        ultrasonic_echo.close()
        print("✓ GPIO cleanup completed")
    except:
        pass

print("Test completed.")