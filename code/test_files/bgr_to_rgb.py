import cv2
import os

# Set your folders
input_path = '/Users/ramsabavat/Desktop/rc_car_code/media/photos/2026_05_03_run_1'
output_path = '/Users/ramsabavat/Downloads/rgb_images_1'

if not os.path.exists(output_path):
    os.makedirs(output_path)

for filename in os.listdir(input_path):
    if filename.endswith((".jpg", ".png", ".jpeg")):
        img = cv2.imread(os.path.join(input_path, filename))
        
        # The Magic Switch: Convert BGR to RGB
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        cv2.imwrite(os.path.join(output_path, filename), rgb_img)

print("Batch conversion complete!")