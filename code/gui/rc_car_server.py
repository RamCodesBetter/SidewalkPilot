#!/usr/bin/python3
import os
import cv2 
import socket
import threading
import json
import time
import datetime
import sys
import math 
import subprocess # Added for external FFmpeg calls

# Ensure gpiozero is installed: sudo apt install -y python3-gpiozero
from gpiozero import PWMOutputDevice, DigitalInputDevice, Servo

# --- CONFIGURATION ---
CMD_PORT = 9999

# --- GLOBAL FLAG FOR SHUTDOWN ---
shutdown_flag = threading.Event()

# --- AEB GRACE PERIOD ---
script_start_time = time.time()
AEB_GRACE_PERIOD_SECONDS = 2.0 # Grace period for AEB at startup

# --- GPIO SETUP ---
headlight_pin = 4
brake_light_pin = 26
indicator_left_pin = 17
indicator_right_pin = 18
horn_pin = 21
IR_SENSOR_F_PIN = 27  # GPIO pin for the front IR sensor
IR_SENSOR_B_PIN = 5   # GPIO pin for the back IR sensor
STEERING_SERVO_PIN = 12 # GPIO pin for the steering servo signal wire
HALL_SENSOR_GPIO_PIN = 24 # GPIO pin for the Hall sensor (connected to E1A)

# --- MOTOR CONTROL PINS (Yahboom Dual MD Module) ---
# Based on your clarification: Motor A is on the RIGHT, Motor B is on the LEFT.
# AIN1: Motor 1 drive signal 1 (Motor A / Right Motor Reverse)
# AIN2: Motor 1 drive signal 2 (Motor A / Right Motor Forward)
# BIN1: Motor 2 drive signal 1 (Motor B / Left Motor Reverse)
# BIN2: Motor 2 drive signal 2 (Motor B / Left Motor Forward)

# Chosen GPIO pins on Raspberry Pi 5 (avoiding existing used pins)
MOTOR_RIGHT_FWD_PIN = 19 # Connect to AIN2 on motor driver (for Motor A / Right)
MOTOR_RIGHT_BWD_PIN = 20 # Connect to AIN1 on motor driver (for Motor A / Right)
MOTOR_LEFT_FWD_PIN = 25  # Connect to BIN2 on motor driver (for Motor B / Left)
MOTOR_LEFT_BWD_PIN = 13  # Connect to BIN1 on motor driver (for Motor B / Left)


# --- STEERING CALIBRATION & SETTINGS ---
STEERING_CENTER_OFFSET = 0.0
# Increased IDLE_STEERING_THRESHOLD to make the servo return to center more readily
# This means a wider dead zone around the center where the servo will detach.
IDLE_STEERING_THRESHOLD = 0.25 # Original was 0.18

# --- MOTOR ACCELERATION/BRAKING SETTINGS ---
ACCEL_RATE = 0.5 # Percentage of full speed per second (e.g., 0.5 means 50% speed in 1 second)
BRAKE_RATE = 1.5 # Rate for manual brake (when brake pedal is pressed)
AEB_RATE = 3.0 # Rate for Automatic Emergency Braking (stronger than manual)
COASTING_RATE = 0.6 # Rate for deceleration when throttle is released and no brake is applied

# --- SPEEDOMETER CALIBRATION & SETTINGS ---
WHEEL_DIAMETER_CM = 7.0 # Diameter of the wheel in centimeters
PULSES_PER_REVOLUTION = 420.0 # Pulses detected by Hall sensor for one full wheel revolution
SPEED_SMOOTHING_ALPHA = 0.2 # Alpha for exponential moving average for speed (0-1, higher means less smoothing)

# Constants for speed calculation
# Circumference = pi * D (in cm)
WHEEL_CIRCUMFERENCE_CM = math.pi * WHEEL_DIAMETER_CM
# Convert cm/s to mph: (cm/s) * (1 m / 100 cm) * (1 km / 1000 m) * (1 mile / 1.60934 km) * (3600 s / 1 hour)
# Simplified: (cm/s) * (3600 / (100 * 1000 * 1.60934)) = (cm/s) * 0.0223694
CM_PER_SEC_TO_MPH = 0.0223694

gpio_initialized = False

# --- GLOBAL SPEED VARIABLES ---
# These are global because they are updated by an interrupt (pulse_detected)
# and read by the main loop/GPIO update function.
g_pulse_count = 0
g_last_pulse_time = time.time()
g_previous_pulse_count = 0 # To calculate pulses in a given time interval
g_previous_speed_calculation_time = time.time()
g_current_raw_mph = 0.0 # Stores the most recently calculated speed before smoothing
g_smoothed_speed_mph = 0.0 # The actual speed sent to client after smoothing

# --- HALL SENSOR CALLBACK ---
def pulse_detected():
    """Callback function for when the Hall sensor detects a pulse."""
    global g_pulse_count, g_last_pulse_time
    g_pulse_count += 1
    g_last_pulse_time = time.time()
    # print(f"DEBUG: Pulse! Count: {g_pulse_count}") # Debugging pulses

# --- CAMERA SETUP ---
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

# --- CAMERA FLIP CONFIGURATION (Software-based) ---
# Options: "NONE", "HFLIP", "VFLIP", "HVFLIP" (Horizontal and Vertical = 180 degrees)
CAMERA_FLIP_MODE = "HVFLIP" 

picam2 = None
video_recorder_encoder = None
video_recorder_output = None
video_recording_active = False
video_start_timestamp = 0
current_video_filename = None # To store the filename of the video being recorded

PHOTO_DIR = "/home/Ram/Desktop/rc_car_media/photos"
VIDEO_DIR = "/home/Ram/Desktop/rc_car_media/videos"
os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

def take_photo():
    """Captures a still photo and saves it to disk, applying a flip if configured."""
    global picam2
    if picam2:
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(PHOTO_DIR, f"photo_{timestamp}.jpg")
            picam2.capture_file(filename)
            print(f"Photo captured: {filename}")
            
            # Post-process with OpenCV for flipping based on CAMERA_FLIP_MODE
            try:
                img = cv2.imread(filename)
                if img is not None:
                    flipped_img = None
                    if CAMERA_FLIP_MODE == "HFLIP":
                        flipped_img = cv2.flip(img, 1) # 1 for horizontal flip
                        print("Applying horizontal flip to photo with OpenCV.")
                    elif CAMERA_FLIP_MODE == "VFLIP":
                        flipped_img = cv2.flip(img, 0) # 0 for vertical flip
                        print("Applying vertical flip to photo with OpenCV.")
                    elif CAMERA_FLIP_MODE == "HVFLIP":
                        flipped_img = cv2.flip(img, -1) # -1 for both (180 degree rotation)
                        print("Applying 180-degree flip (H+V) to photo with OpenCV.")
                    
                    if flipped_img is not None:
                        cv2.imwrite(filename, flipped_img)
                        print(f"Photo successfully flipped and saved: {filename}")
                    else:
                        print("No flip applied to photo (CAMERA_FLIP_MODE is NONE or invalid).")
                else:
                    print(f"Warning: Could not read captured photo {filename} for flipping (image is None).")
            except Exception as cv2_e:
                print(f"Error flipping photo with OpenCV: {cv2_e}")
                import traceback
                traceback.print_exc()
                # Continue even if OpenCV flip fails, original photo is still saved.

            return True, f"Photo saved to {filename}"
        except Exception as e:
            print(f"Error taking photo: {e}")
            return False, f"Error taking photo: {e}"
    return False, "Camera not initialized."

def toggle_video_recording():
    """Starts or stops video recording, applying a flip if configured."""
    global picam2, video_recorder_encoder, video_recorder_output, video_recording_active, video_start_timestamp, current_video_filename
    if not picam2:
        return False, "Camera not initialized."

    if video_recording_active:
        # Stop recording
        try:
            if video_recorder_encoder:
                picam2.stop_encoder() # Stop the encoder
                video_recorder_encoder = None
                video_recorder_output = None
            video_recording_active = False
            print("Video recording stopped.")

            # --- Post-process video with FFmpeg for flipping ---
            if current_video_filename and CAMERA_FLIP_MODE != "NONE":
                input_filename = current_video_filename
                # Create a new filename for the flipped video to avoid overwriting the original
                flipped_filename = os.path.join(VIDEO_DIR, f"flipped_{os.path.basename(input_filename)}")
                
                ffmpeg_command = ["ffmpeg", "-i", input_filename, "-vf"]
                if CAMERA_FLIP_MODE == "HFLIP":
                    ffmpeg_command.append("hflip")
                    print(f"Applying horizontal flip to video: {input_filename}")
                elif CAMERA_FLIP_MODE == "VFLIP":
                    ffmpeg_command.append("vflip")
                    print(f"Applying vertical flip to video: {input_filename}")
                elif CAMERA_FLIP_MODE == "HVFLIP":
                    ffmpeg_command.append("hflip,vflip")
                    print(f"Applying 180-degree flip (H+V) to video: {input_filename}")
                
                ffmpeg_command.append("-c:a")
                ffmpeg_command.append("copy") # Copy audio without re-encoding
                ffmpeg_command.append(flipped_filename)

                try:
                    print(f"Executing FFmpeg command: {' '.join(ffmpeg_command)}")
                    # Use subprocess.run to execute ffmpeg
                    result = subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
                    print(f"FFmpeg stdout:\n{result.stdout}")
                    print(f"FFmpeg stderr:\n{result.stderr}")
                    print(f"Flipped video saved to: {flipped_filename}")
                    # Optionally, remove the original unflipped video if the flipped one is successful
                    os.remove(input_filename)
                    print(f"Original video removed: {input_filename}")
                    current_video_filename = flipped_filename # Update to the flipped file
                except subprocess.CalledProcessError as e:
                    print(f"ERROR: FFmpeg command failed with exit code {e.returncode}")
                    print(f"FFmpeg stdout:\n{e.stdout}")
                    print(f"FFmpeg stderr:\n{e.stderr}")
                    print(f"Original video retained: {input_filename}")
                except FileNotFoundError:
                    print("ERROR: FFmpeg command not found. Please ensure FFmpeg is installed.")
                except Exception as e:
                    print(f"An unexpected error occurred during FFmpeg processing: {e}")
                    import traceback
                    traceback.print_exc()
            current_video_filename = None # Reset after processing

            return True, "Video recording stopped and processed."
        except Exception as e:
            print(f"Error stopping video recording: {e}")
            return False, f"Error stopping video recording: {e}"
    else:
        # Start recording
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # Store the filename for post-processing
            current_video_filename = os.path.join(VIDEO_DIR, f"video_{timestamp}.mp4")
            
            video_recorder_encoder = H264Encoder(10000000) # 10 Mbps bitrate
            
            # Remove ffmpeg_arguments from here as it's not supported by your picamera2 version
            video_recorder_output = FfmpegOutput(current_video_filename) 
            
            picam2.start_encoder(video_recorder_encoder, video_recorder_output)
            
            video_recording_active = True
            video_start_timestamp = time.time()
            print(f"Video recording started to: {current_video_filename}")
            return True, f"Video recording started to {current_video_filename}"
        except Exception as e:
            print(f"Error starting video recording: {e}")
            if video_recorder_encoder:
                try: picam2.stop_encoder()
                except: pass
            video_recorder_encoder = None
            video_recorder_output = None
            video_recording_active = False
            current_video_filename = None
            return False, f"Error starting video recording: {e}"


# Attempt to initialize GPIOs
try:
    headlight = PWMOutputDevice(headlight_pin, frequency=500, initial_value=0)
    brakeL = PWMOutputDevice(brake_light_pin, frequency=500, initial_value=0)
    indL = PWMOutputDevice(indicator_left_pin, frequency=500, initial_value=0)
    indR = PWMOutputDevice(indicator_right_pin, frequency=500, initial_value=0)
    horn = PWMOutputDevice(horn_pin, frequency=440, initial_value=0)
    
    ir_sensor_f = DigitalInputDevice(IR_SENSOR_F_PIN, pull_up=True)
    ir_sensor_b = DigitalInputDevice(IR_SENSOR_B_PIN, pull_up=True)

    steering_servo = Servo(STEERING_SERVO_PIN, min_pulse_width=1/1000, max_pulse_width=2/1000, frame_width=20/1000)

    # Motor control initialization using selected GPIO pins
    # These assignments map the logical "fwd" and "bwd" to their respective physical pins.
    # We will handle any necessary inversion in the update_gpio function based on observed behavior.
    motor_left_fwd = PWMOutputDevice(MOTOR_LEFT_FWD_PIN, frequency=1000, initial_value=0) # Connect to BIN2 (Left Motor Forward)
    motor_left_bwd = PWMOutputDevice(MOTOR_LEFT_BWD_PIN, frequency=1000, initial_value=0) # Connect to BIN1 (Left Motor Reverse)
    motor_right_fwd = PWMOutputDevice(MOTOR_RIGHT_FWD_PIN, frequency=1000, initial_value=0) # Connect to AIN2 (Right Motor Forward)
    motor_right_bwd = PWMOutputDevice(MOTOR_RIGHT_BWD_PIN, frequency=1000, initial_value=0) # Connect to AIN1 (Right Motor Reverse)

    # Hall Sensor for Speedometer (configured as input with pull-up)
    hall_sensor = DigitalInputDevice(HALL_SENSOR_GPIO_PIN, pull_up=True)
    # Attach callback for both rising and falling edges to accurately count pulses for Hall sensor
    hall_sensor.when_activated = pulse_detected 
    hall_sensor.when_deactivated = pulse_detected

    gpio_initialized = True
    print(f"GPIO devices initialized. IR Sensor Front on GPIO {IR_SENSOR_F_PIN}. IR Sensor Back on GPIO {IR_SENSOR_B_PIN}.")
    print(f"Steering Servo on GPIO {STEERING_SERVO_PIN}. Hall Sensor on GPIO {HALL_SENSOR_GPIO_PIN}.")
    print(f"Motor control pins initialized: Left FWD({MOTOR_LEFT_FWD_PIN}), Left BWD({MOTOR_LEFT_BWD_PIN}), Right FWD({MOTOR_RIGHT_FWD_PIN}), Right BWD({MOTOR_RIGHT_BWD_PIN}).")
    print(f"Steering center offset: {STEERING_CENTER_OFFSET}, Idle threshold: {IDLE_STEERING_THRESHOLD}")
    print(f"Speedometer configured: Wheel Diameter={WHEEL_DIAMETER_CM}cm, Pulses/Revolution={PULSES_PER_REVOLUTION}.")

    # Camera Setup
    picam2 = Picamera2()

    # We are no longer relying on libcamera.Transform for flipping.
    # The actual flip is done in software (OpenCV for photos, FFmpeg for videos).
    camera_config_params = {"main": {"size": (640, 480)}}

    camera_config = picam2.create_video_configuration(**camera_config_params)
    picam2.configure(camera_config)
    picam2.start()
    print("Camera initialized and started.")

except Exception as e:
    print(f"Error initializing GPIO or Camera: {e}. GPIO and Camera control will be disabled. Check wiring, 'gpiozero' permissions (e.g., install gpiozero or run with sudo), and 'picamera2' installation.")
    # Define dummy classes for continued operation without GPIO, to prevent errors if hardware isn't connected
    class DummyPWM:
        def __init__(self, pin=None, frequency=None, initial_value=None): self.pin = pin; self._value = initial_value if initial_value is not None else 0
        @property
        def value(self): return self._value
        @value.setter
        def value(self, val): self._value = val;
        def close(self): pass
    class DummyDigitalInput:
        def __init__(self, pin=None, pull_up=None): self.pin = pin; self._value = 0 # Simulate no obstacle by default
        @property
        def value(self): return self._value
        def close(self): pass
    class DummyServo:
        def __init__(self, pin=None, min_pulse_width=None, max_pulse_width=None, frame_width=None): self.pin = pin; self._value = 0; self.is_active = False
        @property
        def value(self): return self._value
        @value.setter
        def value(self, val): self._value = val; self.is_active = val is not None;
        def detach(self): self.is_active = False; self._value = None;
        def close(self): pass

    # Assign dummy objects if GPIO initialization fails
    headlight = DummyPWM(headlight_pin)
    brakeL = DummyPWM(brake_light_pin)
    indL = DummyPWM(indicator_left_pin)
    indR = DummyPWM(indicator_right_pin)
    horn = DummyPWM(horn_pin)
    ir_sensor_f = DummyDigitalInput(IR_SENSOR_F_PIN)
    ir_sensor_b = DummyDigitalInput(IR_SENSOR_B_PIN)
    steering_servo = DummyServo(STEERING_SERVO_PIN)
    motor_left_fwd = DummyPWM(MOTOR_LEFT_FWD_PIN)
    motor_left_bwd = DummyPWM(MOTOR_LEFT_BWD_PIN)
    motor_right_fwd = DummyPWM(MOTOR_RIGHT_FWD_PIN)
    motor_right_bwd = DummyPWM(MOTOR_RIGHT_BWD_PIN)
    hall_sensor = DummyDigitalInput(HALL_SENSOR_GPIO_PIN) # Dummy for Hall sensor
    picam2 = None # Ensure camera is None if initialization failed


# --- SHARED CONTROL STATE ---
state = {
    "steer": 0.0, "throttle": 0.0, "brake": False, "lights": False,
    "night_mode": False, "indicators": "off", "hazard": False, "horn": False,
    "aeb_active": False, "cc_active": False, "cc_target_speed": 0,
    "current_motor_pwm": 0.0, # New: Tracks the actual PWM value applied to motors (0-1.0) for smooth control
    "gear_mode": "P" # New: Current gear mode (P, R, N, D)
}

# --- BLINKING LOGIC STATE ---
blink_state = {"left_on": False, "right_on": False, "last_toggle_time": time.time()}
BLINK_INTERVAL_SEC = 0.5

# --- AEB LOGIC ---
aeb_triggered_by_sensor = False 

def check_aeb():
    """
    Checks for Automatic Emergency Braking conditions based on IR sensors.
    If an obstacle is detected, AEB is activated, forcing brake and zero throttle.
    """
    global aeb_triggered_by_sensor, state
    if not gpio_initialized: 
        state["aeb_active"] = False 
        return

    # Grace period at startup to prevent false AEB triggers
    if time.time() - script_start_time < AEB_GRACE_PERIOD_SECONDS:
        if state["aeb_active"]: 
            aeb_triggered_by_sensor = False 
            state["aeb_active"] = False 
        return

    raw_front_val = ir_sensor_f.value
    raw_back_val = ir_sensor_b.value
    
    # Assuming 1 means obstacle detected (sensor output is HIGH when obstacle is close)
    obstacle_detected_front = (raw_front_val == 1) 
    obstacle_detected_back = (raw_back_val == 1)

    if obstacle_detected_front or obstacle_detected_back:
        if not aeb_triggered_by_sensor: 
            print(f"AEB TRIGGERED by proximity sensor! Front: {obstacle_detected_front} (val={raw_front_val}), Back: {obstacle_detected_back} (val={raw_back_val})")
            aeb_triggered_by_sensor = True
            # Force brake and zero throttle when AEB is active
            state["brake"] = True 
            state["throttle"] = 0.0 
            # Deactivate cruise control if AEB triggers
            if state.get("cc_active", False):
                 state["cc_active"] = False
                 print("AEB disabled Cruise Control.")
        state["aeb_active"] = True 
    else: 
        if aeb_triggered_by_sensor: 
            print("AEB DEACTIVATED (obstacle cleared or condition no longer met).")
            aeb_triggered_by_sensor = False
        state["aeb_active"] = False

# --- SPEED CALCULATION FUNCTION ---
def calculate_speed(dt):
    """
    Calculates the current speed in MPH based on Hall sensor pulses.
    Applies exponential moving average for smoothing.
    """
    global g_previous_pulse_count, g_previous_speed_calculation_time
    global g_current_raw_mph, g_smoothed_speed_mph

    current_time = time.time()
    time_elapsed_since_last_calc = current_time - g_previous_speed_calculation_time

    # Only calculate if enough time has passed or if there are new pulses
    if time_elapsed_since_last_calc > 0.1 or g_pulse_count != g_previous_pulse_count: # Calculate at least every 100ms or on new pulse
        pulses_in_interval = g_pulse_count - g_previous_pulse_count
        
        # Avoid division by zero if no time has passed (shouldn't happen with dt check)
        if time_elapsed_since_last_calc > 0:
            pulses_per_second = pulses_in_interval / time_elapsed_since_last_calc
            
            # Revolutions per second = pulses_per_second / PULSES_PER_REVOLUTION
            revs_per_second = pulses_per_second / PULSES_PER_REVOLUTION
            
            # Distance per second (cm/s) = revs_per_second * WHEEL_CIRCUMFERENCE_CM
            speed_cm_per_sec = revs_per_second * WHEEL_CIRCUMFERENCE_CM
            
            # Convert cm/s to MPH
            g_current_raw_mph = speed_cm_per_sec * CM_PER_SEC_TO_MPH
            
            # Apply Exponential Moving Average (EMA) for smoothing
            # If this is the first real calculation, or speed changes drastically,
            # initialize smoothing with the raw value.
            if g_smoothed_speed_mph == 0.0 or abs(g_current_raw_mph - g_smoothed_speed_mph) > 5.0: # If large jump, reset smoothing
                g_smoothed_speed_mph = g_current_raw_mph
            else:
                g_smoothed_speed_mph = (SPEED_SMOOTHING_ALPHA * g_current_raw_mph) + \
                                       ((1.0 - SPEED_SMOOTHING_ALPHA) * g_smoothed_speed_mph)
            
            # Ensure speed doesn't go negative or too high due to noise
            # If motors are off and speed is very low, set to 0 to prevent drift
            if abs(state["current_motor_pwm"]) < 0.01 and g_current_raw_mph < 0.5: 
                g_smoothed_speed_mph = 0.0
                g_current_raw_mph = 0.0

        # Reset for next interval
        g_previous_pulse_count = g_pulse_count
        g_previous_speed_calculation_time = current_time
    
    # print(f"DEBUG Speed: Raw={g_current_raw_mph:.2f}mph, Smoothed={g_smoothed_speed_mph:.2f}mph, Pulses={g_pulse_count}") # Verbose speed debug

# --- GPIO UPDATE FUNCTION ---
def update_gpio(dt):
    """
    Updates the state of GPIO devices based on the current control state and gear mode.
    Args:
        dt (float): The time elapsed since the last update, in seconds.
    """
    global g_smoothed_speed_mph # Reference the global smoothed speed
    if not gpio_initialized:
        return
    current_time = time.time()

    # Steering Servo
    # Servo should return to center and detach when steer value is close to 0.
    if hasattr(steering_servo, 'value'): 
        calibrated_steer_value = state["steer"] + STEERING_CENTER_OFFSET
        calibrated_steer_value = max(-1.0, min(1.0, calibrated_steer_value))
        
        # If the steer value is within the idle threshold, detach the servo.
        # Otherwise, set its value.
        if abs(state["steer"]) < IDLE_STEERING_THRESHOLD: # Check state["steer"] directly for user input
            if steering_servo.is_active: # Only detach if it was previously active
                steering_servo.value = STEERING_CENTER_OFFSET 
                time.sleep(0.02) # Small delay to allow servo to move
                steering_servo.detach()
        else:
            # Only update servo if it's not already at the target value
            if steering_servo.value != calibrated_steer_value or not steering_servo.is_active: 
                steering_servo.value = calibrated_steer_value
    
    # Determine effective brake state (manual brake OR AEB)
    current_effective_brake_state = state["brake"] or state["aeb_active"]
    
    # Determine the desired PWM based on manual throttle, cruise control, and gear mode
    desired_motor_pwm = 0.0 # This will be the immediate target for smoothing
    
    # --- Gear Mode Logic ---
    if state["gear_mode"] == "P": # Park
        desired_motor_pwm = 0.0
        state["brake"] = True # Force brake in Park
        # Deactivate cruise control if gear is Park
        if state.get("cc_active", False):
            state["cc_active"] = False
            state["cc_target_speed"] = 0
            print("Cruise Control deactivated due to Park mode.")
    elif state["gear_mode"] == "N": # Neutral
        desired_motor_pwm = 0.0
        state["brake"] = False # No brake in Neutral (car can coast/roll freely)
        # Deactivate cruise control if gear is Neutral
        if state.get("cc_active", False):
            state["cc_active"] = False
            state["cc_target_speed"] = 0
            print("Cruise Control deactivated due to Neutral mode.")
    elif state["gear_mode"] == "R": # Reverse
        # In reverse, throttle from GUI (which is positive) means going backward.
        # So, desired_motor_pwm will be negative of throttle.
        if current_effective_brake_state:
            desired_motor_pwm = 0.0
        else:
            desired_motor_pwm = state["throttle"] # Correct: Uses the already-negative throttle value
        # Cruise control is not applicable in Reverse
        if state.get("cc_active", False):
            state["cc_active"] = False
            state["cc_target_speed"] = 0
            print("Cruise Control deactivated due to Reverse mode.")
    elif state["gear_mode"] == "D": # Drive
        if current_effective_brake_state:
            desired_motor_pwm = 0.0
            # If braking, also deactivate cruise control immediately on the server side
            if state.get("cc_active", False):
                state["cc_active"] = False
                print("Cruise Control disabled due to manual brake or AEB.")
        else: # No active braking (manual or AEB)
            if state.get("cc_active", False):
                Kp = 0.05 # Proportional gain for cruise control. Adjust as needed.
                error = state["cc_target_speed"] - g_smoothed_speed_mph

                # Calculate a desired PWM based on the error.
                # A positive error (speed too low) should increase PWM, negative error (speed too high) decrease PWM.
                cc_adjustment = error * Kp
                
                # Combine current motor PWM with adjustment to find the next desired state
                # Ensure this desired PWM is within [0, 1.0] for forward movement
                desired_motor_pwm = max(0.0, min(1.0, state["current_motor_pwm"] + cc_adjustment))
                
                # If target speed is 0 and current speed is low, ensure motors stop
                if state["cc_target_speed"] < 0.5 and g_smoothed_speed_mph < 0.5: 
                    desired_motor_pwm = 0.0
                
                # If vehicle is stopped but CC target is active, give a gentle push to start
                if g_smoothed_speed_mph < 0.1 and state["cc_target_speed"] > 0.1 and desired_motor_pwm < 0.1:
                    desired_motor_pwm = 0.2 # Small initial push

            else: # Cruise control is not active, use manual throttle input
                desired_motor_pwm = state["throttle"] # This is 0 or 1.0 from GUI for forward movement

    # Smooth transition for motor PWM
    # Determine if we are accelerating or decelerating in magnitude
    # and apply the appropriate rate.
    
    # Check if the magnitude of the desired PWM is greater than the current PWM magnitude.
    # This indicates an attempt to accelerate (either forward or backward).
    if abs(desired_motor_pwm) > abs(state["current_motor_pwm"]):
        # Accelerating: move current_motor_pwm towards desired_motor_pwm by ACCEL_RATE
        if desired_motor_pwm > state["current_motor_pwm"]: # Accelerating forward or reducing reverse power
            state["current_motor_pwm"] = min(state["current_motor_pwm"] + ACCEL_RATE * dt, desired_motor_pwm)
        else: # Accelerating reverse or reducing forward power
            state["current_motor_pwm"] = max(state["current_motor_pwm"] - ACCEL_RATE * dt, desired_motor_pwm)
    elif abs(desired_motor_pwm) < abs(state["current_motor_pwm"]):
        # Decelerating: move current_motor_pwm towards desired_motor_pwm by a deceleration rate
        deceleration_rate = COASTING_RATE # Default for coasting
        if state["aeb_active"]:
            deceleration_rate = AEB_RATE
        elif state["brake"] and state["gear_mode"] not in ["P", "N"]:
            deceleration_rate = BRAKE_RATE

        if desired_motor_pwm > state["current_motor_pwm"]: # Decelerating reverse towards 0 or positive
            state["current_motor_pwm"] = min(state["current_motor_pwm"] + deceleration_rate * dt, desired_motor_pwm)
        else: # Decelerating forward towards 0 or negative
            state["current_motor_pwm"] = max(state["current_motor_pwm"] - deceleration_rate * dt, desired_motor_pwm)
    else: # Magnitudes are equal or very close, snap to desired
        if abs(state["current_motor_pwm"] - desired_motor_pwm) < 0.01:
            state["current_motor_pwm"] = desired_motor_pwm


    # Apply motor PWM to correct pins based on current_motor_pwm
    # Reset all motors first to ensure no conflicting signals
    motor_left_fwd.value = 0.0
    motor_left_bwd.value = 0.0
    motor_right_fwd.value = 0.0
    motor_right_bwd.value = 0.0

    # Based on your latest feedback:
    # When car needs to go FORWARD (current_motor_pwm > 0):
    #   Both left and right wheels should spin FORWARD.
    #   This means activating their respective FWD pins.
    # When car needs to go BACKWARD (Reverse) (current_motor_pwm < 0):
    #   Both left and right wheels should spin BACKWARD.
    #   This means activating their respective BWD pins.
    
    if state["current_motor_pwm"] > 0.001: # Moving the car FORWARD
        # The left motor is flipped, so its "backward" pin moves the car forward.
        motor_left_bwd.value = state["current_motor_pwm"]  # Inverted for left motor
        motor_right_fwd.value = state["current_motor_pwm"] # Normal for right motor
    elif state["current_motor_pwm"] < -0.001: # Moving the car BACKWARD (Reverse)
        # The left motor is flipped, so its "forward" pin moves the car backward.
        motor_left_fwd.value = abs(state["current_motor_pwm"]) # Inverted for left motor
        motor_right_bwd.value = abs(state["current_motor_pwm"]) # Normal for right motor

    # Headlights (Night Mode)
    new_headlight_value = 1.0 if state["night_mode"] else 0.0
    if headlight.value != new_headlight_value:
        headlight.value = new_headlight_value

    # Brake Light
    new_brake_light_value = 0.0
    if current_effective_brake_state: # Manual brake or AEB
        new_brake_light_value = 1.0 
    elif state["night_mode"] and state["current_motor_pwm"] == 0.0: # Dim brake light if night mode and stopped
        new_brake_light_value = 0.15 
    else:
        new_brake_light_value = 0.0 

    if brakeL.value != new_brake_light_value:
        brakeL.value = new_brake_light_value
    
    # Indicators and Hazard Lights
    new_indL_value = 0.0
    new_indR_value = 0.0

    if state["hazard"] or state["indicators"] != "off":
        if current_time - blink_state["last_toggle_time"] > BLINK_INTERVAL_SEC:
            blink_state["left_on"] = not blink_state["left_on"]
            blink_state["right_on"] = not blink_state["right_on"]
            blink_state["last_toggle_time"] = current_time

        if state["hazard"]:
            new_indL_value = 0.5 if blink_state["left_on"] else 0.0
            new_indR_value = 0.5 if blink_state["right_on"] else 0.0
        elif state["indicators"] == "left":
            new_indL_value = 0.5 if blink_state["left_on"] else 0.0
            new_indR_value = 0.0
        elif state["indicators"] == "right":
            new_indL_value = 0.0
            new_indR_value = 0.5 if blink_state["right_on"] else 0.0
    else:
        blink_state["left_on"] = False 
        blink_state["right_on"] = False

    if indL.value != new_indL_value:
        indL.value = new_indL_value
    if indR.value != new_indR_value:
        indR.value = new_indR_value

    # Horn
    # Horn should be disabled if steering is active (i.e., state["steer"] is not close to 0)
    new_horn_value = 0.5 if state["horn"] and abs(state["steer"]) < IDLE_STEERING_THRESHOLD else 0.0
    if horn.value != new_horn_value:
        horn.value = new_horn_value

    # Calculate and update speed in the global variable
    calculate_speed(dt) # dt is used for smoothing calculation

# --- COMMAND HANDLING THREAD ---
def cmd_thread():
    """
    Thread to handle incoming commands from the client GUI.
    It receives JSON commands, updates the global state, and sends back responses.
    """
    global state, g_smoothed_speed_mph, video_recording_active, video_start_timestamp, current_video_filename # Access global smoothed speed and camera states
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind(('0.0.0.0', CMD_PORT))
    except Exception as e:
        print(f"CRITICAL: Error binding command socket to port {CMD_PORT}: {e}")
        shutdown_flag.set() 
        return
        
    server_socket.listen(1)
    print(f"Command server listening on port {CMD_PORT} for Z2W client...")
    
    try:
        server_socket.settimeout(1.0) 
        while not shutdown_flag.is_set():
            conn = None # Initialize conn to None for each iteration
            try:
                conn, addr = server_socket.accept()
                print(f"Z2W client connected from: {addr}")
                conn.settimeout(0.1) 
                with conn:
                    data_buffer = b""
                    while not shutdown_flag.is_set():
                        try:
                            chunk = conn.recv(1024 * 1024) 
                            if not chunk:
                                print("Z2W client disconnected (received empty chunk). Signalling server shutdown.")
                                shutdown_flag.set() 
                                break 
                            data_buffer += chunk
                            
                            while True: # Process all complete JSON objects in the buffer
                                try:
                                    decoded_data_str = data_buffer.decode('utf-8')
                                    idx = decoded_data_str.find('}')
                                    if idx == -1: # No complete JSON object found yet
                                        break
                                    
                                    json_str = decoded_data_str[:idx+1]
                                    command = json.loads(json_str)
                                    data_buffer = data_buffer[idx+1:] # Remove processed JSON from buffer
                                    
                                    if command.get("quit", False):
                                        print("Received quit command from client. Signalling server shutdown.")
                                        shutdown_flag.set()
                                        break 

                                    # Update state based on command
                                    state["steer"] = float(command.get("steer", state["steer"]))
                                    client_throttle_request = float(command.get("throttle", 0.0))
                                    client_brake_request = bool(command.get("brake", False))
                                    new_gear_mode = command.get("gear_mode", state["gear_mode"])

                                    # Update gear mode first, as it influences other controls
                                    state["gear_mode"] = new_gear_mode
                                    
                                    # Prioritize braking: If client sends brake or AEB is active, force brake on
                                    if client_brake_request or aeb_triggered_by_sensor:
                                        state["brake"] = True
                                        state["throttle"] = 0.0 # Client throttle is ignored if brake is active
                                        # When manual brake or AEB is active, cruise control must be deactivated
                                        if state.get("cc_active", False): 
                                            state["cc_active"] = False
                                            print("Cruise Control disabled due to manual brake or AEB.")
                                    else:
                                        state["brake"] = False
                                        # Only apply client throttle if not in Park or Neutral
                                        if state["gear_mode"] in ["P", "N"]:
                                            state["throttle"] = 0.0
                                        else:
                                            state["throttle"] = client_throttle_request
                                            # If gas is pressed while CC is active in Drive mode, deactivate CC
                                            if state.get("cc_active", False) and client_throttle_request > 0 and state["gear_mode"] == "D":
                                                state["cc_active"] = False
                                                state["cc_target_speed"] = 0
                                                print("Cruise Control deactivated by manual gas input.")

                                    state["night_mode"] = bool(command.get("night_mode", state["night_mode"]))
                                    new_indicators = command.get("indicators", state["indicators"])
                                    new_hazard = bool(command.get("hazard", state["hazard"]))
                                    if new_indicators != state["indicators"] or new_hazard != state["hazard"]:
                                        state["indicators"] = new_indicators
                                        state["hazard"] = new_hazard
                                        blink_state["left_on"] = True 
                                        blink_state["right_on"] = True
                                        blink_state["last_toggle_time"] = time.time() 
                                    state["horn"] = bool(command.get("horn", state["horn"]))

                                    # Cruise control can only be active if not braking (manual or AEB) AND in Drive mode
                                    # Also, ensure it's not activated if gas is currently pressed (client_throttle_request > 0).
                                    if not state["aeb_active"] and not state["brake"] and state["gear_mode"] == "D" and client_throttle_request == 0:
                                        requested_cc_active = bool(command.get("cc_active", state.get("cc_active", False)))
                                        if requested_cc_active and not state["cc_active"]: # CC just activated
                                            state["cc_active"] = True
                                            state["cc_target_speed"] = g_smoothed_speed_mph # Set target to current speed
                                            print(f"Cruise Control activated. Target speed: {state['cc_target_speed']:.2f} mph")
                                        elif not requested_cc_active: # CC deactivated by client
                                            state["cc_active"] = False
                                            state["cc_target_speed"] = 0
                                            print("Cruise Control deactivated by client.")
                                        # If CC was already active and client sends `cc_active: true`, update target speed if provided.
                                        # For continuous updates, the server simply maintains its internal target.
                                    else: 
                                        if state.get("cc_active", False): 
                                            print("Cruise Control deactivated due to braking, AEB, gas input, or not in Drive mode (server-side).")
                                        state["cc_active"] = False 
                                        state["cc_target_speed"] = 0 # Reset target speed

                                    # Camera commands
                                    if command.get("take_photo", False):
                                        success, msg = take_photo()
                                        print(f"Photo command: {msg}")
                                    
                                    if command.get("toggle_video", False):
                                        success, msg = toggle_video_recording()
                                        print(f"Video toggle command: {msg}")

                                    
                                    response = {
                                        "speed": g_smoothed_speed_mph, # Send the actual smoothed speed in MPH
                                        "aeb_active": state["aeb_active"],
                                        "brake": state["brake"],
                                        "throttle": state["throttle"],
                                        "current_motor_pwm": state["current_motor_pwm"],
                                        "cc_active": state.get("cc_active", False),
                                        "cc_target_speed": state.get("cc_target_speed", 0),
                                        "gear_mode": state["gear_mode"], # Send the current gear mode back
                                        "video_recording_active": video_recording_active, # Send video status
                                        "video_start_timestamp": video_start_timestamp if video_recording_active else 0, # Send start time
                                        }
                                    conn.sendall(json.dumps(response).encode('utf-8'))
                                    
                                except json.JSONDecodeError:
                                    if len(data_buffer) > 4 * 1024 * 1024: 
                                        print(f"[JSON DEBUG] Buffer too large ({len(data_buffer)} bytes) without valid JSON. Flushing buffer.")
                                        data_buffer = b""
                                    break 
                                except UnicodeDecodeError:
                                    print(f"[JSON DEBUG] UnicodeDecodeError. Flushing buffer.")
                                    data_buffer = b""
                                    break 
                                except Exception as e:
                                    print(f"Error processing command or in inner loop: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    data_buffer = b"" 

                        except socket.timeout:
                            continue 
                        except socket.error as e:
                            print(f"Socket error in command processing loop: {e}. Assuming client disconnected. Signalling server shutdown.")
                            shutdown_flag.set() 
                            break 
                        except Exception as e:
                            print(f"Error processing command or in inner loop: {e}")
                            import traceback
                            traceback.print_exc()
                            data_buffer = b"" 
            except socket.timeout: 
                if shutdown_flag.is_set():
                    print("Command thread: Shutdown detected while waiting for connection.")
                continue 
            except Exception as e:
                print(f"Error accepting command connection: {e}")
                if not shutdown_flag.is_set(): 
                    time.sleep(1) 
            finally: # This finally block ensures cleanup after each connection attempt
                if conn: # Only close if conn was successfully assigned
                    try: conn.close()
                    except: pass
                conn = None # Reset conn for the next iteration of the while loop
                if not shutdown_flag.is_set(): # Only print if not shutting down entirely
                    print("Client connection closed. Listening for new connection.")
    
    finally:
        if server_socket: 
            try: server_socket.close()
            except: pass
        print("Command thread finished.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("RC Car Command Server Starting...")
    if gpio_initialized:
        print(f"AEB will be in a grace period for {AEB_GRACE_PERIOD_SECONDS} seconds from script start.")
        print(f"AEB: Based on recent feedback, assuming obstacle detection when ir_sensor.value is 1.")
        print(f"Camera flip functionality is configured via software (OpenCV/FFmpeg) with mode: {CAMERA_FLIP_MODE}.")
        print(f"If ir_sensor.value is 0 (LEDs off, as reported), AEB should remain OFF.")


    cmd_thread_instance = threading.Thread(target=cmd_thread, daemon=True) 
    cmd_thread_instance.start()

    last_update_time = time.time() 
    try:
        while not shutdown_flag.is_set():
            current_loop_time = time.time()
            dt = current_loop_time - last_update_time 
            last_update_time = current_loop_time

            check_aeb()
            update_gpio(dt) 
            time.sleep(0.01) 

    except KeyboardInterrupt:
        print("Shutting down server by KeyboardInterrupt...")
        shutdown_flag.set()
    finally:
        print("Cleaning up server...")
        shutdown_flag.set() 

        if cmd_thread_instance and cmd_thread_instance.is_alive():
            print("Waiting for command thread to exit...")
            cmd_thread_instance.join(timeout=2.5) 
            if cmd_thread_instance.is_alive():
                print("Warning: Command thread did not exit cleanly after join attempt.")

        if gpio_initialized:
            print("Attempting to clean up GPIO resources...")
            try:
                if hasattr(headlight, 'value'): headlight.value = 0.0; headlight.close()
                if hasattr(brakeL, 'value'): brakeL.value = 0.0; brakeL.close()
                if hasattr(indL, 'value'): indL.value = 0.0; indL.close()
                if hasattr(indR, 'value'): indR.value = 0.0; indR.close()
                if hasattr(horn, 'value'): horn.value = 0.0; horn.close()

                # Ensure servo returns to center and detaches on cleanup
                if hasattr(steering_servo, 'value') and steering_servo.is_active:
                    try:
                        steering_servo.value = STEERING_CENTER_OFFSET 
                        time.sleep(0.05) 
                        steering_servo.detach()
                    except Exception as e_servo_detach:
                        print(f"Note: Error during servo detach during cleanup: {e_servo_detach}")
                if hasattr(steering_servo, 'close'): steering_servo.close()
                
                if hasattr(ir_sensor_f, 'close'): ir_sensor_f.close()
                if hasattr(ir_sensor_b, 'close'): ir_sensor_b.close()
                
                # Close Hall sensor GPIO
                if hasattr(hall_sensor, 'close'): hall_sensor.close()

                # Close motor GPIOs
                if hasattr(motor_left_fwd, 'value'): motor_left_fwd.value = 0.0; motor_left_fwd.close()
                if hasattr(motor_left_bwd, 'value'): motor_left_bwd.value = 0.0; motor_left_bwd.close()
                if hasattr(motor_right_fwd, 'value'): motor_right_fwd.value = 0.0; motor_right_fwd.close()
                if hasattr(motor_right_bwd, 'value'): motor_right_bwd.value = 0.0; motor_right_bwd.close()
                
                print("GPIO devices believed to be closed.")
            except Exception as e_gpio:
                print(f"ERROR during GPIO cleanup: {e_gpio}")
                import traceback
                traceback.print_exc()
        else:
            print("GPIO was not initialized, or dummy objects used. No hardware cleanup needed for real pins.")

        # Camera cleanup
        if picam2:
            try:
                if video_recording_active:
                    print("Stopping active video recording during shutdown.")
                    if video_recorder_encoder: picam2.stop_encoder()
                picam2.stop() # Stop the camera itself
                picam2.close()
                print("Camera closed.")
            except Exception as e:
                print(f"Error during camera cleanup: {e}")

        print("Server stopped.")
        sys.exit(0)
