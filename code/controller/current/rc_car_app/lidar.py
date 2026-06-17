#!/usr/bin/python3
import math
import os
import struct
import threading
import time

import serial

DEFAULT_LIDAR_SERIAL_PORT = "/dev/ttyAMA3"
SERIAL_PORT = os.environ.get("RC_CAR_LIDAR_SERIAL_PORT", DEFAULT_LIDAR_SERIAL_PORT).strip() or DEFAULT_LIDAR_SERIAL_PORT
BAUD_RATE = 230400
PACKET_LENGTH = 47
MEASUREMENT_POINTS_PER_PACKET = 12
MAX_LIDAR_RANGE_M = 12.0
OBSTACLE_STOP_THRESHOLD_M = 0.6
OBSTACLE_WARN_THRESHOLD_M = 1.2
RECONNECT_INTERVAL_SEC = 1.5
RECONNECT_INTERVAL_MAX_SEC = 10.0
RECONNECT_LOG_INTERVAL_SEC = 15.0
READ_LOOP_SLEEP_SEC = 0.01
SCAN_STALE_SEC = 1.0


def resolve_lidar_serial_port(port):
    configured = str(port or "").strip()
    if not configured or configured.lower() == "auto":
        configured = DEFAULT_LIDAR_SERIAL_PORT
    if os.path.exists(configured) and os.access(configured, os.R_OK | os.W_OK):
        return configured
    return None


class LidarPoint:
    def __init__(self, angle_deg, distance_mm, confidence):
        self.angle_deg = angle_deg
        self.distance_mm = distance_mm
        self.confidence = confidence
        self.x = 0
        self.y = 0
        self.is_valid = True

    def calculate_cartesian(self):
        distance_m = self.distance_mm / 1000.0
        angle_rad = math.radians(self.angle_deg)
        self.x = distance_m * math.sin(angle_rad)
        self.y = distance_m * math.cos(angle_rad)


class LidarParser:
    def __init__(self, port, baudrate):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.buffer = b""
        self.current_scan_points = []
        self.last_full_scan_points = []
        self.lock = threading.Lock()
        self.last_reconnect_attempt = 0.0
        self.reconnect_interval = RECONNECT_INTERVAL_SEC
        self.last_connect_log_time = 0.0
        self.last_connect_log_message = ""
        self.last_scan_time = 0.0
        self.connected = False
        self.running = False
        self.thread = None

    def log_connect_status(self, message, force=False):
        now = time.monotonic()
        if force or message != self.last_connect_log_message or now - self.last_connect_log_time >= RECONNECT_LOG_INTERVAL_SEC:
            print(message)
            self.last_connect_log_message = message
            self.last_connect_log_time = now

    def connect(self):
        port = resolve_lidar_serial_port(self.port)
        if not port:
            self.connected = False
            self.ser = None
            self.reconnect_interval = min(RECONNECT_INTERVAL_MAX_SEC, self.reconnect_interval * 1.5)
            self.log_connect_status("LiDAR GPIO UART serial port not ready; waiting for /dev/ttyAMA3.")
            return False
        try:
            self.disconnect()
            self.ser = serial.Serial(port, self.baudrate, timeout=0)
            self.buffer = b""
            self.connected = True
            self.reconnect_interval = RECONNECT_INTERVAL_SEC
            self.last_connect_log_message = ""
            print(f"Connected to LiDAR on {port} at {self.baudrate} baud.")
            return True
        except (OSError, serial.SerialException) as e:
            self.connected = False
            self.ser = None
            self.reconnect_interval = min(RECONNECT_INTERVAL_MAX_SEC, self.reconnect_interval * 1.5)
            self.log_connect_status(f"Error opening serial port {port}: {e}")
            return False

    def disconnect(self):
        if self.ser:
            try:
                if self.ser.is_open:
                    self.ser.close()
                    print("Disconnected from LiDAR.")
            except (OSError, serial.SerialException) as e:
                print(f"LiDAR disconnect error ignored: {e}")
        self.ser = None
        self.connected = False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        self.disconnect()

    def _run(self):
        while self.running:
            try:
                self._read_data_once()
            except Exception as exc:
                print(f"LiDAR reader loop error ignored: {exc}")
                self.mark_fault(exc)
            time.sleep(READ_LOOP_SLEEP_SEC)

    def mark_fault(self, error) -> None:
        self.log_connect_status(f"LiDAR serial error: {error}. Ignoring LiDAR until reconnect succeeds.")
        self.disconnect()
        self.buffer = b""
        with self.lock:
            self.current_scan_points = []
            self.last_full_scan_points = []
            self.last_scan_time = 0.0
        self.last_reconnect_attempt = time.monotonic()
        self.reconnect_interval = max(self.reconnect_interval, RECONNECT_INTERVAL_SEC)

    def maybe_reconnect(self) -> None:
        now = time.monotonic()
        if now - self.last_reconnect_attempt < self.reconnect_interval:
            return
        self.last_reconnect_attempt = now
        self.connect()

    def read_data(self):
        if not self.running:
            self.start()

    def _read_data_once(self):
        if not self.ser or not self.ser.is_open:
            self.maybe_reconnect()
            return
        try:
            bytes_to_read = self.ser.in_waiting
            if bytes_to_read:
                self.buffer += self.ser.read(bytes_to_read)
        except (OSError, serial.SerialException) as e:
            self.mark_fault(e)
            return
        while len(self.buffer) >= PACKET_LENGTH:
            header_index = self.buffer.find(0x54)
            if header_index == -1:
                self.buffer = b""
                break
            if header_index > 0:
                self.buffer = self.buffer[header_index:]
                continue
            if len(self.buffer) < PACKET_LENGTH:
                break
            packet = self.buffer[:PACKET_LENGTH]
            if packet[1] != 0x2C:
                self.buffer = self.buffer[1:]
                continue
            try:
                _, start_angle_raw = struct.unpack("<H H", packet[2:6])
                start_angle = start_angle_raw / 100.0
                data_bytes = packet[6:42]
                end_angle_raw, _, _ = struct.unpack("<H H B", packet[42:47])
                end_angle = end_angle_raw / 100.0
                if end_angle < start_angle:
                    end_angle += 360.0

                points_in_packet = []
                for i in range(MEASUREMENT_POINTS_PER_PACKET):
                    offset = i * 3
                    distance_raw = struct.unpack("<H", data_bytes[offset:offset + 2])[0]
                    confidence = data_bytes[offset + 2]
                    angle_step = (end_angle - start_angle) / (MEASUREMENT_POINTS_PER_PACKET - 1)
                    point_angle = (start_angle + angle_step * i) % 360
                    point = LidarPoint(point_angle, distance_raw, confidence)
                    point.is_valid = distance_raw != 0
                    points_in_packet.append(point)

                with self.lock:
                    self.current_scan_points.extend(points_in_packet)
                    if len(self.current_scan_points) > 500:
                        self.last_full_scan_points = self.current_scan_points
                        self.last_scan_time = time.monotonic()
                        self.current_scan_points = []
            except struct.error as e:
                print(f"Struct unpacking error: {e}. Packet: {packet.hex()}")
            except Exception as e:
                print(f"Error parsing packet: {e}. Packet: {packet.hex()}")
            self.buffer = self.buffer[PACKET_LENGTH:]

    def get_latest_scan(self):
        with self.lock:
            if time.monotonic() - self.last_scan_time > SCAN_STALE_SEC:
                return []
            return list(self.last_full_scan_points)


def determine_turn_direction(
    lidar_scan,
    front_clear_threshold_m=1.5,
    side_clear_threshold_m=1.0,
    reverse_clear_threshold_m=0.5,
    critical_front_stop_threshold_m=0.4,
    obstacle_stop_threshold_m=OBSTACLE_STOP_THRESHOLD_M,
    obstacle_warn_threshold_m=OBSTACLE_WARN_THRESHOLD_M,
):
    if not lidar_scan:
        return " ", MAX_LIDAR_RANGE_M, MAX_LIDAR_RANGE_M, MAX_LIDAR_RANGE_M, MAX_LIDAR_RANGE_M

    front_points = []
    left_points = []
    right_points = []
    back_points = []

    for point in lidar_scan:
        if not point.is_valid or point.distance_mm == 0 or point.confidence < 150:
            continue
        distance_m = point.distance_mm / 1000.0
        angle = point.angle_deg
        if angle > 180:
            angle -= 360
        if -30 <= angle <= 30:
            front_points.append(distance_m)
        elif 30 < angle <= 90:
            right_points.append(distance_m)
        elif -90 <= angle < -30:
            left_points.append(distance_m)
        elif (90 < angle <= 180) or (-180 <= angle < -90):
            back_points.append(distance_m)

    min_front_dist = min(front_points) if front_points else MAX_LIDAR_RANGE_M
    min_left_dist = min(left_points) if left_points else MAX_LIDAR_RANGE_M
    min_right_dist = min(right_points) if right_points else MAX_LIDAR_RANGE_M
    min_back_dist = min(back_points) if back_points else MAX_LIDAR_RANGE_M

    if min_front_dist < obstacle_stop_threshold_m:
        return "STOP_WARNING", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if min_front_dist < obstacle_warn_threshold_m:
        return "WARN_WARNING", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if min_front_dist < critical_front_stop_threshold_m:
        if min_back_dist > reverse_clear_threshold_m:
            return "v", min_front_dist, min_left_dist, min_right_dist, min_back_dist
        return "BLOCKED", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if min_front_dist > front_clear_threshold_m:
        return "^", min_front_dist, min_left_dist, min_right_dist, min_back_dist

    left_is_clear = min_left_dist > side_clear_threshold_m
    right_is_clear = min_right_dist > side_clear_threshold_m

    if left_is_clear and right_is_clear:
        return ("<" if min_left_dist > min_right_dist else ">"), min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if left_is_clear:
        return "<", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if right_is_clear:
        return ">", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    if min_back_dist > reverse_clear_threshold_m:
        return "v", min_front_dist, min_left_dist, min_right_dist, min_back_dist
    return "BLOCKED", min_front_dist, min_left_dist, min_right_dist, min_back_dist


def score_heading_windows(
    lidar_scan,
    angle_min_deg=-75,
    angle_max_deg=75,
    step_deg=5,
    window_deg=12,
):
    """Evaluate openness for many headings across the forward field of view."""
    candidates = []
    if not lidar_scan:
        return candidates

    filtered = []
    for point in lidar_scan:
        if not point.is_valid or point.distance_mm == 0 or point.confidence < 150:
            continue
        angle = point.angle_deg
        if angle > 180:
            angle -= 360
        filtered.append((angle, point.distance_mm / 1000.0))

    for heading_deg in range(int(angle_min_deg), int(angle_max_deg) + 1, int(step_deg)):
        sector = [dist for angle, dist in filtered if abs(angle - heading_deg) <= window_deg]
        if not sector:
            min_dist = MAX_LIDAR_RANGE_M
            avg_dist = MAX_LIDAR_RANGE_M
        else:
            min_dist = min(sector)
            avg_dist = sum(sector) / len(sector)
        score = (min_dist * 0.75) + (avg_dist * 0.25)
        candidates.append(
            {
                "heading_deg": float(heading_deg),
                "min_dist_m": float(min_dist),
                "avg_dist_m": float(avg_dist),
                "score": float(score),
            }
        )
    return candidates
