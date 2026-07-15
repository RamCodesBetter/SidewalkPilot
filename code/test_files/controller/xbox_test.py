import pygame
import sys
import time

# --- CONFIGURATION ---
WINDOW_TITLE = "Xbox Controller Tester"
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# --- PYGAME INITIALIZATION ---
print("Initializing Pygame...")
try:
    pygame.init()
    pygame.display.set_caption(WINDOW_TITLE)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font = pygame.font.SysFont(None, 30) # Default font, size 30
    print("Pygame initialized successfully.")
except Exception as e:
    print(f"FATAL: Pygame initialization failed: {e}")
    sys.exit(1)

# --- JOYSTICK INITIALIZATION ---
print("Initializing joysticks...")
pygame.joystick.init()
joystick_count = pygame.joystick.get_count()
print(f"Detected {joystick_count} joystick(s).")

joystick = None
if joystick_count > 0:
    try:
        joystick = pygame.joystick.Joystick(0) # Get the first joystick
        joystick.init()
        print(f"Initialized joystick: {joystick.get_name()}")
        print(f"Number of axes: {joystick.get_numaxes()}")
        print(f"Number of buttons: {joystick.get_numbuttons()}")
        print(f"Number of hats: {joystick.get_numhats()}")
    except pygame.error as e:
        print(f"Error initializing joystick: {e}")
        joystick = None
else:
    print("No joystick detected. Please connect your Xbox controller.")

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
RED = (200, 0, 0)
BLUE = (0, 0, 200)

# --- DISPLAY MESSAGES ---
messages = []
MAX_MESSAGES = 15

def add_message(msg, color=WHITE):
    """Adds a message to the display list."""
    messages.append({"text": msg, "color": color, "timestamp": time.time()})
    if len(messages) > MAX_MESSAGES:
        messages.pop(0) # Remove oldest message if list is full

# --- MAIN LOOP ---
running = True
add_message("Press buttons or move sticks on your Xbox controller.", GREEN)
add_message("Look at the console for detailed output.", GREEN)
add_message("Press ESC or close window to quit.", GREEN)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
        
        # --- Joystick Events ---
        if joystick:
            if event.type == pygame.JOYBUTTONDOWN:
                msg = f"Button {event.button} pressed!"
                print(msg)
                add_message(msg, BLUE)
            elif event.type == pygame.JOYBUTTONUP:
                msg = f"Button {event.button} released!"
                print(msg)
                add_message(msg, WHITE)
            elif event.type == pygame.JOYAXISMOTION:
                # Axis values typically range from -1.0 to 1.0
                # Triggers might be 0.0 to 1.0 or -1.0 to 1.0 depending on controller/driver
                msg = f"Axis {event.axis} moved to {event.value:.3f}"
                print(msg)
                add_message(msg)
            elif event.type == pygame.JOYHATMOTION:
                # Hat values are tuples (x, y) where -1, 0, 1 represent direction
                # E.g., (1, 0) is right, (0, 1) is up, (-1, -1) is down-left
                msg = f"Hat {event.hat} moved to {event.value}"
                print(msg)
                add_message(msg)
            elif event.type == pygame.JOYDEVICEADDED:
                add_message("Joystick connected!", GREEN)
                print("Joystick connected! Re-initializing...")
                # Re-initialize joysticks in case a new one was added or re-connected
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    joystick = pygame.joystick.Joystick(0)
                    joystick.init()
                    print(f"Re-initialized joystick: {joystick.get_name()}")
            elif event.type == pygame.JOYDEVICEREMOVED:
                add_message("Joystick disconnected!", RED)
                print("Joystick disconnected!")
                joystick = None # Clear joystick reference

    # --- Drawing ---
    screen.fill(BLACK) # Clear screen

    y_offset = 50
    for msg_data in messages:
        text_surface = font.render(msg_data["text"], True, msg_data["color"])
        screen.blit(text_surface, (50, y_offset))
        y_offset += text_surface.get_height() + 5

    pygame.display.flip()
    pygame.time.Clock().tick(30) # Limit frame rate

# --- Cleanup ---
print("Exiting controller tester...")
if joystick:
    joystick.quit()
pygame.joystick.quit()
pygame.quit()
sys.exit()
