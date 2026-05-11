#!/usr/bin/python3
import serial
import struct
import math
import pygame
import sys
import time

# --- LiDAR Configuration ---
SERIAL_PORT = '/dev/ttyUSB0'  # Adjust if your LiDAR is on a different port
BAUD_RATE = 230400
PACKET_LENGTH = 47
MEASUREMENT_POINTS_PER_PACKET = 12

# --- Pygame Configuration ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
CENTER_X, CENTER_Y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
LIDAR_DISPLAY_RADIUS = 350  # Max radius for LiDAR points on screen
POINT_SIZE = 2
BACKGROUND_COLOR = (0, 0, 0)  # Black
LIDAR_POINT_COLOR = (0, 255, 0) # Green
INFO_TEXT_COLOR = (255, 255, 255) # White
INFO_BACKGROUND_COLOR = (50, 50, 50, 180) # Dark grey with some transparency
CLICKED_POINT_COLOR = (255, 0, 0) # Red for clicked point

# --- Data Structure for Lidar Points ---
class LidarPoint:
    def __init__(self, angle_deg, distance_mm, confidence):
        self.angle_deg = angle_deg
        self.distance_mm = distance_mm
        self.confidence = confidence
        self.x = 0
        self.y = 0
        self.screen_x = 0
        self.screen_y = 0
        self.is_valid = True

    def calculate_cartesian(self):
        # Convert distance from mm to meters for display scaling
        distance_m = self.distance_mm / 1000.0

        # LD19 uses a left-handed coordinate system (clockwise from 0 degrees/front)
        # Standard polar to Cartesian (with 0 deg on positive Y, clockwise increase):
        # X = r * sin(angle_radians)
        # Y = r * cos(angle_radians)

        angle_rad = math.radians(self.angle_deg)

        # To flip 180 degrees (mirror horizontally AND vertically):
        # Negate both X and Y coordinate calculations
        self.x = -distance_m * math.sin(angle_rad) # X-coordinate (flipped)
        self.y = -distance_m * math.cos(angle_rad) # Y-coordinate (flipped)

    def calculate_screen_coordinates(self, max_lidar_range_m):
        if not self.is_valid:
            self.screen_x = -1
            self.screen_y = -1
            return

        # Scale X and Y coordinates to fit within the display radius
        scale_factor = LIDAR_DISPLAY_RADIUS / max_lidar_range_m

        self.screen_x = int(CENTER_X + self.x * scale_factor)
        self.screen_y = int(CENTER_Y - self.y * scale_factor) # Subtract for Y because Pygame Y increases downwards

# --- Lidar Data Parser ---
class LidarParser:
    def __init__(self, port, baudrate):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.buffer = b''
        self.current_scan_points = []
        self.last_full_scan_points = []

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Connected to LiDAR on {self.port} at {self.baudrate} baud.")
            return True
        except serial.SerialException as e:
            print(f"Error opening serial port {self.port}: {e}")
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Disconnected from LiDAR.")

    def read_data(self):
        if not self.ser or not self.ser.is_open:
            return

        bytes_to_read = self.ser.in_waiting
        if bytes_to_read:
            self.buffer += self.ser.read(bytes_to_read)

        while len(self.buffer) >= PACKET_LENGTH:
            header_index = self.buffer.find(0x54)

            if header_index == -1:
                self.buffer = b''
                break
            elif header_index > 0:
                self.buffer = self.buffer[header_index:]
                continue

            if len(self.buffer) < PACKET_LENGTH:
                break

            packet = self.buffer[:PACKET_LENGTH]

            if packet[1] != 0x2C:
                self.buffer = self.buffer[1:]
                continue

            try:
                speed_raw, start_angle_raw = struct.unpack('<H H', packet[2:6])
                speed_dps = speed_raw / 100.0
                start_angle = start_angle_raw / 100.0

                data_bytes = packet[6:42]

                end_angle_raw, timestamp_raw, crc = struct.unpack('<H H B', packet[42:47])
                end_angle = end_angle_raw / 100.0

                if end_angle < start_angle:
                    end_angle += 360.0

                points_in_packet = []
                for i in range(MEASUREMENT_POINTS_PER_PACKET):
                    offset = i * 3
                    distance_raw = struct.unpack('<H', data_bytes[offset:offset+2])[0]
                    confidence = data_bytes[offset+2]

                    if MEASUREMENT_POINTS_PER_PACKET > 1:
                        angle_step = (end_angle - start_angle) / (MEASUREMENT_POINTS_PER_PACKET - 1)
                        point_angle = start_angle + angle_step * i
                    else:
                        point_angle = start_angle

                    point_angle = point_angle % 360

                    if distance_raw == 0:
                        is_valid = False
                    else:
                        is_valid = True

                    point = LidarPoint(point_angle, distance_raw, confidence)
                    point.is_valid = is_valid
                    points_in_packet.append(point)

                self.current_scan_points.extend(points_in_packet)

                if len(self.current_scan_points) > 500:
                    self.last_full_scan_points = self.current_scan_points
                    self.current_scan_points = []

            except struct.error as e:
                print(f"Struct unpacking error: {e}. Packet: {packet.hex()}")
            except Exception as e:
                print(f"Error parsing packet: {e}. Packet: {packet.hex()}")

            self.buffer = self.buffer[PACKET_LENGTH:]

    def get_latest_scan(self):
        return self.last_full_scan_points

# --- Pygame Display ---
class LidarDisplay:
    def __init__(self, width, height):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Youyeetoo LD19 LiDAR Simulation")
        self.font = pygame.font.Font(None, 24)
        self.clock = pygame.time.Clock()
        self.max_lidar_range_m = 12.0
        self.clicked_point_info = None

    def draw_grid(self):
        colors = [(30,30,30), (50,50,50), (70,70,70), (90,90,90)]
        for i in range(1, 5):
            radius_pixels = int((i * 3.0 / self.max_lidar_range_m) * LIDAR_DISPLAY_RADIUS)
            pygame.draw.circle(self.screen, colors[i-1], (CENTER_X, CENTER_Y), radius_pixels, 1)

        pygame.draw.line(self.screen, (100, 100, 100), (CENTER_X, 0), (CENTER_X, SCREEN_HEIGHT), 1)
        pygame.draw.line(self.screen, (100, 100, 100), (0, CENTER_Y), (SCREEN_WIDTH, CENTER_Y), 1)

        for i in range(1, 5):
            dist_m = i * 3.0
            radius_pixels = int((dist_m / self.max_lidar_range_m) * LIDAR_DISPLAY_RADIUS)
            text_surface = self.font.render(f"{int(dist_m)}m", True, (150, 150, 150))
            self.screen.blit(text_surface, (CENTER_X + radius_pixels - text_surface.get_width()//2, CENTER_Y + 5))
            self.screen.blit(text_surface, (CENTER_X - radius_pixels - text_surface.get_width()//2, CENTER_Y + 5))


    def draw_points(self, points):
        for point in points:
            if point.is_valid:
                point.calculate_cartesian()
                point.calculate_screen_coordinates(self.max_lidar_range_m)
                pygame.draw.circle(self.screen, LIDAR_POINT_COLOR, (point.screen_x, point.screen_y), POINT_SIZE)

        if self.clicked_point_info:
            pygame.draw.circle(self.screen, CLICKED_POINT_COLOR, (self.clicked_point_info.screen_x, self.clicked_point_info.screen_y), POINT_SIZE + 2, 1)

    def display_info_table(self):
        if not self.clicked_point_info:
            return

        info_lines = [
            "Clicked Point Information:",
            f"  Angle: {self.clicked_point_info.angle_deg:.2f}°",
            f"  Distance: {self.clicked_point_info.distance_mm} mm ({self.clicked_point_info.distance_mm/1000.0:.2f} m)",
            f"  Confidence: {self.clicked_point_info.confidence}",
            f"  X: {self.clicked_point_info.x:.2f} m",
            f"  Y: {self.clicked_point_info.y:.2f} m"
        ]

        max_width = 0
        total_height = 0
        for line in info_lines:
            text_surface = self.font.render(line, True, INFO_TEXT_COLOR)
            max_width = max(max_width, text_surface.get_width())
            total_height += text_surface.get_height()

        padding = 10
        table_rect = pygame.Rect(SCREEN_WIDTH - max_width - 2 * padding - 20, 20, max_width + 2 * padding, total_height + 2 * padding)

        s = pygame.Surface((table_rect.width, table_rect.height), pygame.SRCALPHA)
        s.fill(INFO_BACKGROUND_COLOR)
        self.screen.blit(s, (table_rect.x, table_rect.y))
        pygame.draw.rect(self.screen, (100, 100, 100), table_rect, 2)

        y_offset = table_rect.top + padding
        for line in info_lines:
            text_surface = self.font.render(line, True, INFO_TEXT_COLOR)
            self.screen.blit(text_surface, (table_rect.left + padding, y_offset))
            y_offset += text_surface.get_height()


    def run(self, lidar_parser):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_x, mouse_y = event.pos
                        closest_point = None
                        min_distance_sq = float('inf')

                        current_scan_for_click = lidar_parser.get_latest_scan()
                        for point in current_scan_for_click:
                            if point.is_valid:
                                point.calculate_cartesian()
                                point.calculate_screen_coordinates(self.max_lidar_range_m)
                                dist_sq = (point.screen_x - mouse_x)**2 + (point.screen_y - mouse_y)**2
                                if dist_sq < min_distance_sq:
                                    min_distance_sq = dist_sq
                                    closest_point = point

                        if closest_point and math.sqrt(min_distance_sq) < 10:
                            self.clicked_point_info = closest_point
                        else:
                            self.clicked_point_info = None

            self.screen.fill(BACKGROUND_COLOR)
            self.draw_grid()

            lidar_parser.read_data()
            latest_scan = lidar_parser.get_latest_scan()
            self.draw_points(latest_scan)
            self.display_info_table()

            pygame.display.flip()
            self.clock.tick(60)

        lidar_parser.disconnect()
        pygame.quit()
        sys.exit()

# --- Main Execution ---
if __name__ == "__main__":
    lidar_parser = LidarParser(SERIAL_PORT, BAUD_RATE)
    if not lidar_parser.connect():
        sys.exit(1)

    display = LidarDisplay(SCREEN_WIDTH, SCREEN_HEIGHT)
    display.run(lidar_parser)