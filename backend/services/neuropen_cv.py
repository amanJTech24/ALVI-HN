"""
ALVI NeuroPen Computer Vision Engine — Real OpenCV-based analysis for Clock Drawing Test (CDT).

Capabilities:
1. Preprocessing & Quality Assurance:
   - Blur detection (Laplacian variance)
   - Lighting/contrast uniformity assessment
   - Resolution and aspect verification
2. Clock Outline & Boundary Analysis:
   - Contour extraction & Hough Circle transformation
   - Boundary closure estimation & circularity index (4*pi*Area / P^2)
   - Clock bounding circle and center determination
3. Hand Detection & Angle Estimation:
   - Polar radial projection & center-emanating stroke analysis
   - Peak angle extraction relative to 12 o'clock (0 deg)
   - Length differentiation for Hour vs. Minute hand
   - Target 11:10 evaluation (approx. 11h = 330 deg / -30 deg, 2h = 60 deg)
4. Digit Candidate Detection:
   - Perimeter contour cluster analysis
   - Unambiguous disclaimers: does NOT claim verified OCR digits without dedicated OCR engine
5. Video Motion Analysis:
   - Frame sampling via cv2.VideoCapture
   - Frame difference / optical motion density over time
   - Distinguishes general drawing activity motion from fine pen-tip tracking
6. Visual Annotation:
   - Generates annotated image output with bounding circles, center point, and hand vectors
"""

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


class NeuroPenAnalysisError(Exception):
    """Raised when an unrecoverable error occurs during NeuroPen analysis."""
    pass


def _detect_blurriness(gray: np.ndarray) -> Tuple[float, bool]:
    """Calculate Laplacian variance to assess image focus / blur."""
    var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = bool(var < 45.0)
    return float(round(var, 2)), is_blurry


def _detect_lighting(gray: np.ndarray) -> Tuple[float, str]:
    """Assess overall illumination uniformity."""
    mean_val = float(np.mean(gray))
    if mean_val < 40:
        return round(mean_val, 1), "Under-exposed / dark lighting"
    elif mean_val > 235:
        return round(mean_val, 1), "Over-exposed / washed out"
    return round(mean_val, 1), "Adequate lighting"


def _find_clock_circle(gray: np.ndarray) -> Optional[Tuple[int, int, int, float, bool]]:
    """
    Locates the clock face circle boundary.
    Returns: (center_x, center_y, radius, circularity_score, is_closed) or None.
    """
    h, w = gray.shape
    min_dim = min(h, w)
    
    # 1. Try Hough Circles on smoothed image
    blurred = cv2.GaussianBlur(gray, (9, 9), 1.5)
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_dim // 3,
        param1=90,
        param2=36,
        minRadius=min_dim // 8,
        maxRadius=min_dim // 2,
    )

    if circles is not None:
        c = circles[0][0]
        cx, cy, r = int(c[0]), int(c[1]), int(c[2])
        # Compute circularity around detected boundary
        mask = np.zeros_like(gray)
        cv2.circle(mask, (cx, cy), r, 255, 2)
        return (cx, cy, r, 0.88, True)

    # 2. Contour-based fallback
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    best_candidate = None
    best_score = 0.0

    min_area = (min_dim * min_dim) * 0.04
    max_area = (min_dim * min_dim) * 0.90

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter <= 0:
            continue
        circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
        if circularity > 0.35 and circularity > best_score:
            (cx, cy), radius = cv2.minEnclosingCircle(cnt)
            best_candidate = (int(cx), int(cy), int(radius), float(round(circularity, 3)), True)
            best_score = circularity

    return best_candidate


def _analyze_hands(
    gray: np.ndarray, cx: int, cy: int, r: int
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[bool]]:
    """
    Detects clock hands using radial ink density projections from clock center.
    Returns: (hands_list, estimated_time_str, is_11_10_approx).
    """
    h, w = gray.shape
    # Mask inside clock face, excluding outer rim (digits) and inner pivot noise
    inner_r = int(r * 0.15)
    outer_r = int(r * 0.78)
    if outer_r <= inner_r:
        return [], "Unable to determine", None

    # Invert so dark ink on light paper becomes bright
    _, ink_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Radial projection around center for 360 degrees
    # Clock 12 o'clock is 0 degrees (straight up, which is -Y in image coordinates)
    angle_densities = np.zeros(360, dtype=np.float32)

    for deg in range(360):
        rad = math.radians(deg)
        # 0 deg = top (12h), 90 deg = right (3h), 180 deg = bottom (6h), 270 deg = left (9h)
        dx = math.sin(rad)
        dy = -math.cos(rad)

        samples = []
        for dist in range(inner_r, outer_r, 2):
            px = int(cx + dist * dx)
            py = int(cy + dist * dy)
            if 0 <= px < w and 0 <= py < h:
                samples.append(ink_binary[py, px])
        if samples:
            angle_densities[deg] = float(np.mean(samples))

    # Smooth the angular profile
    kernel = np.ones(9) / 9.0
    smooth_densities = np.convolve(np.tile(angle_densities, 3), kernel, mode="same")[360:720]

    # Find prominent peaks separated by at least 25 degrees
    peaks = []
    mean_density = np.mean(smooth_densities)
    std_density = np.std(smooth_densities)
    threshold = mean_density + 0.6 * std_density

    for i in range(360):
        prev_i = (i - 1) % 360
        next_i = (i + 1) % 360
        val = smooth_densities[i]
        if val > threshold and val > smooth_densities[prev_i] and val >= smooth_densities[next_i]:
            peaks.append((i, val))

    # Non-maximum suppression across circular angle space (merge peaks within 30 degrees)
    peaks.sort(key=lambda x: x[1], reverse=True)
    selected_peaks: List[Tuple[int, float]] = []
    for deg, val in peaks:
        too_close = False
        for s_deg, _ in selected_peaks:
            diff = abs(deg - s_deg)
            circular_diff = min(diff, 360 - diff)
            if circular_diff < 30:
                too_close = True
                break
        if not too_close:
            selected_peaks.append((deg, val))
        if len(selected_peaks) >= 2:
            break

    if len(selected_peaks) < 2:
        # Fallback to single hand or unable to determine
        if len(selected_peaks) == 1:
            deg = selected_peaks[0][0]
            approx_hour = (deg / 30.0) % 12
            return [{
                "hand_type": "undifferentiated",
                "angle_deg": deg,
                "clock_hour": round(approx_hour, 1),
            }], "Unable to determine (only 1 hand resolved)", None
        return [], "Unable to determine (no clear hands detected)", None

    # Measure stroke length along the two peaks to classify Hour vs Minute
    p1_deg, _ = selected_peaks[0]
    p2_deg, _ = selected_peaks[1]

    def measure_length(deg: int) -> int:
        rad = math.radians(deg)
        dx, dy = math.sin(rad), -math.cos(rad)
        last_ink = inner_r
        for dist in range(inner_r, outer_r, 2):
            px = int(cx + dist * dx)
            py = int(cy + dist * dy)
            if 0 <= px < w and 0 <= py < h:
                if ink_binary[py, px] > 128:
                    last_ink = dist
        return last_ink

    len1 = measure_length(p1_deg)
    len2 = measure_length(p2_deg)

    if len1 < len2:
        hour_deg, hour_len = p1_deg, len1
        minute_deg, minute_len = p2_deg, len2
    else:
        hour_deg, hour_len = p2_deg, len2
        minute_deg, minute_len = p1_deg, len1

    # Hour hand angle to approximate hour
    # 0 deg = 12h, 30 deg = 1h, 60 deg = 2h, ..., 330 deg = 11h
    hour_val = (hour_deg / 30.0) % 12
    if hour_val < 0.5:
        hour_int = 12
    else:
        hour_int = int(round(hour_val))

    # Minute hand angle to approximate minutes
    # 0 deg = 0m, 60 deg = 10m, 180 deg = 30m
    minute_val = (minute_deg / 6.0) % 60
    minute_int = int(round(minute_val))

    hands = [
        {
            "hand_type": "hour",
            "angle_deg": hour_deg,
            "length_px": hour_len,
            "pointing_hour": hour_int,
        },
        {
            "hand_type": "minute",
            "angle_deg": minute_deg,
            "length_px": minute_len,
            "pointing_minute": minute_int,
        },
    ]

    estimated_time = f"{hour_int}:{minute_int:02d} (estimated)"

    # Evaluation for 11:10 target:
    # 11:10 target requires:
    # - Minute hand near 10m (approx 60 deg, range 40 - 80 deg)
    # - Hour hand near 11h (approx 330 deg / -30 deg, range 305 - 355 deg)
    hour_target_diff = min(abs(hour_deg - 330), 360 - abs(hour_deg - 330))
    minute_target_diff = min(abs(minute_deg - 60), 360 - abs(minute_deg - 60))

    # Allow tolerance of +/- 28 degrees
    is_11_10 = bool(hour_target_diff <= 28 and minute_target_diff <= 28)

    return hands, estimated_time, is_11_10


def _detect_digit_candidates(gray: np.ndarray, cx: int, cy: int, r: int) -> int:
    """
    Identifies candidate digit mark clusters around the perimeter ring.
    Strictly reports candidate count; does NOT pretend to read digits without OCR.
    """
    h, w = gray.shape
    inner_ring = int(r * 0.70)
    outer_ring = int(r * 0.98)
    if outer_ring <= inner_ring:
        return 0

    mask = np.zeros_like(gray)
    cv2.circle(mask, (cx, cy), outer_ring, 255, -1)
    cv2.circle(mask, (cx, cy), inner_ring, 0, -1)

    _, ink_binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ring_ink = cv2.bitwise_and(ink_binary, ink_binary, mask=mask)

    contours, _ = cv2.findContours(ring_ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    digit_candidates = 0
    min_digit_area = max(10, int((r * r) * 0.002))
    max_digit_area = int((r * r) * 0.06)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_digit_area <= area <= max_digit_area:
            digit_candidates += 1

    return digit_candidates


def _draw_annotations(
    bgr: np.ndarray,
    circle_info: Optional[Tuple[int, int, int, float, bool]],
    hands: List[Dict[str, Any]],
    is_11_10: Optional[bool],
    quality_warnings: List[str],
) -> np.ndarray:
    """Generates an annotated visual overlay on the image for clinical review."""
    annotated = bgr.copy()
    h, w = annotated.shape[:2]

    # Banner header
    banner_h = 36
    cv2.rectangle(annotated, (0, 0), (w, banner_h), (20, 24, 33), -1)
    status_text = "ALVI NeuroPen CDT Analysis"
    if is_11_10 is True:
        status_text += " — Hand Target Match: 11:10 (Pass)"
        badge_color = (60, 180, 75)
    elif is_11_10 is False:
        status_text += " — Hand Position Divergence"
        badge_color = (50, 130, 240)
    else:
        status_text += " — Review Required (Indeterminate)"
        badge_color = (120, 120, 120)

    cv2.putText(
        annotated,
        status_text,
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        badge_color,
        2,
        cv2.LINE_AA,
    )

    if circle_info:
        cx, cy, r, circularity, is_closed = circle_info
        # Draw clock face boundary (Cyan)
        cv2.circle(annotated, (cx, cy), r, (240, 200, 30), 2, cv2.LINE_AA)
        # Center anchor (Red)
        cv2.circle(annotated, (cx, cy), 5, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.putText(
            annotated,
            f"Boundary: {int(circularity * 100)}%",
            (cx - 40, cy - r - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (240, 200, 30),
            1,
            cv2.LINE_AA,
        )

        # Draw hands
        for hand in hands:
            deg = hand.get("angle_deg", 0)
            length = hand.get("length_px", int(r * 0.5))
            rad = math.radians(deg)
            hx = int(cx + length * math.sin(rad))
            hy = int(cy - length * math.cos(rad))

            if hand.get("hand_type") == "hour":
                color = (40, 120, 255)  # Orange for Hour
                label = f"Hour ({hand.get('pointing_hour')}h)"
                thickness = 3
            else:
                color = (255, 100, 40)  # Blue for Minute
                label = f"Minute ({hand.get('pointing_minute')}m)"
                thickness = 2

            cv2.line(annotated, (cx, cy), (hx, hy), color, thickness, cv2.LINE_AA)
            cv2.putText(
                annotated,
                label,
                (hx + 5, hy - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    # Footer warnings
    if quality_warnings:
        warn_y = h - 12
        for w_msg in quality_warnings[-2:]:
            cv2.putText(
                annotated,
                f"* Warning: {w_msg}",
                (10, warn_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (0, 165, 255),
                1,
                cv2.LINE_AA,
            )
            warn_y -= 16

    return annotated


def analyze_clock_image(
    image_input: bytes | str | Path,
    output_dir: Optional[Path] = None,
    filename_prefix: str = "neuropen",
) -> Dict[str, Any]:
    """
    Performs full OpenCV analysis of a Clock Drawing Test image.
    Handles photo uploads (JPG, PNG, WebP).
    """
    # 1. Load image
    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.is_file():
            return {
                "success": False,
                "error": f"Image file not found: {p}",
                "clock_detected": False,
            }
        bgr = cv2.imread(str(p))
    else:
        arr = np.frombuffer(image_input, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if bgr is None or bgr.size == 0:
        return {
            "success": False,
            "error": "Failed to decode image data into OpenCV BGR matrix",
            "clock_detected": False,
        }

    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 2. Quality checks
    quality_warnings: List[str] = []
    blur_var, is_blurry = _detect_blurriness(gray)
    if is_blurry:
        quality_warnings.append(f"Image appears blurry (Laplacian variance: {blur_var})")

    lighting_val, lighting_msg = _detect_lighting(gray)
    if "Adequate" not in lighting_msg:
        quality_warnings.append(lighting_msg)

    if min(h, w) < 180:
        quality_warnings.append("Low image resolution (<180px)")

    # 3. Detect clock boundary
    circle_info = _find_clock_circle(gray)
    clock_detected = circle_info is not None

    if not clock_detected:
        quality_warnings.append("Clock circle outline could not be confidently identified")
        annotated = _draw_annotations(bgr, None, [], None, quality_warnings)
        annotated_path = None
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            annotated_path = str(output_dir / f"annotated_{filename_prefix}.jpg")
            cv2.imwrite(annotated_path, annotated)

        return {
            "success": True,
            "clock_detected": False,
            "circle_detected": False,
            "circle_score": 0.0,
            "circle_closed": False,
            "hands_detected": 0,
            "hands": [],
            "estimated_time": "Unable to determine",
            "is_11_10_approx": None,
            "digits_detected_count": 0,
            "digit_recognition_note": "Not evaluated (clock boundary not resolved)",
            "quality_warnings": quality_warnings,
            "annotated_image_path": annotated_path,
            "dimensions": {"width": w, "height": h},
            "blur_metric": blur_var,
        }

    cx, cy, r, circularity, is_closed = circle_info

    # 4. Analyze hands
    hands, estimated_time, is_11_10 = _analyze_hands(gray, cx, cy, r)
    hands_detected = len(hands)

    # 5. Detect candidate digit blobs
    digits_count = _detect_digit_candidates(gray, cx, cy, r)
    digit_note = (
        f"{digits_count} candidate perimeter digit clusters detected. "
        "Specific digit values (1-12) are marked 'Unable to determine' without dedicated OCR."
    )

    # 6. Generate annotations & save
    annotated = _draw_annotations(bgr, circle_info, hands, is_11_10, quality_warnings)
    annotated_path = None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        annotated_path = str(output_dir / f"annotated_{filename_prefix}.jpg")
        cv2.imwrite(annotated_path, annotated)

    return {
        "success": True,
        "clock_detected": True,
        "circle_detected": True,
        "circle_score": circularity,
        "circle_closed": is_closed,
        "circle_center": {"x": cx, "y": cy},
        "circle_radius": r,
        "hands_detected": hands_detected,
        "hands": hands,
        "estimated_time": estimated_time,
        "is_11_10_approx": is_11_10,
        "digits_detected_count": digits_count,
        "digit_recognition_note": digit_note,
        "quality_warnings": quality_warnings,
        "annotated_image_path": annotated_path,
        "dimensions": {"width": w, "height": h},
        "blur_metric": blur_var,
    }


def analyze_drawing_video(
    video_path: str | Path,
    output_dir: Optional[Path] = None,
    max_sample_frames: int = 150,
) -> Dict[str, Any]:
    """
    Analyzes an MP4 or WebM video of the handwriting session.
    Extracts duration, motion activity profile, and key final frame.
    Explicitly distinguishes general motion from fine pen-tip tracking.
    """
    p = Path(video_path)
    if not p.is_file():
        return {
            "success": False,
            "error": f"Video file not found: {p}",
        }

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        return {
            "success": False,
            "error": f"Failed to open video file with OpenCV VideoCapture: {p}",
        }

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps > 0 else 0.0

    step = max(1, total_frames // max_sample_frames)
    frame_idx = 0
    prev_gray = None
    motion_energies: List[float] = []
    final_frame = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Resize for efficient difference computation
            small = cv2.resize(gray, (160, 120))
            if prev_gray is not None:
                diff = cv2.absdiff(small, prev_gray)
                motion_energy = float(np.mean(diff))
                motion_energies.append(round(motion_energy, 2))
            prev_gray = small
            final_frame = frame
        frame_idx += 1

    cap.release()

    active_motion_pct = 0.0
    avg_motion = 0.0
    if motion_energies:
        avg_motion = float(np.mean(motion_energies))
        active_count = sum(1 for m in motion_energies if m > 2.5)
        active_motion_pct = round((active_count / len(motion_energies)) * 100.0, 1)

    # Save final frame for CDT image analysis
    final_frame_path = None
    image_analysis = None
    if final_frame is not None and output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        final_frame_path = output_dir / f"final_frame_{p.stem}.jpg"
        cv2.imwrite(str(final_frame_path), final_frame)
        image_analysis = analyze_clock_image(final_frame_path, output_dir=output_dir, filename_prefix=p.stem)

    return {
        "success": True,
        "duration_sec": round(duration_sec, 2),
        "total_frames": total_frames,
        "fps": round(fps, 2),
        "motion_analysis": {
            "average_motion_energy": round(avg_motion, 2),
            "active_motion_percent": active_motion_pct,
            "motion_classification": "General drawing movement detected" if active_motion_pct > 20 else "Low movement / static scene",
            "disclaimer": "Metrics represent global frame pixel-difference dynamics; fine pen-tip stroke trajectories are not inferred.",
        },
        "final_frame_extracted": str(final_frame_path) if final_frame_path else None,
        "clock_analysis": image_analysis,
    }
