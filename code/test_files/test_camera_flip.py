import cv2
from picamera2 import Picamera2
import datetime
import time
import os

PHOTO_DIR = "/home/Ram/Desktop/rc_car_media/test_photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

print("--- Starting Camera Flip Test Script ---")

picam2 = None
try:
    # Initialize Picamera2
    picam2 = Picamera2()
    camera_config = picam2.create_still_configuration(main={"size": (1280, 720)}) # Use a common resolution
    picam2.configure(camera_config)
    picam2.start()
    print("Picamera2 initialized and started.")
    time.sleep(2) # Allow camera to warm up

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    original_filename = os.path.join(PHOTO_DIR, f"test_original_{timestamp}.jpg")
    flipped_filename = os.path.join(PHOTO_DIR, f"test_flipped_{timestamp}.jpg")

    # Capture original photo
    picam2.capture_file(original_filename)
    print(f"Original photo captured: {original_filename}")

    # Attempt to flip with OpenCV
    print(f"Attempting to flip photo: {original_filename}")
    img = cv2.imread(original_filename)

    if img is not None:
        # -1 means flip both horizontally and vertically (180 degree rotation)
        flipped_img = cv2.flip(img, -1) 
        cv2.imwrite(flipped_filename, flipped_img)
        print(f"Flipped photo saved: {flipped_filename}")
    else:
        print(f"ERROR: Could not read original photo {original_filename} for flipping. Is it corrupted or empty?")

except Exception as e:
    print(f"An error occurred during camera test: {e}")
    import traceback
    traceback.print_exc()
finally:
    if picam2:
        try:
            picam2.stop()
            picam2.close()
            print("Camera stopped and closed.")
        except Exception as e_close:
            print(f"Error closing camera: {e_close}")
    print("--- Camera Flip Test Script Finished ---")

