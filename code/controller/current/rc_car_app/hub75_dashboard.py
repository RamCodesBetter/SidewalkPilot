#!/usr/bin/python3
import json
import socket
import subprocess
import time
from typing import Dict, List

try:
    import serial
except Exception:
    serial = None


class Hub75DashboardSender:
    def __init__(
        self,
        transport: str,
        baud_rate: int,
        send_interval_sec: float = 0.1,
        serial_port: str | None = None,
        udp_host: str | None = None,
        udp_port: int | None = None,
    ):
        self.transport = str(transport).strip().lower()
        self.baud_rate = baud_rate
        self.send_interval_sec = send_interval_sec
        self.serial_port = serial_port
        self.udp_host = udp_host
        self.udp_port = udp_port
        self.serial_handle = None
        self.socket_handle = None
        self.udp_targets = []
        self.active_udp_target_index = 0
        self.last_udp_target_probe_time = 0.0
        self.udp_target_probe_interval_sec = 2.0
        self.last_udp_target_log = ""
        self.last_send_time = 0.0
        self.last_payload_json = ""
        self.last_connect_attempt = 0.0
        self.connect_retry_sec = 2.0
        self.import_error_reported = False
        self.pending_notifications: List[Dict[str, object]] = []

    def _ensure_connected(self):
        if self.transport == "serial" and self.serial_handle is not None:
            return True
        if self.transport == "udp" and self.socket_handle is not None and self.udp_targets:
            return True

        now = time.monotonic()
        if now - self.last_connect_attempt < self.connect_retry_sec:
            return False
        self.last_connect_attempt = now

        if self.transport == "udp":
            if not self.udp_host or self.udp_port is None:
                if not self.import_error_reported:
                    print("Hub75 dashboard telemetry disabled: UDP host/port not configured.")
                    self.import_error_reported = True
                return False
            try:
                targets = []
                for host in [part.strip() for part in str(self.udp_host).split(",") if part.strip()]:
                    try:
                        addrinfo = socket.getaddrinfo(
                            host,
                            self.udp_port,
                            family=socket.AF_INET,
                            type=socket.SOCK_DGRAM,
                        )
                    except Exception as exc:
                        print(f"Hub75 dashboard telemetry UDP target unavailable {host}:{self.udp_port}: {exc}")
                        continue
                    targets.append((host, addrinfo[0][4]))
                if not targets:
                    self.socket_handle = None
                    self.udp_targets = []
                    return False
                self.socket_handle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp_targets = targets
                target_names = ", ".join(f"{host}:{self.udp_port}" for host, _ in targets)
                print(f"Hub75 dashboard telemetry sending UDP to {target_names}.")
                return True
            except Exception as exc:
                print(f"Hub75 dashboard telemetry UDP setup failed for {self.udp_host}:{self.udp_port}: {exc}")
                self.socket_handle = None
                self.udp_targets = []
                return False

        if self.transport != "serial":
            if not self.import_error_reported:
                print(f"Hub75 dashboard telemetry disabled: unsupported transport '{self.transport}'.")
                self.import_error_reported = True
            return False

        if serial is None:
            if not self.import_error_reported:
                print("Hub75 dashboard telemetry disabled: missing dependency 'pyserial'.")
                self.import_error_reported = True
            return False

        try:
            self.serial_handle = serial.Serial(self.serial_port, self.baud_rate, timeout=0, write_timeout=0)
            print(f"Hub75 dashboard telemetry connected on {self.serial_port} @ {self.baud_rate}.")
            return True
        except Exception as exc:
            print(f"Hub75 dashboard telemetry connect failed on {self.serial_port}: {exc}")
            self.serial_handle = None
            return False

    def _probe_udp_host(self, host: str) -> bool:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", host],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1.5,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _select_udp_target(self, now: float):
        if not self.udp_targets:
            return None
        if self.active_udp_target_index >= len(self.udp_targets):
            self.active_udp_target_index = 0

        if now - self.last_udp_target_probe_time >= self.udp_target_probe_interval_sec:
            self.last_udp_target_probe_time = now
            selected_index = None
            for index, (host, _) in enumerate(self.udp_targets):
                if self._probe_udp_host(host):
                    selected_index = index
                    break
            self.active_udp_target_index = selected_index if selected_index is not None else 0

        host, target = self.udp_targets[self.active_udp_target_index]
        if host != self.last_udp_target_log:
            print(f"Hub75 dashboard telemetry active UDP target: {host}:{self.udp_port}.")
            self.last_udp_target_log = host
        return target

    def send(
        self,
        speed_mph: float,
        gear: str,
        left_signal_visible: bool,
        right_signal_visible: bool,
        dashboard_alert: str,
        brightness_percent: int,
        dashboard_page: int = 1,
        dashboard_page_transition: str = "",
        servo_deg: float = 90.0,
        throttle_percent: int = 0,
        brake_percent: int = 0,
        drive_mode: str = "MAN",
        lidar_points: List[List[float]] | None = None,
        lidar_point_count: int = 0,
        model_choice: str = "",
        camera_confidence_percent: int = 0,
        cpu_temp_c: float = 0.0,
        camera_pixels: List[str] | None = None,
        photos_run: int = 0,
        photos_all: int = 0,
        photo_run_stats: Dict[str, int] | None = None,
        camera_fps: float = 0.0,
        system_status: str = "",
        nav_status: Dict[str, object] | None = None,
        steering_trim_delta_deg: float = 0.0,
        steering_trim_total_deg: float = 90.0,
        steering_center_offset: float = 0.0,
    ):
        now = time.monotonic()
        if now - self.last_send_time < self.send_interval_sec:
            return False
        if not self._ensure_connected():
            return False

        payload = {
            "speed_mph": round(max(0.0, float(speed_mph)), 2),
            "gear": str(gear),
            "left_signal_visible": bool(left_signal_visible),
            "right_signal_visible": bool(right_signal_visible),
            "dashboard_alert": str(dashboard_alert)[:4],
            "brightness_percent": max(0, min(100, int(brightness_percent))),
            "dashboard_page": max(1, min(14, int(dashboard_page))),
            "dashboard_page_transition": str(dashboard_page_transition)[:8],
            "servo_deg": round(max(0.0, min(180.0, float(servo_deg))), 1),
            "throttle_percent": max(0, min(100, int(throttle_percent))),
            "brake_percent": max(0, min(100, int(brake_percent))),
            "drive_mode": str(drive_mode)[:3],
            "lidar_points": lidar_points or [],
            "lidar_point_count": max(0, int(lidar_point_count)),
            "model_choice": str(model_choice)[:4],
            "camera_confidence_percent": max(0, min(100, int(camera_confidence_percent))),
            "cpu_temp_c": round(max(0.0, min(99.0, float(cpu_temp_c))), 1),
            "camera_pixels": camera_pixels or [],
            "photos_run": max(0, int(photos_run)),
            "photos_all": max(0, int(photos_all)),
            "photo_run_stats": photo_run_stats or {},
            "camera_fps": round(max(0.0, float(camera_fps)), 2),
            "system_status": str(system_status)[:4],
            "nav_status": nav_status or {},
            "steering_trim_delta_deg": round(max(-180.0, min(180.0, float(steering_trim_delta_deg))), 2),
            "steering_trim_total_deg": round(max(0.0, min(180.0, float(steering_trim_total_deg))), 2),
            "steering_center_offset": round(max(-1.0, min(1.0, float(steering_center_offset))), 4),
            "timestamp": time.time(),
        }
        notification_sent = False
        if self.pending_notifications:
            payload["dashboard_notification"] = self.pending_notifications[0]
        if self._write_payload(payload, now):
            notification_sent = "dashboard_notification" in payload
        if notification_sent:
            self.pending_notifications.pop(0)
        return True

    def send_shutdown(self):
        if not self._ensure_connected():
            return
        for _ in range(5):
            try:
                self._write_payload({"shutdown": True, "timestamp": time.time()}, time.monotonic())
                time.sleep(0.05)
            except Exception as exc:
                print(f"Hub75 dashboard telemetry shutdown write failed: {exc}")
                self.close()
                return

    def queue_notification(self, cells: List[str], duration_sec: float = 2.0):
        normalized_cells = [str(cell)[:2] for cell in cells[:8]]
        if len(normalized_cells) < 8:
            normalized_cells.extend([""] * (8 - len(normalized_cells)))
        self.pending_notifications.append(
            {
                "cells": normalized_cells,
                "duration_sec": max(0.1, float(duration_sec)),
            }
        )

    def _write_payload(self, payload, send_time_monotonic: float) -> bool:
        try:
            payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            encoded = (payload_json + "\n").encode("utf-8")
            if self.transport == "udp":
                if self.socket_handle is None or not self.udp_targets:
                    return False
                target = self._select_udp_target(send_time_monotonic)
                if target is None:
                    self.close()
                    return False
                self.socket_handle.sendto(encoded, target)
            else:
                if self.serial_handle is None:
                    return False
                self.serial_handle.write(encoded)
            self.last_send_time = send_time_monotonic
            self.last_payload_json = payload_json
            return True
        except Exception as exc:
            print(f"Hub75 dashboard telemetry write failed: {exc}")
            self.close()
            return False

    def close(self):
        if self.serial_handle is not None:
            try:
                self.serial_handle.close()
            except Exception:
                pass
            self.serial_handle = None
        if self.socket_handle is not None:
            try:
                self.socket_handle.close()
            except Exception:
                pass
            self.socket_handle = None
            self.udp_targets = []
            self.active_udp_target_index = 0
            self.last_udp_target_log = ""
