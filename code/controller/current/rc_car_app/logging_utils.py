#!/usr/bin/python3
import csv
import datetime


def init_csv_logger(csv_filename, csv_headers):
    try:
        csv_file = open(csv_filename, "a", newline="")
        csv_writer = csv.writer(csv_file)
        if csv_file.tell() == 0:
            csv_writer.writerow(csv_headers)
        print(f"CSV logging initialized: {csv_filename}")
        return csv_file, csv_writer
    except Exception as e:
        print(f"Error initializing CSV logger: {e}")
        return None, None


def log_data_to_csv(csv_file, csv_writer, state, metrics, cpu_percent, memory_percent, cpu_temp):
    if not csv_writer:
        return
    current_time = datetime.datetime.now()
    time_since_start = current_time.timestamp() - metrics.start_time
    average_speed_mph = 0.0
    if time_since_start > 0:
        total_distance_miles = metrics.total_distance_cm * 0.00000621371
        average_speed_mph = total_distance_miles / (time_since_start / 3600.0)
    time_since_last_pulse = current_time.timestamp() - metrics.last_pulse_time

    row = [
        current_time.strftime("%Y-%m-%d %H:%M:%S"),
        f"{time_since_start:.2f}",
        int(state["autonomous_mode"]),
        int(state["cc_active"]),
        int(state["event_shift_up"]),
        int(state["event_shift_down"]),
        int(state["event_quit_pressed"]),
        int(state["event_cc_increase"]),
        int(state["event_cc_decrease"]),
        f"{state['steer']:.2f}",
        int(state["brake"]),
        f"{state['throttle']:.2f}",
        f"{metrics.max_speed_recall:.2f}",
        f"{average_speed_mph:.2f}",
        f"{metrics.smoothed_speed_mph:.2f}",
        f"{state['current_motor_pwm']:.2f}",
        state["gear_mode"],
        f"{state['cc_target_speed']:.2f}",
        f"{state['lidar_front_dist']:.2f}",
        f"{state['lidar_left_dist']:.2f}",
        f"{state['lidar_right_dist']:.2f}",
        f"{state['lidar_back_dist']:.2f}",
        state["direction_arrow"],
        f"{state['target_heading_deg']:.2f}",
        state["stop_reason"],
        f"{cpu_percent:.2f}",
        f"{memory_percent:.2f}",
        state["num_lidar_points"],
        f"{time_since_last_pulse:.2f}",
        f"{cpu_temp:.1f}",
        int(metrics.aeb_enabled),
        int(metrics.aeb_triggered),
        f"{metrics.pid_output:.2f}",
        f"{state['lidar_best_heading_deg']:.2f}",
        f"{state['lidar_heading_confidence']:.2f}",
        f"{state['lidar_forward_clearance_m']:.2f}",
        f"{state['camera_steering_bias']:.2f}",
        f"{state['camera_confidence']:.2f}",
        int(state["camera_left_edge_found"]),
        int(state["camera_right_edge_found"]),
        f"{state['camera_corridor_width_px']:.2f}",
        int(state["driveway_cut_suspected"]),
        f"{state['steering_servo_deg']:.2f}",
        int(state.get("event_intervention", False)),
        state.get("intervention_cause", ""),
        state.get("dashboard_payload_json", ""),
    ]
    try:
        csv_writer.writerow(row)
        csv_file.flush()
    except Exception as e:
        print(f"Error writing to CSV: {e}")

    state["event_shift_up"] = False
    state["event_shift_down"] = False
    state["event_cc_increase"] = False
    state["event_cc_decrease"] = False
    state["event_intervention"] = False
    state["intervention_cause"] = ""
