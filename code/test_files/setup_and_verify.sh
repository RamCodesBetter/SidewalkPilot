#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_section() {
  printf '\n== %s ==\n' "$1"
}

run_cmd() {
  printf '\n$ %s\n' "$*"
  "$@"
}

prompt_continue() {
  printf '\nPress Enter to continue...'
  read -r _
}

print_section "RC Car Setup And Verification"
printf 'Working directory: %s\n' "$SCRIPT_DIR"

print_section "1. System Package Install"
printf 'This will update apt metadata and install the common packages used by the RC car stack.\n'
run_cmd sudo apt update
run_cmd sudo apt install -y \
  git curl wget vim tmux htop \
  python3 python3-pip python3-venv \
  python3-gpiozero python3-serial python3-psutil python3-pygame \
  python3-opencv python3-numpy \
  v4l-utils usbutils bluetooth bluez bluez-tools \
  joystick evtest ffmpeg

print_section "2. Python Package Verification"
run_cmd python3 - <<'PY'
mods = ["serial", "psutil", "pygame", "gpiozero", "cv2", "numpy"]
for m in mods:
    try:
        __import__(m)
        print(f"{m}: OK")
    except Exception as e:
        print(f"{m}: FAIL -> {e}")
PY

print_section "3. USB Device Inventory"
run_cmd lsusb
printf '\nVideo devices:\n'
run_cmd bash -lc 'ls /dev/video* 2>/dev/null || true'
printf '\nSerial USB devices:\n'
run_cmd bash -lc 'ls /dev/ttyUSB* 2>/dev/null || true'

print_section "4. Camera Verification"
run_cmd v4l2-ctl --list-devices
run_cmd bash -lc 'v4l2-ctl -d /dev/video0 --all || true'
run_cmd python3 - <<'PY'
import cv2
cap = cv2.VideoCapture('/dev/video0')
print("camera opened:", cap.isOpened())
ret, frame = cap.read()
print("frame read:", ret)
print("frame shape:", None if frame is None else frame.shape)
cap.release()
PY
printf '\nIf you want a live preview, run this manually in another terminal:\n'
printf "ffplay -f v4l2 -video_size 640x480 -i /dev/video0\n"

print_section "5. LiDAR Verification"
run_cmd python3 - <<'PY'
import serial.tools.list_ports
ports = list(serial.tools.list_ports.comports())
if not ports:
    print("No serial ports found.")
for p in ports:
    print(p.device, "-", p.description)
PY
run_cmd bash -lc 'dmesg | grep -i ttyUSB | tail -n 20 || true'
run_cmd python3 - <<'PY'
import os
import serial
port = '/dev/ttyUSB0'
if not os.path.exists(port):
    print(f"{port} not found")
else:
    ser = serial.Serial(port, 230400, timeout=1)
    data = ser.read(100)
    print("bytes read:", len(data))
    print("sample:", data[:20])
    ser.close()
PY

print_section "6. Bluetooth Service Verification"
run_cmd sudo systemctl enable bluetooth
run_cmd sudo systemctl start bluetooth
run_cmd systemctl status bluetooth --no-pager
run_cmd bluetoothctl show
printf '\nTo pair a controller manually, run:\n'
cat <<'EOF'
bluetoothctl
power on
agent on
default-agent
scan on
pair XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
info XX:XX:XX:XX:XX:XX
quit
EOF

print_section "7. Joystick Verification"
run_cmd python3 - <<'PY'
import pygame
pygame.init()
pygame.joystick.init()
print("joystick count:", pygame.joystick.get_count())
for i in range(pygame.joystick.get_count()):
    j = pygame.joystick.Joystick(i)
    j.init()
    print(i, j.get_name(), "axes", j.get_numaxes(), "buttons", j.get_numbuttons())
PY
printf '\nIf your controller creates /dev/input/js0, you can test it manually with:\n'
printf "jstest /dev/input/js0\n"

print_section "8. Hall Sensor Verification"
run_cmd python3 - <<'PY'
from gpiozero import DigitalInputDevice
hall = DigitalInputDevice(24, pull_up=True)
print("hall current value:", hall.value)
hall.close()
PY
printf '\nFor a full hall sensor pulse test, run manually:\n'
printf "python3 \"CODE/TEST FILES/hall_sensor_test.py\"\n"

print_section "9. Front Ultrasonic Verification"
run_cmd python3 - <<'PY'
from gpiozero import DigitalOutputDevice, DigitalInputDevice
trig = DigitalOutputDevice(5, initial_value=False)
echo = DigitalInputDevice(6, pull_up=False)
print("front ultrasonic GPIO opened OK")
trig.close()
echo.close()
PY
printf '\nFor the full ultrasonic interactive test, run manually:\n'
printf "python3 \"CODE/TEST FILES/ultrasonic_test.py\"\n"

print_section "10. Servo And Motor Sanity Test"
printf 'Only continue if the wheels are off the ground.\n'
prompt_continue
run_cmd python3 - <<'PY'
from gpiozero import PWMOutputDevice, Servo
import time

servo = Servo(12, min_pulse_width=1/1000, max_pulse_width=2/1000, frame_width=20/1000)
mrf = PWMOutputDevice(19, frequency=1000, initial_value=0)
mrb = PWMOutputDevice(20, frequency=1000, initial_value=0)
mlf = PWMOutputDevice(25, frequency=1000, initial_value=0)
mlb = PWMOutputDevice(13, frequency=1000, initial_value=0)

print("center servo")
servo.value = 0
time.sleep(1)
print("right servo")
servo.value = 0.5
time.sleep(1)
print("left servo")
servo.value = -0.5
time.sleep(1)

print("motors forward test")
mrf.value = 0.6
mlb.value = 0.6
time.sleep(3)

mrf.value = 0
mlb.value = 0

print("motors backward test")
mrb.value = 0.6
mlf.value = 0.6
time.sleep(3)

print("stop")
for d in [mrf, mrb, mlf, mlb]:
    d.value = 0
servo.value = 0

for d in [servo, mrf, mrb, mlf, mlb]:
    d.close()
PY

print_section "11. Controller Preflight"
run_cmd python3 - <<'PY'
import os
import cv2
import serial.tools.list_ports
import pygame

print("video devices:", [d for d in os.listdir('/dev') if d.startswith('video')])
print("serial ports:", [p.device for p in serial.tools.list_ports.comports()])
pygame.init()
pygame.joystick.init()
print("joysticks:", pygame.joystick.get_count())
cap = cv2.VideoCapture('/dev/video0')
print("camera opened:", cap.isOpened())
cap.release()
PY

print_section "12. Run Current Controller"
printf 'When you are ready to start the current controller, run:\n'
printf "python3 \"CODE/CONTROLLER/CURRENT/rc_car.py\"\n"

print_section "Done"
printf 'Setup and verification sequence complete.\n'
