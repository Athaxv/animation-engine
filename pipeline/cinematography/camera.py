"""
Cinematic Camera Intelligence Subsystem.

Provides:
- Comprehensive shot composition vocabulary (extreme wide to extreme close-up, OTS, POV)
- Character-aware and multi-character framing with vertical safe-area headroom calculation
- Conversational axis tracking (180-degree rule enforcement)
- Ray-tested obstacle avoidance and camera clearance cones
- Quintic S-curve smooth camera movement trajectories (dolly, truck, pan, crane, orbit, track)
"""
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from mathutils import Vector, Euler, Quaternion
except ImportError:
    # Pure Python Vector fallback for non-Blender testing environments
    class Vector(tuple):
        def __new__(cls, coords=(0.0, 0.0, 0.0)):
            return super().__new__(cls, (float(coords[0]), float(coords[1]), float(coords[2])))

        @property
        def x(self): return self[0]
        @property
        def y(self): return self[1]
        @property
        def z(self): return self[2]

        def __add__(self, other):
            return Vector((self.x + other[0], self.y + other[1], self.z + other[2]))

        def __sub__(self, other):
            return Vector((self.x - other[0], self.y - other[1], self.z - other[2]))

        def __mul__(self, scalar):
            return Vector((self.x * scalar, self.y * scalar, self.z * scalar))

        def __rmul__(self, scalar):
            return self.__mul__(scalar)

        def __truediv__(self, scalar):
            return Vector((self.x / scalar, self.y / scalar, self.z / scalar))

        def __neg__(self):
            return Vector((-self.x, -self.y, -self.z))

        @property
        def length(self):
            return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

        def normalized(self):
            L = self.length
            return Vector((self.x / L, self.y / L, self.z / L)) if L > 1e-6 else Vector((0, 0, 0))

        def copy(self):
            return Vector((self.x, self.y, self.z))

        def lerp(self, other, t):
            return Vector((
                self.x + (other[0] - self.x) * t,
                self.y + (other[1] - self.y) * t,
                self.z + (other[2] - self.z) * t
            ))

        def dot(self, other):
            return self.x * other[0] + self.y * other[1] + self.z * other[2]

        def cross(self, other):
            return Vector((
                self.y * other[2] - self.z * other[1],
                self.z * other[0] - self.x * other[2],
                self.x * other[1] - self.y * other[0]
            ))


# ---------------------------------------------------------------------------
# Camera Constants & Vocabulary
# ---------------------------------------------------------------------------
HEAD_Z = 4.62
DEFAULT_LENS = 35.0
SENSOR_WIDTH = 36.0
SENSOR_HEIGHT = 24.0

# Framing Heights (studs visible in vertical frame)
FRAME_H: Dict[str, float] = {
    "extreme_wide": 40.0,
    "wide": 15.0,
    "establishing": 18.0,
    "full_body": 10.0,
    "medium": 6.6,
    "medium_close": 4.4,
    "close_up": 3.1,
    "extreme_close_up": 1.9,
    "two_shot": 7.2,
    "group": 8.5,
    "over_shoulder": 6.0,
    "pov": 5.0,
    "insert": 2.4,
}

# Look Target Heights (studs from ground)
LOOK_Z: Dict[str, float] = {
    "extreme_wide": 5.0,
    "wide": 3.6,
    "establishing": 4.5,
    "full_body": 3.8,
    "medium": 3.4,
    "medium_close": 4.0,
    "close_up": 4.45,
    "extreme_close_up": 4.62,
    "two_shot": 3.5,
    "group": 3.6,
    "over_shoulder": 4.3,
    "pov": 4.4,
    "insert": 3.0,
}

# Depth of Field F-Stop Presets
FSTOP: Dict[str, float] = {
    "extreme_close_up": 2.2,
    "close_up": 2.8,
    "medium_close": 3.5,
    "insert": 2.4,
    "over_shoulder": 3.2,
    "pov": 4.0,
}


def fwd_vector(yaw: float) -> Vector:
    """Returns forward unit vector for a given yaw angle in radians."""
    return Vector((math.sin(yaw), -math.cos(yaw), 0.0))


def right_vector(yaw: float) -> Vector:
    """Returns right unit vector for a given yaw angle in radians."""
    return Vector((math.cos(yaw), math.sin(yaw), 0.0))


def quintic_ease(t: float) -> float:
    """Quintic S-curve easing: 6t^5 - 15t^4 + 10t^3."""
    t = max(0.0, min(1.0, float(t)))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


# ---------------------------------------------------------------------------
# Conversational Axis & 180-Degree Rule
# ---------------------------------------------------------------------------
class ConversationalAxisTracker:
    """
    Maintains conversational continuity and prevents disorienting 180-degree axis jumps.

    When two characters converse, an invisible 'Line of Action' connects them.
    All cameras covering the conversation should stay on one side of this line
    so Character A consistently appears on one side of screen facing the other.
    """
    def __init__(self):
        self._last_axis_side: Dict[Tuple[str, str], int] = {}  # (actor_a, actor_b) -> +1 or -1

    def get_or_set_axis_side(
        self,
        actor_a: str,
        actor_b: str,
        pos_a: Vector,
        pos_b: Vector,
        desired_cam_pos: Optional[Vector] = None
    ) -> int:
        key = tuple(sorted([actor_a, actor_b]))
        if key in self._last_axis_side:
            return self._last_axis_side[key]

        # Determine side from initial camera or default to screen-left for actor_a
        line = pos_b - pos_a
        normal = Vector((-line.y, line.x, 0.0)).normalized()

        if desired_cam_pos is not None:
            midpoint = (pos_a + pos_b) * 0.5
            cam_dir = desired_cam_pos - midpoint
            side = 1 if normal.dot(cam_dir) >= 0 else -1
        else:
            side = 1

        self._last_axis_side[key] = side
        return side

    def reset(self):
        self._last_axis_side.clear()


# Global axis tracker instance
AXIS_TRACKER = ConversationalAxisTracker()


# ---------------------------------------------------------------------------
# Framing & Positioning Calculation
# ---------------------------------------------------------------------------
def calculate_framing(
    shot_type: str,
    target_pos: Vector,
    target_yaw: float,
    angle: str = "eye",
    lens: float = DEFAULT_LENS,
    body_bounds: Optional[Tuple[Vector, Vector]] = None,
    secondary_target_pos: Optional[Vector] = None,
    secondary_yaw: Optional[float] = None,
    group_positions: Optional[List[Vector]] = None,
    distance_mult: float = 1.0,
    orbit_angle: float = 0.0,
    truck_offset: float = 0.0,
    axis_side: int = 1,
) -> Tuple[Vector, Vector, float]:
    """
    Computes camera world position, look point, and roll angle for any cinematic shot type.

    Returns:
        (cam_pos, look_pos, roll_radians)
    """
    tan_half = 18.0 / lens
    H = FRAME_H.get(shot_type, 6.6)
    lz = LOOK_Z.get(shot_type, 3.4)

    # Base look point
    if body_bounds:
        feet, head = body_bounds
        look = feet + (head - feet) * (lz / HEAD_Z)
    else:
        look = target_pos + Vector((0.0, 0.0, lz))

    # Multi-character bounding (two-shot & group)
    if shot_type in ("two_shot", "group") and group_positions and len(group_positions) > 1:
        pts = group_positions
        mid = sum(pts, Vector()) / len(pts)
        look = Vector((mid.x, mid.y, look.z))

        # Horizontal span
        span_x = max(abs(p.x - mid.x) for p in pts) * 2.0 + 3.5
        span_y = max(abs(p.y - mid.y) for p in pts) * 2.0 + 3.5
        span = max(span_x, span_y)

        # Headroom & social media safe area (window y in [0.22, 0.85] -> factor 0.63)
        H = max(H, span * (16.0 / 9.0) * 0.85, (HEAD_Z + 1.5) / 0.63)

    # Over-The-Shoulder (OTS) Framing
    if shot_type == "over_shoulder" and secondary_target_pos is not None:
        # Looking over target_pos (forefront character) at secondary_target_pos (focal speaker)
        ch_a = target_pos
        ch_b = secondary_target_pos
        line = (ch_b - ch_a).normalized()
        perp = Vector((-line.y, line.x, 0.0)) * (0.85 * axis_side)

        # Camera placed behind character A's shoulder
        cam_pos = ch_a - line * (3.8 * distance_mult) + perp + Vector((0.0, 0.0, 4.8))
        look_pos = ch_b + Vector((0.0, 0.0, LOOK_Z["medium_close"]))
        roll = math.radians(10.0 if angle == "dutch" else 0.0)
        return cam_pos, look_pos, roll

    # Character POV Framing
    if shot_type == "pov":
        # Eye level position, pushed slightly forward in facing direction
        fy = fwd_vector(target_yaw)
        cam_pos = target_pos + Vector((0.0, 0.0, 4.3)) + fy * 0.6
        if secondary_target_pos:
            look_pos = secondary_target_pos + Vector((0.0, 0.0, 3.8))
        else:
            look_pos = cam_pos + fy * 12.0
        roll = math.radians(10.0 if angle == "dutch" else 0.0)
        return cam_pos, look_pos, roll

    # Standard / Angle-aware positioning
    dist = (H / (2.0 * tan_half)) * distance_mult

    # Direction vector from target toward camera
    fwd = fwd_vector(target_yaw)
    d = Vector((0.0, -1.0, 0.0))
    if fwd.y > 0.3 and shot_type not in ("two_shot", "group", "wide", "extreme_wide"):
        d = (fwd + Vector((0.0, -0.3, 0.0))).normalized()
    else:
        d = (d * 0.75 + fwd * 0.25).normalized()

    # Apply azimuthal orbit
    if orbit_angle != 0.0:
        cos_o = math.cos(orbit_angle)
        sin_o = math.sin(orbit_angle)
        d = Vector((d.x * cos_o - d.y * sin_o, d.x * sin_o + d.y * cos_o, 0.0)).normalized()

    # Base camera position
    cam_pos = look + d * dist

    # Lateral truck offset
    if truck_offset != 0.0:
        side = Vector((-d.y, d.x, 0.0))
        cam_pos += side * truck_offset
        look += side * (truck_offset * 0.4)

    # Elevation Angles
    if angle == "low":
        # Low-angle hero perspective (camera low, looking up)
        cam_pos = Vector((cam_pos.x, cam_pos.y, max(target_pos.z + 0.8, look.z - 0.42 * dist)))
    elif angle == "high":
        # High-angle dramatic perspective (camera high, looking down)
        cam_pos = Vector((cam_pos.x, cam_pos.y, look.z + 0.65 * dist))
    elif angle in ("top", "birds_eye"):
        # Top-down / bird's-eye perspective
        cam_pos = Vector((look.x, look.y, look.z + dist * 1.35))
    else:
        # Eye level standard
        cam_pos = Vector((cam_pos.x, cam_pos.y, look.z + 0.08 * dist))

    roll = math.radians(10.0 if angle == "dutch" else 0.0)
    return cam_pos, look, roll


# ---------------------------------------------------------------------------
# Obstacle Avoidance & Clearance Cone
# ---------------------------------------------------------------------------
def test_obstruction_pure(
    cam_pos: Vector,
    look_pos: Vector,
    obstacles: Optional[List[Dict[str, Any]]] = None
) -> Optional[float]:
    """
    Pure Python raycast collision test against obstacle bounding boxes.
    Returns distance to hit, or None if clear.
    """
    if not obstacles:
        return None

    ray_dir = (cam_pos - look_pos).normalized()
    ray_len = (cam_pos - look_pos).length

    for obs in obstacles:
        bmin = obs.get("min", (-1, -1, -1))
        bmax = obs.get("max", (1, 1, 1))

        # Test AABB intersection along ray
        tmin = 0.0
        tmax = ray_len
        intersected = True
        for i in range(3):
            ro = look_pos[i]
            rd = ray_dir[i]
            if abs(rd) < 1e-6:
                if ro < bmin[i] or ro > bmax[i]:
                    intersected = False
                    break
            else:
                t1 = (bmin[i] - ro) / rd
                t2 = (bmax[i] - ro) / rd
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    intersected = False
                    break

        if intersected and 0.5 < tmin < ray_len:
            return tmin

    return None


def resolve_camera_obstruction(
    cam_pos: Vector,
    look_pos: Vector,
    ray_test_fn=None,
    safe_margin: float = 0.45
) -> Vector:
    """
    Resolves camera obstruction by testing clearance and adjusting elevation, orbit, or distance.
    """
    if ray_test_fn is None:
        return cam_pos

    hit_dist = ray_test_fn(look_pos, cam_pos)
    if hit_dist is None:
        return cam_pos

    # 1. Try vertical lift (looking over low obstacles / counters)
    d = cam_pos - look_pos
    dist = d.length
    for lift in (1.5, 3.0, 5.0):
        q = look_pos + d.normalized() * dist + Vector((0.0, 0.0, lift))
        if ray_test_fn(look_pos, q) is None:
            return q

    # 2. Try azimuthal orbits (orbiting around obstacle)
    for ang_deg in (20.0, -20.0, 35.0, -35.0):
        rad = math.radians(ang_deg)
        dd = Vector((d.x * math.cos(rad) - d.y * math.sin(rad), d.x * math.sin(rad) + d.y * math.cos(rad), d.z))
        q = look_pos + dd
        if ray_test_fn(look_pos, q) is None:
            return q

    # 3. Pull camera forward in front of blocker
    if hit_dist > 1.2:
        return look_pos + (cam_pos - look_pos).normalized() * max(1.0, hit_dist - safe_margin)

    return cam_pos


# ---------------------------------------------------------------------------
# Smooth Camera Motion Trajectories
# ---------------------------------------------------------------------------
def generate_camera_trajectory(
    move_type: str,
    base_cam: Vector,
    base_look: Vector,
    duration: float,
    fps: int = 30,
    track_target_start: Optional[Vector] = None,
    track_target_end: Optional[Vector] = None,
    num_samples: int = 5,
) -> List[Tuple[float, Vector, Vector]]:
    """
    Generates smooth, quintic-eased camera waypoints (time, cam_pos, look_pos) across a shot.
    """
    if duration <= 0:
        return [(0.0, base_cam, base_look)]

    # S-curve waypoints
    samples: List[Tuple[float, Vector, Vector]] = []
    times = [0.0]
    if num_samples > 2:
        step = duration / (num_samples - 1)
        times = [i * step for i in range(num_samples)]
    else:
        times = [0.0, duration]

    cam_dir = (base_cam - base_look).normalized()
    cam_dist = (base_cam - base_look).length
    side_dir = Vector((-cam_dir.y, cam_dir.x, 0.0)).normalized()

    for t in times:
        u = t / duration
        s = quintic_ease(u)

        if move_type in ("push_in", "dolly_in"):
            # Move smoothly closer
            scale = 1.25 - 0.28 * s
            p = base_look + cam_dir * (cam_dist * scale)
            L = base_look.copy()

        elif move_type in ("pull_out", "dolly_out"):
            # Move smoothly farther
            scale = 0.92 + 0.38 * s
            p = base_look + cam_dir * (cam_dist * scale)
            L = base_look.copy()

        elif move_type in ("pan_left", "truck_left"):
            # Lateral move left
            offset = side_dir * (1.8 * (s - 0.5))
            p = base_cam + offset
            L = base_look + offset * 0.3

        elif move_type in ("pan_right", "truck_right"):
            # Lateral move right
            offset = -side_dir * (1.8 * (s - 0.5))
            p = base_cam + offset
            L = base_look + offset * 0.3

        elif move_type in ("tilt_up", "crane_up"):
            # Vertical rise
            lift = Vector((0.0, 0.0, 2.5 * s))
            p = base_cam + lift
            L = base_look + lift * 0.2

        elif move_type in ("tilt_down", "crane_down"):
            # Vertical descent
            lift = Vector((0.0, 0.0, -2.5 * s))
            p = base_cam + lift
            L = base_look + lift * 0.2

        elif move_type in ("orbit_left", "orbit_right"):
            # Smooth azimuthal orbit
            sgn = 1.0 if move_type == "orbit_left" else -1.0
            angle = math.radians(18.0 * (s - 0.5) * sgn)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            od = Vector((cam_dir.x * cos_a - cam_dir.y * sin_a, cam_dir.x * sin_a + cam_dir.y * cos_a, cam_dir.z))
            p = base_look + od * cam_dist
            L = base_look.copy()

        elif move_type == "establishing_pan":
            # Slow, graceful establishing pan
            offset = side_dir * (3.5 * (s - 0.5))
            p = base_cam + offset
            L = base_look + offset * 0.6

        elif move_type in ("track", "follow") and track_target_start and track_target_end:
            # Follow moving actor
            cur_actor = track_target_start.lerp(track_target_end, s)
            offset = cur_actor - track_target_start
            p = base_cam + offset
            L = base_look + offset

        elif move_type == "whip_in":
            # Fast snap in
            whip_s = math.pow(s, 0.35)
            scale = 2.2 - 1.22 * whip_s
            p = base_look + cam_dir * (cam_dist * scale)
            L = base_look.copy()

        elif move_type == "crash_zoom":
            # Hold then rapid zoom punch
            zoom_s = 0.0 if u < 0.4 else quintic_ease((u - 0.4) / 0.6)
            scale = 1.0 - 0.55 * zoom_s
            p = base_look + cam_dir * (cam_dist * scale)
            L = base_look.copy()

        else:
            # static / subtle cinematic drift
            drift = 1.02 - 0.02 * s
            p = base_look + cam_dir * (cam_dist * drift)
            L = base_look.copy()

        samples.append((t, p, L))

    return samples
