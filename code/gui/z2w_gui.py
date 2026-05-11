#!/usr/bin/env python3
import pygame
import socket
import json
import datetime
import time
import math
import sys

# --- CONFIGURATION ---
RPI_HOST = "raspberrypi5.local"
CMD_PORT = 9999
WINDOW_TITLE = "RC Car Control"

# --- PYGAME INITIALIZATION ---
print("Initializing Pygame...")
try:
    pygame.init()
    print("Pygame initialized successfully.")
except Exception as e:
    print(f"FATAL: Pygame initialization failed: {e}")
    sys.exit(1)

try:
    print("Getting display info...")
    info = pygame.display.Info()
    W, H = info.current_w, info.current_h
    print(f"Display info: Width={W}, Height={H}")
    screen = pygame.display.set_mode((W, H)) # Use full available resolution
    print("Pygame screen created.")
except pygame.error as e:
    print(f"Pygame display error: {e}. Using fallback dimensions 800x480.")
    W, H = 800, 480 # Fallback dimensions
    try:
        screen = pygame.display.set_mode((W,H))
        print("Pygame screen created (fallback 800x480).")
    except Exception as e_fallback:
        print(f"FATAL: Pygame fallback screen creation failed: {e_fallback}")
        pygame.quit()
        sys.exit(1)

pygame.display.set_caption(WINDOW_TITLE)
print(f"Window title set to: {WINDOW_TITLE}")

font_size = min(W // 30, H // 20)
small_font_size = int(font_size * 0.7)
popup_font_size = int(font_size * 0.8)

try:
    font = pygame.font.SysFont(None, font_size)
    small_font = pygame.font.SysFont(None, small_font_size)
    popup_font = pygame.font.SysFont(None, popup_font_size)
    print(f"System font loaded with size {font_size}, small font {small_font_size}, popup font {popup_font_size}.")
except Exception:
    font = pygame.font.Font(None, font_size) # Pygame's default font
    small_font = pygame.font.Font(None, small_font_size) # Pygame's default font
    popup_font = pygame.font.Font(None, popup_font_size) # Pygame's default font
    print(f"Default font loaded with size {font_size}, small font {small_font_size}, popup font {popup_font_size}.")

# --- COLORS ---
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
GRAY = (150, 150, 150)
LIGHT_GRAY = (200, 200, 200)
GREEN = (0, 200, 0)
BLUE = (0, 100, 255)
DARK_BG = (30, 30, 30)
CC_COLOR_ACTIVE = (0, 255, 255)
AEB_COLOR_ACTIVE = YELLOW
AEB_COLOR_INACTIVE = DARK_BG 
POPUP_BG_COLOR = (50, 50, 50, 200) # Semi-transparent dark gray for popup
HIGHLIGHT_COLOR = (0, 150, 255) # Color for highlighted PRND button

# --- POPUP NOTIFICATION STATE ---
popup_message = None
popup_timer_start = 0
POPUP_DURATION_SEC = 5.0

# --- NETWORK SETUP ---
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connected_to_server = False
print(f"Attempting to connect to command server at {RPI_HOST}:{CMD_PORT}...")
retry_count = 0
MAX_RETRIES = 5
while not connected_to_server and retry_count < MAX_RETRIES:
    try:
        client_socket.connect((RPI_HOST, CMD_PORT))
        client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) # Disable Nagle's algorithm for low latency
        print(f"Successfully connected to command server at {RPI_HOST}:{CMD_PORT} (TCP_NODELAY enabled).")
        connected_to_server = True
    except socket.error as e:
        retry_count += 1
        msg = f"Cmd server conn failed: {e}. Retry {retry_count}/{MAX_RETRIES}..."
        print(msg)
        if 'screen' in locals() and screen:
            screen.fill(BLACK)
            err_text = font.render(msg, True, RED)
            screen.blit(err_text, (W // 2 - err_text.get_width() // 2, H // 2 - err_text.get_height() // 2))
            pygame.display.flip()
        
        if retry_count >= MAX_RETRIES:
            print("Max retries reached for command server. Proceeding without connection.")
            if 'screen' in locals() and screen:
                 screen.fill(BLACK)
                 final_err_msg = "Max retries. Running without server."
                 err_text = font.render(final_err_msg, True, RED)
                 screen.blit(err_text, (W // 2 - err_text.get_width() // 2, H // 2 - err_text.get_height() // 2))
                 pygame.display.flip()
                 pygame.time.wait(2000)
            break 
        time.sleep(3) 

print("No local camera initialization as requested.")

# --- CONTROL STATE (Client-side) ---
steer = 0.0
target_steer = 0.0
throttle = 0.0 # This is what gets sent to the server (0 or 1.0)
manual_brake_pressed_gui = False # Tracks if the user is manually pressing the brake button
manual_gas_pressed_gui = False # Tracks if the user is manually pressing the gas button

brake_pressed_ui = False # This is for UI visual feedback: True if manual brake OR AEB is active
night_mode = False
indicators = "off"
hazard = False
horn = False
speed = 0.0 # Speed received from server (now actual MPH)
cc_active = False # Cruise control active state received from server
cc_target_speed = 0 # Cruise control target speed received from server
aeb_active = False # This reflects if AEB is active on the server
current_gear = "P" # Initial gear mode: Park

# --- CAMERA CONTROL STATE (Client-side) ---
video_recording_active = False
video_start_timestamp = 0 # Unix timestamp from server, 0 if not recording

# Flags to send commands only once per click
_take_photo_pressed_this_frame = False
_toggle_video_pressed_this_frame = False


# --- UI ELEMENT DEFINITIONS (Dynamic Sizing) ---
BUTTON_SIZE_BASE = min(W // 12, H // 8)
BUTTON_MARGIN = max(5, BUTTON_SIZE_BASE // 10)

# Clock and Quit Button (Top-Left)
clock_x = BUTTON_MARGIN
clock_y = BUTTON_MARGIN
_placeholder_clock_height = font.get_linesize()
quit_button_width = int(BUTTON_SIZE_BASE * 1.0)
quit_button_height = int(BUTTON_SIZE_BASE * 0.4)
btn_quit = pygame.Rect(clock_x, clock_y + _placeholder_clock_height + BUTTON_MARGIN, quit_button_width, quit_button_height)

# PRND Sidebar (Left side, below Quit button)
PRND_BUTTON_WIDTH = int(BUTTON_SIZE_BASE * 0.8)
PRND_BUTTON_HEIGHT = int(BUTTON_SIZE_BASE * 0.8)
prnd_start_y = btn_quit.bottom + BUTTON_MARGIN * 2 # Start below quit button, with more margin
prnd_x = BUTTON_MARGIN

btn_p = pygame.Rect(prnd_x, prnd_start_y, PRND_BUTTON_WIDTH, PRND_BUTTON_HEIGHT)
btn_r = pygame.Rect(prnd_x, btn_p.bottom + BUTTON_MARGIN, PRND_BUTTON_WIDTH, PRND_BUTTON_HEIGHT)
btn_n = pygame.Rect(prnd_x, btn_r.bottom + BUTTON_MARGIN, PRND_BUTTON_WIDTH, PRND_BUTTON_HEIGHT)
btn_d = pygame.Rect(prnd_x, btn_n.bottom + BUTTON_MARGIN, PRND_BUTTON_WIDTH, PRND_BUTTON_HEIGHT)

# Top-Right Buttons (Hazard, Indicators, Night Mode, CC, Photo, Video)
num_top_right_buttons = 7 # Increased for Photo and Video buttons
top_button_size = int(BUTTON_SIZE_BASE * 0.8)
top_right_row_start_x = W - (num_top_right_buttons * top_button_size) - ((num_top_right_buttons -1) * BUTTON_MARGIN) - BUTTON_MARGIN
top_right_row_y = BUTTON_MARGIN

btn_hazard  = pygame.Rect(top_right_row_start_x, top_right_row_y, top_button_size, top_button_size)
btn_indi_l  = pygame.Rect(btn_hazard.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)
btn_indi_r  = pygame.Rect(btn_indi_l.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)
btn_night   = pygame.Rect(btn_indi_r.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)
btn_cc      = pygame.Rect(btn_night.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)
btn_photo   = pygame.Rect(btn_cc.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)
btn_video   = pygame.Rect(btn_photo.right + BUTTON_MARGIN, top_right_row_y, top_button_size, top_button_size)

# Stopwatch Display (below video button)
stopwatch_height = int(small_font.get_linesize() * 1.2) # Adjusted height
stopwatch_width = int(top_button_size * 1.5) # Make it a bit wider
stopwatch_x = btn_video.centerx - stopwatch_width // 2
stopwatch_y = btn_video.bottom + BUTTON_MARGIN


# Control Area and Remaining Space Calculation
top_elements_bottom = max(btn_quit.bottom, btn_video.bottom, btn_d.bottom, stopwatch_y + stopwatch_height) + BUTTON_MARGIN
CONTROL_AREA_HEIGHT = int(H * 0.35)
CONTROL_AREA_Y_START = H - CONTROL_AREA_HEIGHT

# Define the area that used to be the camera feed.
# It will now simply be a black background, effectively removed as a "box".
EMPTY_AREA_Y_START = top_elements_bottom
EMPTY_AREA_HEIGHT = CONTROL_AREA_Y_START - EMPTY_AREA_Y_START
EMPTY_AREA_WIDTH = W


# Steering Wheel (Left side of control area)
# Increased steering_radius to make the steering circle bigger
steering_radius = min(CONTROL_AREA_HEIGHT // 2.0, W // 6) 
steering_center_x = int(W * 0.23)
# Lift the steering circle up a bit by adjusting steering_center_y
steering_center_y = CONTROL_AREA_Y_START + CONTROL_AREA_HEIGHT // 2 - int(CONTROL_AREA_HEIGHT * 0.25) 
steering_handle_radius_factor = 0.85
steering_dragging = False
STEERING_RETURN_SPEED = 3.0

# Horn Button (Center of steering wheel)
horn_button_radius = steering_radius * 0.4

# Pedals (Right side of control area)
pedal_width = int(BUTTON_SIZE_BASE * 0.9)
pedal_height = int(BUTTON_SIZE_BASE * 1.3)
pedal_y_offset = CONTROL_AREA_Y_START + (CONTROL_AREA_HEIGHT - pedal_height) // 2
pedal_x_start = W - 2 * (pedal_width + BUTTON_MARGIN) - int(W*0.05)

btn_brake = pygame.Rect(pedal_x_start, pedal_y_offset, pedal_width, pedal_height)
btn_gas = pygame.Rect(pedal_x_start + pedal_width + BUTTON_MARGIN, pedal_y_offset, pedal_width, pedal_height)


# AEB Indicator (Left of Brake Pedal)
aeb_text_surf_placeholder = font.render("AEB", True, WHITE)
aeb_text_width = aeb_text_surf_placeholder.get_width()
aeb_text_height = aeb_text_surf_placeholder.get_height()
aeb_text_x = btn_brake.left - aeb_text_width - BUTTON_MARGIN
aeb_text_y = btn_brake.centery - aeb_text_height // 2

# Speedometer Display (Centered above pedals)
speedo_width = int(BUTTON_SIZE_BASE * 1.8)
speedo_height = int(BUTTON_SIZE_BASE * 0.6)
# Calculate the center of the combined brake and gas pedal area
pedal_area_center_x = (btn_brake.left + btn_gas.right) // 2
speedo_x = pedal_area_center_x - speedo_width // 2 # Centered above the pedal group
speedo_y = btn_gas.top - speedo_height - BUTTON_MARGIN
btn_speedo_box = pygame.Rect(speedo_x, speedo_y, speedo_width, speedo_height)


pg_clock = pygame.time.Clock()
running = True
print("Starting main Pygame loop...")

# --- MAIN LOOP ---
while running:
    dt_sec = pg_clock.tick(30) / 1000.0
    
    # Get current mouse state once per frame
    mouse_pos = pygame.mouse.get_pos()
    mouse_buttons = pygame.mouse.get_pressed()

    # Reset manual pedal states at the start of each frame before checking events/continuous state
    manual_gas_pressed_gui = False
    manual_brake_pressed_gui = False


    # --- Event Handling (for discrete events like clicks, keydowns, quit) ---
    # This loop handles events that happen once, like a button being clicked.
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left mouse button click
                # Handle TOGGLE buttons
                if btn_quit.collidepoint(mouse_pos): running = False
                elif btn_hazard.collidepoint(mouse_pos):
                    hazard = not hazard
                    if hazard: indicators = "off"
                elif btn_indi_l.collidepoint(mouse_pos):
                    indicators = "left" if indicators != "left" else "off"
                    if indicators == "left": hazard = False
                elif btn_indi_r.collidepoint(mouse_pos):
                    indicators = "right" if indicators != "right" else "off"
                    if indicators == "right": hazard = False
                elif btn_night.collidepoint(mouse_pos): night_mode = not night_mode
                elif btn_cc.collidepoint(mouse_pos):
                    # Only allow CC activation if no AEB, no manual brake, and in Drive mode
                    if not aeb_active and not manual_brake_pressed_gui and current_gear == "D": 
                        cc_active = not cc_active
                        if cc_active: 
                            cc_target_speed = int(speed) # Set target speed to current speed on activation
                            print(f"Cruise Control activated. Target speed: {cc_target_speed:.0f} mph")
                        else:
                            print("Cruise Control deactivated.")
                    elif aeb_active:
                        popup_message = "Cannot activate CC: AEB is active!"
                        popup_timer_start = time.time()
                    elif manual_brake_pressed_gui:
                         popup_message = "Cannot activate CC: Brake is pressed!"
                         popup_timer_start = time.time()
                    elif current_gear != "D":
                         popup_message = "Cannot activate CC: Must be in Drive mode!"
                         popup_timer_start = time.time()
                
                # Handle Photo and Video buttons
                elif btn_photo.collidepoint(mouse_pos):
                    _take_photo_pressed_this_frame = True # Set flag for this frame
                    popup_message = "Photo capture requested!"
                    popup_timer_start = time.time()
                elif btn_video.collidepoint(mouse_pos):
                    _toggle_video_pressed_this_frame = True # Set flag for this frame
                    if video_recording_active:
                        popup_message = "Video recording stopping..."
                    else:
                        popup_message = "Video recording starting..."
                    popup_timer_start = time.time()

                # Handle PRND buttons
                elif btn_p.collidepoint(mouse_pos):
                    current_gear = "P"
                    popup_message = "Gear: Park"
                    popup_timer_start = time.time()
                    cc_active = False # Deactivate CC if gear changes
                elif btn_r.collidepoint(mouse_pos):
                    current_gear = "R"
                    popup_message = "Gear: Reverse"
                    popup_timer_start = time.time()
                    cc_active = False # Deactivate CC if gear changes
                elif btn_n.collidepoint(mouse_pos):
                    current_gear = "N"
                    popup_message = "Gear: Neutral"
                    popup_timer_start = time.time()
                    cc_active = False # Deactivate CC if gear changes
                elif btn_d.collidepoint(mouse_pos):
                    current_gear = "D"
                    popup_message = "Gear: Drive"
                    popup_timer_start = time.time()
                
                # Handle DRAG START for steering wheel
                elif (math.hypot(mouse_pos[0] - steering_center_x, mouse_pos[1] - steering_center_y) <= steering_radius and
                      math.hypot(mouse_pos[0] - steering_center_x, mouse_pos[1] - steering_center_y) > horn_button_radius):
                    steering_dragging = True
                    # Update steer immediately on click
                    x, y = mouse_pos
                    dx = x - steering_center_x
                    dy = y - steering_center_y
                    
                    # Calculate angle (0 at top, positive clockwise)
                    # Note: Pygame Y-axis is inverted (down is positive Y)
                    # So to get standard Cartesian Y (up is positive), we use -dy
                    # atan2(y, x)
                    angle_rad = math.atan2(dx, -dy) # This gives angle: 0 (top), pi/2 (right), pi (bottom), -pi/2 (left)

                    # If the angle is in the bottom half of the circle (e.g., from pi/2 to pi or -pi to -pi/2),
                    # clamp the steering value to the maximum left/right.
                    if angle_rad > math.pi / 2.0: # Mouse is in bottom-right quadrant
                        steer = 1.0
                    elif angle_rad < -math.pi / 2.0: # Mouse is in bottom-left quadrant
                        steer = -1.0
                    else: # Mouse is in top half of the circle (from -pi/2 to pi/2), map linearly
                        # Map [-pi/2, pi/2] to [-1.0, 1.0]
                        steer = angle_rad / (math.pi / 2.0)
                    
                    # Ensure steer is strictly within -1.0 to 1.0
                    steer = max(-1.0, min(1.0, steer))

                    target_steer = steer
                    horn = False # Disable horn when steering starts

        elif event.type == pygame.MOUSEMOTION:
            if steering_dragging:
                # Handle DRAG MOTION for steering wheel
                x, y = event.pos
                dx = x - steering_center_x
                dy = y - steering_center_y
                
                # Calculate angle (0 at top, positive clockwise)
                # Note: Pygame Y-axis is inverted (down is positive Y)
                # So to get standard Cartesian Y (up is positive), we use -dy
                # atan2(y, x)
                angle_rad = math.atan2(dx, -dy) # This gives angle: 0 (top), pi/2 (right), pi (bottom), -pi/2 (left)

                # If the angle is in the bottom half of the circle (e.g., from pi/2 to pi or -pi to -pi/2),
                # clamp the steering value to the maximum left/right.
                if angle_rad > math.pi / 2.0: # Mouse is in bottom-right quadrant
                    steer = 1.0
                elif angle_rad < -math.pi / 2.0: # Mouse is in bottom-left quadrant
                    steer = -1.0
                else: # Mouse is in top half of the circle (from -pi/2 to pi/2), map linearly
                    # Map [-pi/2, pi/2] to [-1.0, 1.0]
                    steer = angle_rad / (math.pi / 2.0)

                # Ensure steer is strictly within -1.0 to 1.0
                steer = max(-1.0, min(1.0, steer))

                target_steer = steer
                horn = False # Keep horn disabled while steering

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1: # Left mouse button release
                # Handle DRAG END for steering wheel
                if steering_dragging:
                    steering_dragging = False
                    target_steer = 0.0

    # --- Continuous State Handling (for held-down buttons like pedals and horn) ---
    # This block runs every frame, checking the CURRENT state of the mouse.
    
    # Horn - Only allow horn if not currently steering
    if mouse_buttons[0] and math.hypot(mouse_pos[0] - steering_center_x, mouse_pos[1] - steering_center_y) <= horn_button_radius:
        if not steering_dragging: # Only allow horn if not steering
            horn = True
        else:
            horn = False # Horn remains off if steering
    else:
        horn = False

    # Pedals
    if mouse_buttons[0] and btn_gas.collidepoint(mouse_pos):
        manual_gas_pressed_gui = True
    
    if mouse_buttons[0] and btn_brake.collidepoint(mouse_pos):
        manual_brake_pressed_gui = True

    # Determine `throttle` and `brake` to send to server based on manual input and current gear.
    # AEB state (aeb_active) is received from server and should influence local UI,
    # but not the "brake" command sent to the server, as the server handles AEB independently.
    
    # Default values for command to send
    send_throttle = 0.0
    send_brake = False

    # Logic based on gear mode
    if current_gear == "P": # Park
        send_throttle = 0.0
        send_brake = True # Force brake in Park
        cc_active = False # Deactivate CC if in Park
        if manual_gas_pressed_gui:
            popup_message = "Gas disabled in Park!"
            popup_timer_start = time.time()
    elif current_gear == "N": # Neutral
        send_throttle = 0.0
        send_brake = False # No brake in Neutral (unless manually pressed)
        cc_active = False # Deactivate CC if in Neutral
        if manual_gas_pressed_gui:
            popup_message = "Gas disabled in Neutral!"
            popup_timer_start = time.time()
        if manual_brake_pressed_gui:
            popup_message = "Brake disabled in Neutral (car can still roll)!"
            popup_timer_start = time.time()
            send_brake = False # Override manual brake for Neutral
    elif current_gear == "R": # Reverse
        if manual_gas_pressed_gui:
            send_throttle = -1.0 # Negative throttle for reverse
        else:
            send_throttle = 0.0
        send_brake = manual_brake_pressed_gui
        cc_active = False # Deactivate CC if in Reverse
    elif current_gear == "D": # Drive
        if manual_gas_pressed_gui:
            send_throttle = 1.0 # Positive throttle for forward
        else:
            send_throttle = 0.0
        send_brake = manual_brake_pressed_gui
        # CC logic handled in MOUSEBUTTONDOWN for activation/deactivation.
        # If CC is active, send_throttle will be overridden by server's CC logic.

    # If manual brake is pressed, it overrides gas input regardless of gear (except N, P where it's already forced)
    if manual_brake_pressed_gui and current_gear not in ["P", "N"]:
        send_brake = True
        send_throttle = 0.0 # Brake overrides gas
        # If manual brake is pressed, client-side CC should also be deactivated immediately for consistency
        if cc_active:
            cc_active = False 
            popup_message = "Cruise Control deactivated by manual brake."
            popup_timer_start = time.time()
    
    # Determine `brake_pressed_ui` for visual feedback (combines manual brake and AEB)
    # This variable is only for local UI display and does not affect the command payload.
    brake_pressed_ui = manual_brake_pressed_gui or aeb_active
    

    # Smooth steering return to center
    if not steering_dragging and abs(steer - target_steer) > 0.01:
        if steer > target_steer: steer = max(steer - STEERING_RETURN_SPEED * dt_sec, target_steer)
        else: steer = min(steer + STEERING_RETURN_SPEED * dt_sec, target_steer)
    elif not steering_dragging and abs(steer - target_steer) <= 0.01:
         steer = target_steer

    # --- Drawing ---
    screen.fill(DARK_BG)

    # Clock
    now = datetime.datetime.now()
    time_str = now.strftime("%I:%M:%S %p")
    clock_surf = font.render(time_str, True, WHITE)
    screen.blit(clock_surf, (clock_x, clock_y))
    
    btn_quit = pygame.Rect(clock_x, clock_y + clock_surf.get_height() + BUTTON_MARGIN, quit_button_width, quit_button_height)
    pygame.draw.rect(screen, RED, btn_quit, border_radius=5)
    quit_text_surf = font.render("QUIT", True, WHITE)
    screen.blit(quit_text_surf, (btn_quit.centerx - quit_text_surf.get_width()//2, btn_quit.centery - quit_text_surf.get_height()//2))

    # PRND Sidebar Drawing
    prnd_buttons = [("P", btn_p), ("R", btn_r), ("N", btn_n), ("D", btn_d)]
    for gear_char, rect in prnd_buttons:
        color = HIGHLIGHT_COLOR if current_gear == gear_char else LIGHT_GRAY
        pygame.draw.rect(screen, color, rect, border_radius=5)
        gear_text_surf = font.render(gear_char, True, BLACK)
        screen.blit(gear_text_surf, (rect.centerx - gear_text_surf.get_width()//2, rect.centery - gear_text_surf.get_height()//2))


    # Top-Right Buttons
    pygame.draw.rect(screen, RED if hazard else LIGHT_GRAY, btn_hazard, border_radius=5)
    screen.blit(font.render("H", True, BLACK), (btn_hazard.centerx - font.size("H")[0]//2, btn_hazard.centery - font.size("H")[1]//2))

    pygame.draw.rect(screen, YELLOW if indicators == "left" else LIGHT_GRAY, btn_indi_l, border_radius=5)
    screen.blit(font.render("L", True, BLACK), (btn_indi_l.centerx - font.size("L")[0]//2, btn_indi_l.centery - font.size("L")[1]//2))

    pygame.draw.rect(screen, YELLOW if indicators == "right" else LIGHT_GRAY, btn_indi_r, border_radius=5)
    screen.blit(font.render("R", True, BLACK), (btn_indi_r.centerx - font.size("R")[0]//2, btn_indi_r.centery - font.size("R")[1]//2))

    pygame.draw.rect(screen, BLUE if night_mode else LIGHT_GRAY, btn_night, border_radius=5)
    screen.blit(font.render("N", True, WHITE if night_mode else BLACK), (btn_night.centerx - font.size("N")[0]//2, btn_night.centery - font.size("N")[1]//2))

    # CC Button
    pygame.draw.rect(screen, CC_COLOR_ACTIVE if cc_active else LIGHT_GRAY, btn_cc, border_radius=5)
    cc_label_surf = font.render("CC", True, BLACK)
    label_x = btn_cc.centerx - cc_label_surf.get_width() // 2
    label_y = btn_cc.centery - cc_label_surf.get_height() // 2 
    screen.blit(cc_label_surf, (label_x, label_y))
    
    # Photo Button
    pygame.draw.rect(screen, LIGHT_GRAY, btn_photo, border_radius=5)
    # Using an emoji for the camera icon
    photo_text_surf = font.render("📸", True, BLACK) 
    screen.blit(photo_text_surf, (btn_photo.centerx - photo_text_surf.get_width()//2, btn_photo.centery - photo_text_surf.get_height()//2))

    # Video Button
    video_button_color = RED if video_recording_active else LIGHT_GRAY
    pygame.draw.rect(screen, video_button_color, btn_video, border_radius=5)
    video_text = "End Video" if video_recording_active else "Start Video"
    video_text_surf = small_font.render(video_text, True, BLACK)
    screen.blit(video_text_surf, (btn_video.centerx - video_text_surf.get_width()//2, btn_video.centery - video_text_surf.get_height()//2))

    # Stopwatch Display
    pygame.draw.rect(screen, BLACK, (stopwatch_x, stopwatch_y, stopwatch_width, stopwatch_height), border_radius=5)
    if video_recording_active and video_start_timestamp > 0:
        elapsed_time = time.time() - video_start_timestamp
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        time_display = f"{minutes:02d}:{seconds:02d}"
        stopwatch_surf = small_font.render(time_display, True, WHITE)
    else:
        stopwatch_surf = small_font.render("00:00", True, GRAY)
    
    screen.blit(stopwatch_surf, (stopwatch_x + (stopwatch_width - stopwatch_surf.get_width()) // 2, stopwatch_y + (stopwatch_height - stopwatch_surf.get_height()) // 2))


    # Steering Wheel
    pygame.draw.circle(screen, GRAY, (steering_center_x, steering_center_y), int(steering_radius), 0)
    pygame.draw.circle(screen, LIGHT_GRAY, (steering_center_x, steering_center_y), int(steering_radius), 3)
    # Calculate handle position based on steer value
    # Map steer (-1 to 1) back to angle (-pi/2 to pi/2, centered at 0 for top)
    handle_angle_rad = steer * (math.pi / 2.0) 
    handle_x = steering_center_x + steering_radius * steering_handle_radius_factor * math.sin(handle_angle_rad)
    handle_y = steering_center_y - steering_radius * steering_handle_radius_factor * math.cos(handle_angle_rad) # -cos for Y-axis up
    pygame.draw.line(screen, WHITE, (steering_center_x, steering_center_y), (int(handle_x), int(handle_y)), 8)
    
    # Horn Button
    # Horn button color changes based on whether it's active AND not steering.
    horn_button_color = RED if horn else BLACK
    pygame.draw.circle(screen, horn_button_color, (steering_center_x, steering_center_y), int(horn_button_radius), 0)
    horn_text_surf = font.render("Horn", True, WHITE)
    screen.blit(horn_text_surf, (steering_center_x - horn_text_surf.get_width()//2, steering_center_y - horn_text_surf.get_height()//2))

    # Pedals
    pygame.draw.rect(screen, RED if brake_pressed_ui else GRAY, btn_brake, border_radius=8)
    brake_text_surf = font.render("Brake", True, WHITE)
    screen.blit(brake_text_surf, (btn_brake.centerx - brake_text_surf.get_width()//2, btn_brake.centery - brake_text_surf.get_height()//2))

    pygame.draw.rect(screen, GREEN if manual_gas_pressed_gui else GRAY, btn_gas, border_radius=8)
    gas_text_surf = font.render("Gas", True, WHITE)
    screen.blit(gas_text_surf, (btn_gas.centerx - gas_text_surf.get_width()//2, btn_gas.centery - gas_text_surf.get_height()//2))

    # AEB Indicator Text
    aeb_indicator_color = AEB_COLOR_ACTIVE if aeb_active else WHITE
    aeb_text_surf = font.render("AEB", True, aeb_indicator_color)
    screen.blit(aeb_text_surf, (aeb_text_x, aeb_text_y))

    # Speedometer
    pygame.draw.rect(screen, BLACK, btn_speedo_box, border_radius=5)
    speed_text_surf = font.render(f"{speed:.1f} mph", True, WHITE) # Display with 1 decimal place
    speed_text_x = btn_speedo_box.centerx - speed_text_surf.get_width() // 2
    speed_text_y = btn_speedo_box.centery - speed_text_surf.get_height() // 2
    screen.blit(speed_text_surf, (speed_text_x, speed_text_y))

    # --- Display Popup Notification ---
    if popup_message:
        current_time_popup = time.time()
        if current_time_popup - popup_timer_start < POPUP_DURATION_SEC:
            popup_text_surf = popup_font.render(popup_message, True, WHITE)
            popup_rect_height = popup_text_surf.get_height() + 20 
            popup_rect_width = popup_text_surf.get_width() + 40
            
            popup_rect_width = min(popup_rect_width, W - 20)
            
            popup_rect_x = (W - popup_rect_width) // 2
            popup_rect_y = EMPTY_AREA_Y_START + 10 # Position in the empty area (was camera area)

            bg_surface = pygame.Surface((popup_rect_width, popup_rect_height), pygame.SRCALPHA)
            bg_surface.fill(POPUP_BG_COLOR) 
            screen.blit(bg_surface, (popup_rect_x, popup_rect_y))
            
            text_x = popup_rect_x + (popup_rect_width - popup_text_surf.get_width()) // 2
            text_y = popup_rect_y + (popup_rect_height - popup_text_surf.get_height()) // 2
            screen.blit(popup_text_surf, (text_x, text_y))
        else:
            popup_message = None

    pygame.display.flip()


    # --- Send Command to Server ---
    if connected_to_server:
        command_payload = {
            "steer": steer,
            "throttle": send_throttle, # Use the new send_throttle
            "brake": send_brake,       # Use the new send_brake
            "lights": False, 
            "night_mode": night_mode,
            "indicators": indicators,
            "hazard": hazard,
            "horn": horn,
            "cc_active": cc_active,
            "cc_target_speed": cc_target_speed,
            "gear_mode": current_gear, # Send the current gear mode
            "quit": False,
            "take_photo": _take_photo_pressed_this_frame, # Send photo command flag
            "toggle_video": _toggle_video_pressed_this_frame, # Send video toggle command flag
        }
        
        # Reset flags after creating payload for this frame
        _take_photo_pressed_this_frame = False
        _toggle_video_pressed_this_frame = False

        try:
            client_socket.sendall(json.dumps(command_payload).encode('utf-8'))
            client_socket.settimeout(0.5)
            response_data = client_socket.recv(1024)
            client_socket.settimeout(None)

            if response_data:
                response_json = json.loads(response_data.decode('utf-8'))
                speed = response_json.get("speed", speed) # Update speed from server
                aeb_active = response_json.get("aeb_active", aeb_active)
                
                cc_active = response_json.get("cc_active", cc_active)
                cc_target_speed = response_json.get("cc_target_speed", cc_target_speed)
                current_gear = response_json.get("gear_mode", current_gear) # Update gear mode from server

                video_recording_active = response_json.get("video_recording_active", video_recording_active)
                video_start_timestamp = response_json.get("video_start_timestamp", video_start_timestamp)

        except socket.timeout:
            pass # No response in time, continue as normal
        except socket.error as e:
            print(f"Socket error during send/recv: {e}. Connection likely lost.")
            connected_to_server = False
            screen.fill(BLACK)
            err_text = font.render(f"Connection to server lost. Check server.", True, RED)
            screen.blit(err_text, (W // 2 - err_text.get_width() // 2, H // 2 - err_text.get_height() // 2))
            pygame.display.flip()
            time.sleep(2)
        except json.JSONDecodeError:
            print("Received invalid JSON response from server.")
        except Exception as e:
            print(f"Error sending command or receiving response: {e}")

# --- Cleanup ---
print("Exiting RC Car GUI...")

if connected_to_server:
    print("Sending quit command to server...")
    try:
        quit_command_payload = {
            "quit": True,
            "steer": 0, "throttle": 0, "brake": True, 
            "lights": False, "night_mode": False, "indicators": "off", 
            "hazard": False, "horn": False, "take_photo": False, # Ensure these are False on quit
            "toggle_video": False, # Ensure these are False on quit
            "cc_active": False, "cc_target_speed": 0,
            "gear_mode": current_gear # Send current gear mode on quit
        }
        client_socket.sendall(json.dumps(quit_command_payload).encode('utf-8'))
        time.sleep(0.2)
    except socket.error as e:
        print(f"Error sending quit command to server: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while sending quit command: {e}")


if client_socket:
    try:
        client_socket.close()
        print("Client socket closed.")
    except Exception as e:
        print(f"Error closing client socket: {e}")

pygame.quit()
print("Pygame quit.")
sys.exit()

