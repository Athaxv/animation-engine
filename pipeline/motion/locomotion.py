"""
R6 Locomotion and Foot-Planting Subsystem.

Provides:
- S-curve acceleration and deceleration root trajectories
- Optimal gait calculation (stride period, arm/leg swing, lean, bobbing) matching speed
- Foot-planting synchronization to prevent moonwalking / foot sliding
- Direction-aware turning with pre-turn head anticipation and torso banking
- Multi-waypoint path traversal generator
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from pipeline.motion.blending import ease_in_out_cubic, ease_in_quad, ease_out_quad, unwrap_angle_deg

# Gait physical constants (R6 leg length = 1.9 studs)
LEG_LENGTH = 1.9


def calculate_optimal_gait(speed: float, fps: int = 30) -> Dict[str, Any]:
    """
    Computes gait parameters dynamically adapted to movement speed:
    - Matches stride frequency to ground velocity to eliminate foot sliding
    - Sets speed-proportional spine lean and vertical root bobbing
    """
    speed = max(1.0, float(speed))

    if speed <= 8.0:
        # Walking
        gait_name = "walk"
        swing_leg = 32.0 + (speed / 8.0) * 6.0    # 32 to 38 deg
        swing_arm = 30.0 + (speed / 8.0) * 8.0    # 30 to 38 deg
        lean = 2.0 + (speed / 8.0) * 3.0          # 2 to 5 deg forward
        bob = 0.05 + (speed / 8.0) * 0.03         # 0.05 to 0.08 studs
    elif speed <= 15.0:
        # Running
        gait_name = "run"
        u = (speed - 8.0) / 7.0
        swing_leg = 38.0 + u * 14.0                # 38 to 52 deg
        swing_arm = 38.0 + u * 22.0                # 38 to 60 deg
        lean = 5.0 + u * 7.0                       # 5 to 12 deg
        bob = 0.08 + u * 0.07                      # 0.08 to 0.15 studs
    else:
        # Sprinting
        gait_name = "sprint"
        u = min(1.0, (speed - 15.0) / 10.0)
        swing_leg = 52.0 + u * 12.0                # 52 to 64 deg
        swing_arm = 60.0 + u * 15.0                # 60 to 75 deg
        lean = 12.0 + u * 5.0                      # 12 to 17 deg
        bob = 0.15 + u * 0.05                      # 0.15 to 0.20 studs

    # Stride length for this leg swing amplitude: L_stride = 2 * L_leg * sin(swing_leg)
    rad_swing = math.radians(swing_leg)
    stride_length = 2.0 * LEG_LENGTH * math.sin(rad_swing)

    # Period P (frames) = (stride_length / speed) * fps
    # One full cycle has two steps (left foot contact + right foot contact)
    raw_period = (stride_length / speed) * fps
    # Round to an even integer for quarter-phase symmetry
    period = max(8, int(round(raw_period / 2.0) * 2))

    return {
        "gait": gait_name,
        "speed": speed,
        "period": period,
        "stride_length": round(stride_length, 3),
        "swing_leg": round(swing_leg, 2),
        "swing_arm": round(swing_arm, 2),
        "lean": round(lean, 2),
        "bob": round(bob, 3),
    }


def generate_scurve_trajectory(
    frames: int,
    dist: float,
    acc_frames: int = 6,
    dec_frames: int = 6,
) -> List[float]:
    """
    Generates cumulative distance travelled at each frame step 0..frames using
    an acceleration -> cruise -> deceleration profile.
    Returns list of length (frames + 1) with values in [0.0, dist].
    """
    frames = max(2, int(frames))
    acc = min(acc_frames, frames // 3)
    dec = min(dec_frames, frames // 3)
    cruise = frames - acc - dec

    # Weights per frame:
    # During acc (t in 0..acc): ramp from 0 to 1
    # During cruise: 1
    # During dec (t in 0..dec): ramp from 1 to 0
    weights = []
    for f in range(frames):
        if f < acc:
            w = (f + 0.5) / max(1, acc)
        elif f < acc + cruise:
            w = 1.0
        else:
            w = 1.0 - (f - (acc + cruise) + 0.5) / max(1, dec)
        weights.append(max(0.01, w))

    total_w = sum(weights)
    scale = dist / total_w if total_w > 1e-6 else 0.0

    trajectory = [0.0]
    cum = 0.0
    for w in weights:
        cum += w * scale
        trajectory.append(round(cum, 4))
    trajectory[-1] = round(dist, 4)
    return trajectory


def calculate_turn_telemetry(
    current_heading_deg: float,
    target_heading_deg: float,
    dur_frames: int = 6,
) -> List[Dict[str, Any]]:
    """
    Calculates frame-by-frame heading, pre-turn head anticipation, and spine bank angle.
    Head leads body by 2 frames; spine banks into turn by up to 4 degrees.
    """
    dur_frames = max(2, int(dur_frames))
    unwrapped_target = unwrap_angle_deg(current_heading_deg, target_heading_deg)
    delta = unwrapped_target - current_heading_deg
    turn_dir = 1.0 if delta > 0 else -1.0
    bank_max = min(4.5, abs(delta) * 0.05) * turn_dir

    telemetry = []
    for f in range(dur_frames + 1):
        t = f / float(dur_frames)
        w_root = ease_in_out_cubic(t)
        root_h = current_heading_deg + delta * w_root

        # Head anticipation: leads root by 2 frames (t + 2/dur)
        t_head = min(1.0, (f + 2) / float(dur_frames))
        w_head = ease_in_out_cubic(t_head)
        # Head yaw offset relative to torso
        head_lead_deg = (w_head - w_root) * delta * 0.4

        # Torso bank (peaks around middle of turn)
        bank_deg = bank_max * math.sin(math.pi * t)

        telemetry.append({
            "frame_offset": f,
            "heading": round(root_h % 360.0, 2),
            "head_yaw": round(head_lead_deg, 2),
            "spine_roll": round(bank_deg, 2),
        })

    return telemetry


def measure_foot_sliding(
    root_start: Tuple[float, float, float],
    root_end: Tuple[float, float, float],
    frames: int,
    period: int,
    stride_length: float,
) -> float:
    """
    Calculates foot sliding metric (studs of drift):
    Compares expected stance-foot ground sweep against actual root displacement.
    Returns 0.0 for perfectly synchronized foot planting.
    """
    dx = root_end[0] - root_start[0]
    dy = root_end[1] - root_start[1]
    actual_dist = math.sqrt(dx * dx + dy * dy)

    # Number of strides completed
    strides = frames / float(max(1, period))
    expected_dist = strides * stride_length

    drift = abs(actual_dist - expected_dist)
    return round(drift, 3)
