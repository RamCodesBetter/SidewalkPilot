#!/usr/bin/python3
import os
import queue
import threading
import time

from .config import (
    CONTROL_LOOP_HZ,
    ENABLE_WEBCAM_VISION,
    PI_CAMERA_NUM,
    PI_CAMERA_ROTATE_180,
    USE_PI_CAMERA,
)

STEERING_MODEL_VERSIONS = (
    "1.0",
    "1.0b",
    "1.1",
    "1.1b",
    "1.2",
    "1.2b",
    "1.3",
    "1.3b",
    "1.4",
    "1.4b",
    "1.5",
    "1.5b",
    "1.6",
    "1.6b",
    "1.7",
    "1.7b",
    "1.8",
    "1.8b",
    "1.9",
    "1.9b",
    "2.0",
    "2.0b",
    "2.1",
    "2.1b",
    "2.2",
    "2.2b",
    "2.3",
    "2.3b",
    "2.4",
    "2.4b",
    # Series 3/4 hybrid models. Every listed family runs on the Jetson Orin Nano;
    # the Raspberry Pi stores only the selected version and sends it with frames.
    # 3.0/3.0b = 2-output regression; 3.1+ = 19-output hybrid (9 class logits +
    # 9 within-bucket offsets + 1 throttle), decoded on Jon by output length.
    "3.0",
    "3.0b",
    "3.1",
    "3.1b",
    "3.2",
    "3.2b",
    "3.3",
    "3.3b",
    "3.4",
    "3.4b",
    # Series 4 experimental temporal contracts, all steering-only hybrid models:
    #   p/r = PC  (image + previous 3 targets -> current target)
    #   f/g = CF  (image -> current + next 3 targets)
    #   a/c = PCF (image + previous 3 targets -> current + next 3 targets)
    # Final checkpoints are p/f/a; best-validation checkpoints are r/g/c.
    "4.0p",
    "4.0r",
    "4.0f",
    "4.0g",
    "4.0a",
    "4.0c",
    "4.1p",
    "4.1r",
    "4.1f",
    "4.1g",
    "4.1a",
    "4.1c",
)
STEERING_MODEL_CHOICES = {version: version for version in STEERING_MODEL_VERSIONS}
# v3.4 won the 2026-07-13 shadow/turn field comparison. Keep newer and b checkpoints
# selectable, but do not infer the live research default from list order.
DEFAULT_STEERING_MODEL_CHOICE = os.environ.get("RC_CAR_STEERING_MODEL", "3.4")
YOLO_IMGSZ = 640
YOLO_CONF = 0.20
CAMERA_FRAME_WIDTH = 1280
CAMERA_FRAME_HEIGHT = 720
CAMERA_FPS = CONTROL_LOOP_HZ
# Camera Module 3's 2304x1296 mode preserves the full IMX708 field of view and
# supports up to 56 FPS. Pin it so requesting 50 FPS cannot select the cropped
# 1536x864/120 FPS sensor mode and change the view learned by the models.
CAMERA_SENSOR_WIDTH = 2304
CAMERA_SENSOR_HEIGHT = 1296
CAMERA_SENSOR_BIT_DEPTH = 10

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

try:
    from picamera2 import Picamera2
    from libcamera import Transform
except ImportError:
    Picamera2 = None
    Transform = None

class _PiCameraCapture:
    def __init__(self, camera_num):
        self.camera_num = camera_num
        self.camera = None
        self.started = False

    def open(self):
        if Picamera2 is None:
            return False
        self.camera = Picamera2(camera_num=self.camera_num)
        config_kwargs = {
            # Keep the frame in OpenCV-style BGR order for the rest of the
            # pipeline and avoid any extra channel swaps.
            "main": {"size": (CAMERA_FRAME_WIDTH, CAMERA_FRAME_HEIGHT), "format": "BGR888"},
            "sensor": {
                "output_size": (CAMERA_SENSOR_WIDTH, CAMERA_SENSOR_HEIGHT),
                "bit_depth": CAMERA_SENSOR_BIT_DEPTH,
            },
            "controls": {"FrameRate": float(CAMERA_FPS)},
        }
        if Transform is not None:
            config_kwargs["transform"] = Transform(hflip=PI_CAMERA_ROTATE_180, vflip=PI_CAMERA_ROTATE_180)
        config = self.camera.create_video_configuration(**config_kwargs)
        self.camera.configure(config)
        self.camera.start()
        self.started = True
        return True

    def isOpened(self):
        return self.started

    def read(self):
        if not self.started or self.camera is None:
            return False, None
        frame = self.camera.capture_array()
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        camera = self.camera
        self.camera = None
        self.started = False
        if camera is not None:
            def close_camera():
                try:
                    camera.stop()
                except Exception:
                    pass
                try:
                    camera.close()
                except Exception:
                    pass

            close_thread = threading.Thread(
                target=close_camera,
                name="sidewalkpilot-camera-close",
                daemon=True,
            )
            close_thread.start()
            close_thread.join(timeout=3.0)
            if close_thread.is_alive():
                print("Pi camera close exceeded 3 seconds; continuing shutdown.")


def _empty_analysis():
    return {
        "heading_bias": 0.0,
        "confidence": 0.0,
        "left_edge_found": False,
        "right_edge_found": False,
        "corridor_width_px": 0.0,
        "driveway_cut_hint": False,
        "roi_top": 0,
        "roi_height": 0,
        "left_edge_x": None,
        "right_edge_x": None,
        "corridor_center_x": None,
        "image_width": 0,
        "image_height": 0,
        "mask_confidence": 0.0,
        "edge_confidence": 0.0,
        "steering_angle_deg": 90.0,
        "method": "none",
    }


def _mask_to_analysis(frame_shape, component_mask, method_name, base_confidence):
    analysis = _empty_analysis()
    height, width = frame_shape[:2]
    roi_top = int(height * 0.50)
    roi_bottom_exclusive = int(height * 0.92)
    roi_height = max(1, roi_bottom_exclusive - roi_top)
    roi_width = width

    analysis["roi_top"] = roi_top
    analysis["roi_height"] = roi_height
    analysis["image_width"] = width
    analysis["image_height"] = height

    mask_edges = _fit_edges_from_mask(component_mask)
    if mask_edges is None:
        return analysis

    width_ratio = mask_edges["corridor_width_px"] / max(1.0, roi_width)
    stability_penalty = min(
        0.42,
        (
            mask_edges["width_stability"]
            + mask_edges["left_spread"]
            + mask_edges["right_spread"]
            + mask_edges["center_stability"]
        )
        / 180.0,
    )
    width_bonus = 0.25 if 0.24 <= width_ratio <= 0.9 else max(0.0, 0.08 - abs(width_ratio - 0.45))
    perspective_bonus = 0.18 if 0.35 <= mask_edges["width_ratio_top_to_bottom"] <= 0.95 else 0.0
    mask_confidence = max(
        0.0,
        min(0.95, base_confidence + width_bonus + perspective_bonus - stability_penalty),
    )

    corridor_center_x = float(mask_edges["corridor_center_x"])
    normalized_error = (corridor_center_x - (roi_width / 2.0)) / max(1.0, roi_width / 2.0)

    analysis.update(
        {
            "heading_bias": max(-1.0, min(1.0, normalized_error)),
            "confidence": mask_confidence,
            "left_edge_found": True,
            "right_edge_found": True,
            "corridor_width_px": float(mask_edges["corridor_width_px"]),
            "left_edge_x": int(round(mask_edges["left_edge_x"])),
            "right_edge_x": int(round(mask_edges["right_edge_x"])),
            "corridor_center_x": corridor_center_x,
            "mask_confidence": mask_confidence,
            "edge_confidence": 0.0,
            "method": method_name,
        }
    )
    return analysis


def _extract_yolo_component(frame, model):
    if model is None or cv2 is None or np is None:
        return None

    height, width = frame.shape[:2]
    roi_top = int(height * 0.50)
    roi_bottom_exclusive = int(height * 0.92)
    roi = frame[roi_top:roi_bottom_exclusive, :]
    if roi.size == 0:
        return None

    result = model.predict(
        source=roi,
        imgsz=YOLO_IMGSZ,
        conf=YOLO_CONF,
        verbose=False,
        retina_masks=False,
        device="cpu",
    )[0]
    masks = getattr(result, "masks", None)
    if masks is None or getattr(masks, "data", None) is None or len(masks.data) == 0:
        return None

    best_mask = None
    best_score = -1.0
    roi_height, roi_width = roi.shape[:2]

    confs = None
    if getattr(result, "boxes", None) is not None and getattr(result.boxes, "conf", None) is not None:
        confs = result.boxes.conf.detach().cpu().numpy()

    for idx, mask_tensor in enumerate(masks.data):
        mask = mask_tensor.detach().cpu().numpy()
        mask = (mask > 0.5).astype(np.uint8) * 255
        if mask.shape[:2] != (roi_height, roi_width):
            mask = cv2.resize(mask, (roi_width, roi_height), interpolation=cv2.INTER_NEAREST)

        component_mask, component_score = _find_sidewalk_component(mask, roi_width, roi_height)
        if component_mask is None:
            component_mask, component_score = _extract_seeded_component(mask, roi_width, roi_height)
        if component_mask is None:
            continue

        detection_conf = float(confs[idx]) if confs is not None and idx < len(confs) else 0.0
        total_score = component_score + detection_conf
        if total_score > best_score:
            best_score = total_score
            best_mask = component_mask

    return best_mask


def _find_sidewalk_component(mask, roi_width, roi_height):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return None, 0.0

    bottom_band_top = int(roi_height * 0.75)
    bottom_center_x = roi_width // 2
    best_label = None
    best_score = -1.0

    for label in range(1, num_labels):
        x = stats[label, cv2.CC_STAT_LEFT]
        y = stats[label, cv2.CC_STAT_TOP]
        w = stats[label, cv2.CC_STAT_WIDTH]
        h = stats[label, cv2.CC_STAT_HEIGHT]
        area = float(stats[label, cv2.CC_STAT_AREA])
        if area < roi_width * roi_height * 0.015:
            continue

        x2 = x + w
        y2 = y + h
        touches_bottom = y2 >= bottom_band_top
        contains_center = labels[min(roi_height - 1, roi_height - 5), bottom_center_x] == label
        center_dist = abs((x + x2) / 2.0 - bottom_center_x) / max(1.0, roi_width / 2.0)

        score = area / max(1.0, roi_width * roi_height)
        if touches_bottom:
            score += 0.8
        if contains_center:
            score += 1.2
        score += max(0.0, 0.4 - center_dist)

        if score > best_score:
            best_score = score
            best_label = label

    if best_label is None:
        return None, 0.0
    return (labels == best_label).astype(np.uint8) * 255, best_score


def _extract_seeded_component(mask, roi_width, roi_height):
    seed_y = min(roi_height - 4, int(roi_height * 0.92))
    seed_xs = np.linspace(int(roi_width * 0.35), int(roi_width * 0.65), 9).astype(int)

    seeded = np.zeros_like(mask)
    found = False
    flood_mask = np.zeros((roi_height + 2, roi_width + 2), dtype=np.uint8)

    for seed_x in seed_xs:
        if mask[seed_y, seed_x] == 0:
            continue
        candidate = mask.copy()
        flood_mask.fill(0)
        _, candidate, _, _ = cv2.floodFill(candidate, flood_mask, (int(seed_x), int(seed_y)), 128)
        component = np.where(candidate == 128, 255, 0).astype(np.uint8)
        if cv2.countNonZero(component) < roi_width * roi_height * 0.01:
            continue
        seeded = cv2.bitwise_or(seeded, component)
        found = True

    if not found:
        return None, 0.0

    component_area = cv2.countNonZero(seeded) / max(1.0, roi_width * roi_height)
    return seeded, component_area


def _fit_edges_from_mask(component_mask):
    roi_height, roi_width = component_mask.shape[:2]
    sample_rows = np.linspace(int(roi_height * 0.2), roi_height - 3, 14).astype(int)
    left_points = []
    right_points = []
    width_rows = []

    for y in sample_rows:
        xs = np.where(component_mask[y] > 0)[0]
        if xs.size < max(8, int(roi_width * 0.06)):
            continue
        left_points.append((float(xs[0]), float(y)))
        right_points.append((float(xs[-1]), float(y)))
        width_rows.append((float(xs[-1] - xs[0]), float(y)))

    if len(left_points) < 4 or len(right_points) < 4:
        return None

    left_x = [p[0] for p in left_points]
    right_x = [p[0] for p in right_points]
    row_y = np.array([p[1] for p in left_points], dtype=np.float32)
    width_samples = np.array([p[0] for p in right_points]) - np.array([p[0] for p in left_points])

    left_edge_x = float(np.median(left_x))
    right_edge_x = float(np.median(right_x))
    corridor_center_x = (left_edge_x + right_edge_x) / 2.0
    corridor_width_px = right_edge_x - left_edge_x

    if corridor_width_px < roi_width * 0.18:
        return None

    left_spread = float(np.std(left_x))
    right_spread = float(np.std(right_x))
    width_stability = float(np.std(width_samples))
    bottom_width = float(np.median(width_samples[row_y >= np.percentile(row_y, 65)]))
    top_width = float(np.median(width_samples[row_y <= np.percentile(row_y, 35)]))
    width_ratio_top_to_bottom = top_width / max(1.0, bottom_width)

    center_samples = (np.array(left_x) + np.array(right_x)) / 2.0
    center_stability = float(np.std(center_samples))

    # Sidewalks under perspective generally get narrower with distance,
    # but should not collapse into a tiny slit.
    if width_ratio_top_to_bottom < 0.18 or width_ratio_top_to_bottom > 1.1:
        return None
    if center_stability > roi_width * 0.18:
        return None

    return {
        "left_edge_x": left_edge_x,
        "right_edge_x": right_edge_x,
        "corridor_center_x": corridor_center_x,
        "corridor_width_px": corridor_width_px,
        "left_spread": left_spread,
        "right_spread": right_spread,
        "width_stability": width_stability,
        "center_stability": center_stability,
        "top_width": top_width,
        "bottom_width": bottom_width,
        "width_ratio_top_to_bottom": width_ratio_top_to_bottom,
        "sample_count": len(left_points),
    }


def _edge_fallback(normalized):
    roi_height, roi_width = normalized.shape[:2]
    blurred = cv2.GaussianBlur(normalized, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    column_energy = edges.sum(axis=0).astype(np.float32)
    total_energy = float(column_energy.sum())
    if total_energy < 1000.0:
        return None

    left_band = column_energy[: int(roi_width * 0.48)]
    right_band = column_energy[int(roi_width * 0.52) :]
    if left_band.size == 0 or right_band.size == 0:
        return None

    left_idx = int(np.argmax(left_band))
    right_idx = int(np.argmax(right_band) + int(roi_width * 0.52))
    left_peak = float(left_band[left_idx])
    right_peak = float(right_band[right_idx - int(roi_width * 0.52)])
    edge_threshold = max(800.0, total_energy * 0.025 / max(1, roi_width))
    left_found = left_peak >= edge_threshold
    right_found = right_peak >= edge_threshold
    if not (left_found and right_found) or right_idx <= left_idx:
        return None

    corridor_width_px = float(right_idx - left_idx)
    if corridor_width_px < roi_width * 0.18:
        return None
    corridor_center_x = (left_idx + right_idx) / 2.0
    confidence = min(0.55, total_energy / max(1.0, edges.shape[0] * 255.0 * roi_width * 0.12))
    return {
        "left_edge_x": float(left_idx),
        "right_edge_x": float(right_idx),
        "corridor_center_x": float(corridor_center_x),
        "corridor_width_px": corridor_width_px,
        "confidence": confidence,
    }


def estimate_path_bias_from_frame(frame):
    if cv2 is None or np is None:
        return _empty_analysis()

    height, width = frame.shape[:2]
    roi_top = int(height * 0.42)
    roi_bottom_exclusive = int(height * 0.92)
    roi = frame[roi_top:roi_bottom_exclusive, :]
    roi_height, roi_width = roi.shape[:2]

    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    normalized = cv2.GaussianBlur(gray, (5, 5), 0)

    a = lab[:, :, 1].astype(np.float32) - 128.0
    b = lab[:, :, 2].astype(np.float32) - 128.0
    chroma = np.sqrt((a * a) + (b * b))
    bgr_spread = (
        roi.astype(np.float32).max(axis=2)
        - roi.astype(np.float32).min(axis=2)
    )

    neutral_mask = (chroma < 18.0).astype(np.uint8) * 255
    low_color_spread_mask = (bgr_spread < 55.0).astype(np.uint8) * 255
    lit_mask = (gray > 45).astype(np.uint8) * 255
    candidate_mask = cv2.bitwise_and(cv2.bitwise_and(neutral_mask, low_color_spread_mask), lit_mask)

    kernel = np.ones((5, 5), np.uint8)
    candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, kernel)
    candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    seeded_mask, seeded_score = _extract_seeded_component(candidate_mask, roi_width, roi_height)
    component_mask, component_score = _find_sidewalk_component(candidate_mask, roi_width, roi_height)

    if seeded_mask is not None:
        if component_mask is None:
            component_mask = seeded_mask
            component_score = seeded_score
        else:
            overlap = cv2.countNonZero(cv2.bitwise_and(seeded_mask, component_mask))
            if overlap > 0:
                component_mask = cv2.bitwise_or(seeded_mask, component_mask)
                component_score = max(component_score, seeded_score)
            elif seeded_score >= component_score * 0.8:
                component_mask = seeded_mask
                component_score = seeded_score

    analysis = _empty_analysis()
    analysis["roi_top"] = roi_top
    analysis["roi_height"] = roi_height
    analysis["image_width"] = width
    analysis["image_height"] = height

    mask_edges = None
    mask_confidence = 0.0
    if component_mask is not None:
        mask_edges = _fit_edges_from_mask(component_mask)
        if mask_edges is not None:
            width_ratio = mask_edges["corridor_width_px"] / max(1.0, roi_width)
            stability_penalty = min(
                0.42,
                (
                    mask_edges["width_stability"]
                    + mask_edges["left_spread"]
                    + mask_edges["right_spread"]
                    + mask_edges["center_stability"]
                )
                / 180.0,
            )
            coverage_bonus = min(0.25, component_score / 2.5)
            width_bonus = 0.25 if 0.24 <= width_ratio <= 0.9 else max(0.0, 0.08 - abs(width_ratio - 0.45))
            perspective_bonus = 0.18 if 0.35 <= mask_edges["width_ratio_top_to_bottom"] <= 0.95 else 0.0
            mask_confidence = max(
                0.0,
                min(0.92, 0.28 + coverage_bonus + width_bonus + perspective_bonus - stability_penalty),
            )

    fallback_edges = _edge_fallback(normalized)
    edge_confidence = fallback_edges["confidence"] if fallback_edges is not None else 0.0

    if mask_edges is not None and mask_confidence >= max(0.32, edge_confidence + 0.08):
        chosen = mask_edges
        method = "mask"
        confidence = mask_confidence
    elif fallback_edges is not None and edge_confidence >= 0.48:
        chosen = fallback_edges
        method = "edge_fallback"
        confidence = edge_confidence
    else:
        analysis["driveway_cut_hint"] = bool(float(np.std(normalized)) < 18.0)
        return analysis

    corridor_center_x = float(chosen["corridor_center_x"])
    left_edge_x = int(round(chosen["left_edge_x"]))
    right_edge_x = int(round(chosen["right_edge_x"]))
    corridor_width_px = float(chosen["corridor_width_px"])
    normalized_error = (corridor_center_x - (roi_width / 2.0)) / max(1.0, roi_width / 2.0)

    analysis.update(
        {
            "heading_bias": max(-1.0, min(1.0, normalized_error)),
            "confidence": confidence,
            "left_edge_found": True,
            "right_edge_found": True,
            "corridor_width_px": corridor_width_px,
            "driveway_cut_hint": bool(confidence < 0.25 and float(np.std(normalized)) < 18.0),
            "left_edge_x": left_edge_x,
            "right_edge_x": right_edge_x,
            "corridor_center_x": corridor_center_x,
            "mask_confidence": mask_confidence,
            "edge_confidence": edge_confidence,
            "method": method,
        }
    )
    return analysis


def annotate_sidewalk_edges(frame, analysis):
    if cv2 is None:
        return frame

    annotated = frame.copy()
    height, width = annotated.shape[:2]
    roi_top = int(analysis.get("roi_top", int(height * 0.55)))
    roi_bottom = height - 1

    cv2.rectangle(annotated, (0, roi_top), (width - 1, roi_bottom), (80, 80, 80), 2)
    cv2.putText(
        annotated,
        "ROI",
        (10, max(25, roi_top - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (80, 80, 80),
        2,
        cv2.LINE_AA,
    )

    left_edge_x = analysis.get("left_edge_x")
    right_edge_x = analysis.get("right_edge_x")
    corridor_center_x = analysis.get("corridor_center_x")

    if left_edge_x is not None:
        cv2.rectangle(annotated, (left_edge_x - 8, roi_top), (left_edge_x + 8, roi_bottom), (0, 255, 0), 2)
        cv2.putText(
            annotated,
            "Left sidewalk edge",
            (max(10, left_edge_x - 110), max(30, roi_top + 25)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    if right_edge_x is not None:
        cv2.rectangle(annotated, (right_edge_x - 8, roi_top), (right_edge_x + 8, roi_bottom), (0, 200, 255), 2)
        cv2.putText(
            annotated,
            "Right sidewalk edge",
            (max(10, right_edge_x - 120), max(55, roi_top + 50)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 200, 255),
            2,
            cv2.LINE_AA,
        )

    if corridor_center_x is not None:
        center_x = int(corridor_center_x)
        cv2.line(annotated, (center_x, roi_top), (center_x, roi_bottom), (255, 255, 0), 2)
        cv2.putText(
            annotated,
            "Estimated sidewalk center",
            (max(10, center_x - 120), roi_bottom - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 0),
            2,
            cv2.LINE_AA,
        )

    overlay_lines = [
        f"Heading bias: {analysis.get('heading_bias', 0.0):.3f}",
        f"Confidence: {analysis.get('confidence', 0.0):.3f}",
        f"Corridor width px: {analysis.get('corridor_width_px', 0.0):.1f}",
        f"Driveway cut hint: {analysis.get('driveway_cut_hint', False)}",
        f"Method: {analysis.get('method', 'none')}",
    ]
    y = 25
    for line in overlay_lines:
        cv2.putText(annotated, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(annotated, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
        y += 28

    return annotated


class WebcamVisionProcessor:
    """Capture Pi camera frames for Jetson inference, previews, and data collection."""

    def __init__(self, model_choice=None):
        self.capture = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.last_frame_time = 0.0
        self.camera_fps = 0.0
        self._fps_last_frame_time = 0.0
        self.analysis = _empty_analysis()
        self.latest_frame = None
        self.latest_frame_captured_at = 0.0
        self.frame_sequence = 0
        self.model_choice = model_choice or DEFAULT_STEERING_MODEL_CHOICE
        # async JPEG writer: keep the slow cv2.imwrite OFF the control loop so
        # high-rate run capture doesn't stutter steering or the dashboard.
        # Bound queued raw 1280x720 frames to roughly three seconds of capture.
        # A 240-frame queue could retain hundreds of MB and pressure the control loop.
        self._save_q: "queue.Queue" = queue.Queue(maxsize=30)
        self._save_thread = None
        self.frames_dropped = 0
        self._capture_error_next_log = 0.0

    def _open_capture(self):
        if USE_PI_CAMERA and Picamera2 is not None:
            pi_capture = _PiCameraCapture(PI_CAMERA_NUM)
            if pi_capture.open():
                print(
                    f"Using Pi Camera {PI_CAMERA_NUM} at "
                    f"{CAMERA_FRAME_WIDTH}x{CAMERA_FRAME_HEIGHT}, target {CAMERA_FPS} FPS."
                )
                return pi_capture
            raise RuntimeError(f"Failed to start Pi Camera {PI_CAMERA_NUM}")
        raise RuntimeError("Pi Camera support is required but Picamera2 is unavailable")

    def start(self):
        if not ENABLE_WEBCAM_VISION or cv2 is None or np is None:
            print("Camera vision disabled or OpenCV unavailable.")
            return False

        print("Pi camera capture active; steering inference runs on the Jetson Orin Nano.")

        try:
            self.capture = self._open_capture()
        except Exception as e:
            print(f"Failed to open Pi Camera for vision processing: {e}")
            self.capture = None
            return False

        if not self.capture.isOpened():
            print(f"Failed to open Pi Camera for vision processing: camera={PI_CAMERA_NUM}")
            self.capture.release()
            self.capture = None
            return False
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self._save_thread.start()
        print("Pi camera vision processor started.")
        return True

    def queue_frame_save(self, output_path) -> bool:
        """Snapshot the current frame (fast copy) and hand the slow JPEG write to
        the background writer. Returns False if no frame yet or the queue is full."""
        if cv2 is None:
            return False
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return False
        try:
            self._save_q.put_nowait((str(output_path), frame))
            return True
        except queue.Full:
            self.frames_dropped += 1
            return False

    def _save_worker(self):
        while self.running or not self._save_q.empty():
            try:
                path, frame = self._save_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if not cv2.imwrite(path, frame):
                    print(f"Async frame write failed for {path}: OpenCV returned false")
            except Exception as exc:
                print(f"Async frame write failed for {path}: {exc}")

    def set_model_choice(self, model_choice: str) -> bool:
        requested_choice = str(model_choice).strip()
        if requested_choice not in STEERING_MODEL_CHOICES:
            print(f"Cannot select unknown steering model: {requested_choice}")
            return False
        if requested_choice == self.model_choice:
            return True
        with self.lock:
            self.model_choice = requested_choice
            self.analysis = _empty_analysis()
            self.analysis["method"] = "camera_capture"
        print(
            f"Model choice -> {requested_choice} "
            "(inference runs on the Jetson Orin Nano)."
        )
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self._save_thread:
            self._save_thread.join(timeout=3.0)   # let queued frames flush to disk
        if self.capture:
            self.capture.release()
            self.capture = None

    def grab_latest_frame(self):
        """Fast copy of the most recent BGR frame (for sending to the Jetson)."""
        if cv2 is None:
            return None
        with self.lock:
            return None if self.latest_frame is None else self.latest_frame.copy()

    def grab_latest_frame_sample(self, after_sequence=0):
        """Return each captured frame and its timestamp at most once."""
        with self.lock:
            if self.latest_frame is None or self.frame_sequence <= int(after_sequence):
                return None
            return (
                self.frame_sequence,
                self.latest_frame_captured_at,
                self.latest_frame.copy(),
            )

    def get_preview_frame(self):
        if cv2 is None:
            return None, _empty_analysis(), 0.0
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
            analysis = dict(self.analysis)
            last_frame_time = self.last_frame_time
        if frame is None:
            return None, analysis, last_frame_time
        return annotate_sidewalk_edges(frame, analysis), analysis, last_frame_time

    def get_dashboard_camera_pixels(self, width=64, height=32):
        if cv2 is None:
            return []
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return []
        small = cv2.resize(frame, (int(width), int(height)), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        rows = []
        for row in rgb:
            encoded_pixels = []
            for r, g, b in row:
                rgb565 = ((int(r) & 0xF8) << 8) | ((int(g) & 0xFC) << 3) | (int(b) >> 3)
                encoded_pixels.append(f"{rgb565:04x}")
            rows.append("".join(encoded_pixels))
        return rows

    def save_current_frame(self, output_path):
        if cv2 is None:
            return False, "OpenCV unavailable"
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return False, "No Pi camera frame available yet"
        ok = cv2.imwrite(str(output_path), frame)
        if not ok:
            return False, f"Failed to write frame to {output_path}"
        return True, str(output_path)

    def _run(self):
        while self.running and self.capture:
            try:
                ok, frame = self.capture.read()
            except Exception as exc:
                now = time.monotonic()
                if now >= self._capture_error_next_log:
                    self._capture_error_next_log = now + 2.0
                    print(f"Pi camera capture error; retrying: {exc}", flush=True)
                time.sleep(0.05)
                continue
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            captured_at = time.monotonic()
            analysis = _empty_analysis()
            analysis["method"] = "camera_capture"
            analysis["image_width"] = int(frame.shape[1])
            analysis["image_height"] = int(frame.shape[0])
            with self.lock:
                self.analysis = analysis
                self.latest_frame = frame.copy()
                self.latest_frame_captured_at = captured_at
                self.frame_sequence += 1
                now = time.time()
                dt = now - self._fps_last_frame_time
                self.camera_fps = (1.0 / dt) if dt > 0 else 0.0
                self._fps_last_frame_time = now
                self.last_frame_time = now
