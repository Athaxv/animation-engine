"""
Analytical R6 Kinematics Subsystem.

Provides:
- Analytical single-bone spherical Inverse Kinematics (IK) for R6 shoulders
- Forward Kinematics (FK) for hand contact point prediction
- Spine-compensated reach solver (bending waist to reach ground / low props)
- Anatomical joint limit enforcement (preventing unnatural bone breaks)
- Head gaze / look-at solver for tracking actors and props
- Mutual facing angle calculators
"""
import math
from typing import Any, Dict, Optional, Tuple

# R6 Rig Anatomy Constants (studs, relative to rig root origin)
SHOULDER_L = (1.5, 0.0, 3.5)
SHOULDER_R = (-1.5, 0.0, 3.5)
HIP_L = (0.5, 0.0, 2.0)
HIP_R = (-0.5, 0.0, 2.0)
NECK_PIVOT = (0.0, 0.0, 4.0)
SPINE_PIVOT = (0.0, 0.0, 2.0)

ARM_LENGTH = 1.5
GRIP_REACH = 1.9
LEG_LENGTH = 1.9

# Anatomical Joint Limits (degrees)
LIMITS_ARM_RX = (-180.0, 45.0)   # -180: straight up, -90: horizontal fwd, 0: down, +45: back
LIMITS_ARM_RY = (-90.0, 90.0)     # side-to-side abduction / adduction
LIMITS_ARM_RZ = (-60.0, 60.0)
LIMITS_HEAD_PITCH = (-35.0, 35.0) # -35: tilt up, +35: nod down
LIMITS_HEAD_YAW = (-60.0, 60.0)   # side turn
LIMITS_SPINE_LEAN = (-15.0, 45.0) # lean back / forward


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(val)))


def forward_arm_fk(
    rot_deg: Tuple[float, float, float],
    side: str = "R",
    spine_rot_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    arm_length: float = ARM_LENGTH,
) -> Tuple[float, float, float]:
    """
    Computes evaluated hand position in character-local space given arm and spine rotations.
    """
    side = side.upper()
    s_pivot = SHOULDER_L if side == "L" else SHOULDER_R

    # 1. Base unit vector pointing along rest arm axis: (0, 0, -1)
    rx, ry, rz = [math.radians(a) for a in rot_deg]

    # Evaluate R_x(rx) @ R_y(ry) @ (0, 0, -1)
    # ux = -sin(ry)
    # uy = sin(rx) * cos(ry)
    # uz = -cos(rx) * cos(ry)
    ux = -math.sin(ry)
    uy = math.sin(rx) * math.cos(ry)
    uz = -math.cos(rx) * math.cos(ry)

    arm_vec = (ux * arm_length, uy * arm_length, uz * arm_length)

    # Spine lean forward rotates shoulder around SPINE_PIVOT (0, 0, 2.0)
    srx = math.radians(spine_rot_deg[0])
    if abs(srx) > 1e-4:
        dz = s_pivot[2] - SPINE_PIVOT[2]
        shoulder_y = -dz * math.sin(srx)
        shoulder_z = SPINE_PIVOT[2] + dz * math.cos(srx)
        sp = (s_pivot[0], shoulder_y, shoulder_z)
    else:
        sp = s_pivot

    return (
        round(sp[0] + arm_vec[0], 3),
        round(sp[1] + arm_vec[1], 3),
        round(sp[2] + arm_vec[2], 3),
    )


def solve_arm_ik(
    target_local: Tuple[float, float, float],
    side: str = "R",
    allow_spine_lean: bool = True,
    arm_length: float = ARM_LENGTH,
) -> Dict[str, Any]:
    """
    Solves for single-bone arm Euler rotation (and optional spine lean) to direct
    the hand to `target_local` = (tx, ty, tz) in character-local space.

    Returns:
      {
        "upper_arm.<side>": (rx, ry, rz),
        "spine": (lean_x, 0, 0),
        "hand_pos": (hx, hy, hz),
        "reachable": bool,
        "contact_distance": float
      }
    """
    side = side.upper()
    bone_name = f"upper_arm.{side}"
    s_pivot = SHOULDER_L if side == "L" else SHOULDER_R

    tx, ty, tz = target_local
    spine_lean = 0.0

    # If target is far forward or below waist level (tz < 2.2) and spine lean is permitted,
    # lean waist forward to extend reach.
    if allow_spine_lean:
        init_dist = math.sqrt(
            (tx - s_pivot[0]) ** 2 +
            (ty - s_pivot[1]) ** 2 +
            (tz - s_pivot[2]) ** 2
        )
        needed_forward = max(0.0, init_dist - (arm_length * 0.95))
        needed_drop = max(0.0, 2.2 - tz)
        needed_lean = max(needed_forward * 22.0, needed_drop * 22.0)
        spine_lean = clamp(needed_lean, 0.0, LIMITS_SPINE_LEAN[1])

    srx = math.radians(spine_lean)
    dz = s_pivot[2] - SPINE_PIVOT[2]
    shoulder_y = -dz * math.sin(srx)
    shoulder_z = SPINE_PIVOT[2] + dz * math.cos(srx)
    eff_shoulder = (s_pivot[0], shoulder_y, shoulder_z)

    # Direction vector from effective shoulder to target
    dx = tx - eff_shoulder[0]
    dy = ty - eff_shoulder[1]
    dz_target = tz - eff_shoulder[2]

    dist = math.sqrt(dx * dx + dy * dy + dz_target * dz_target)
    if dist < 1e-4:
        return {
            bone_name: (0.0, 0.0, 0.0),
            "spine": (round(spine_lean, 2), 0.0, 0.0),
            "hand_pos": eff_shoulder,
            "reachable": True,
            "contact_distance": 0.0,
        }

    ux = dx / dist
    uy = dy / dist
    uz = dz_target / dist

    # Analytical spherical Euler XYZ extraction from direction unit vector
    # ux = -sin(ry) -> ry = -asin(ux)
    ry_rad = -math.asin(clamp(ux, -1.0, 1.0))
    cos_ry = math.cos(ry_rad)

    if abs(cos_ry) > 1e-4:
        rx_rad = math.atan2(uy / cos_ry, -uz / cos_ry)
    else:
        rx_rad = -math.pi * 0.5 if uy < 0 else math.pi * 0.5

    rx_deg = math.degrees(rx_rad)
    ry_deg = math.degrees(ry_rad)
    rz_deg = 0.0

    # Clamp within anatomical limits
    clamped_rx = clamp(rx_deg, LIMITS_ARM_RX[0], LIMITS_ARM_RX[1])
    clamped_ry = clamp(ry_deg, LIMITS_ARM_RY[0], LIMITS_ARM_RY[1])

    hand_pos = forward_arm_fk(
        (clamped_rx, clamped_ry, rz_deg),
        side=side,
        spine_rot_deg=(spine_lean, 0.0, 0.0),
        arm_length=arm_length,
    )

    contact_dist = math.sqrt(
        (hand_pos[0] - tx) ** 2 +
        (hand_pos[1] - ty) ** 2 +
        (hand_pos[2] - tz) ** 2
    )

    reachable = (dist <= GRIP_REACH) and (contact_dist <= 0.35)

    return {
        bone_name: (round(clamped_rx, 2), round(clamped_ry, 2), round(rz_deg, 2)),
        "spine": (round(spine_lean, 2), 0.0, 0.0),
        "hand_pos": hand_pos,
        "reachable": reachable,
        "contact_distance": round(contact_dist, 3),
    }


def solve_look_at(
    target_local: Tuple[float, float, float],
    max_yaw: float = LIMITS_HEAD_YAW[1],
    max_pitch: float = LIMITS_HEAD_PITCH[1],
) -> Dict[str, Tuple[float, float, float]]:
    """
    Solves for head pitch and yaw to gaze toward `target_local` relative to character neck.
    In R6 axes:
      head X+: nod forward/down, X-: tilt up
      head Y+: turn toward character's left (+X), Y-: turn toward right (-X)
    """
    tx, ty, tz = target_local
    dx = tx - NECK_PIVOT[0]
    dy = ty - NECK_PIVOT[1]
    dz = tz - NECK_PIVOT[2]

    horiz_dist = math.sqrt(dx * dx + dy * dy)
    if horiz_dist < 1e-4 and abs(dz) < 1e-4:
        return {"head": (0.0, 0.0, 0.0)}

    # Pitch: looking up (dz > 0) -> X < 0; looking down (dz < 0) -> X > 0
    pitch_rad = -math.atan2(dz, max(1e-3, horiz_dist))
    pitch_deg = clamp(math.degrees(pitch_rad), -max_pitch, max_pitch)

    # Yaw: Character front faces -Y. Target at +X (left) -> Y > 0; Target at -X (right) -> Y < 0
    yaw_rad = math.atan2(dx, -dy)
    yaw_deg = clamp(math.degrees(yaw_rad), -max_yaw, max_yaw)

    return {"head": (round(pitch_deg, 2), round(yaw_deg, 2), 0.0)}


def solve_mutual_facing(
    pos_a: Tuple[float, float, float],
    pos_b: Tuple[float, float, float],
) -> Tuple[float, float]:
    """
    Computes world heading angles (degrees) for two characters at pos_a and pos_b
    to face each other directly.
    Heading 0 faces -Y. Heading 90 faces +X. Heading 180/-180 faces +Y. Heading -90 faces -X.
    """
    dx = pos_b[0] - pos_a[0]
    dy = pos_b[1] - pos_a[1]

    # Angle from A to B
    heading_a = math.degrees(math.atan2(dx, -dy))
    # Angle from B to A (opposite direction)
    heading_b = math.degrees(math.atan2(-dx, dy))

    return round(heading_a, 2), round(heading_b, 2)


def world_to_local_point(
    world_pt: Tuple[float, float, float],
    root_pos: Tuple[float, float, float],
    root_heading_deg: float,
) -> Tuple[float, float, float]:
    """Transforms a world 3D coordinate into character root-local coordinate space."""
    rx = world_pt[0] - root_pos[0]
    ry = world_pt[1] - root_pos[1]
    rz = world_pt[2] - root_pos[2]

    h_rad = math.radians(-root_heading_deg)
    cos_h = math.cos(h_rad)
    sin_h = math.sin(h_rad)

    lx = rx * cos_h - ry * sin_h
    ly = rx * sin_h + ry * cos_h
    return (round(lx, 3), round(ly, 3), round(rz, 3))


def local_to_world_point(
    local_pt: Tuple[float, float, float],
    root_pos: Tuple[float, float, float],
    root_heading_deg: float,
) -> Tuple[float, float, float]:
    """Transforms a character root-local coordinate into world coordinate space."""
    h_rad = math.radians(root_heading_deg)
    cos_h = math.cos(h_rad)
    sin_h = math.sin(h_rad)

    wx = local_pt[0] * cos_h - local_pt[1] * sin_h + root_pos[0]
    wy = local_pt[0] * sin_h + local_pt[1] * cos_h + root_pos[1]
    wz = local_pt[2] + root_pos[2]
    return (round(wx, 3), round(wy, 3), round(wz, 3))
