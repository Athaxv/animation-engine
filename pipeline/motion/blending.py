"""
Motion Blending, Easing, and Priority Subsystem for R6 Roblox Animations.

Provides:
- Parametric easing functions (quad, cubic, sine, back, bounce, smoothstep)
- Shortest-arc Euler angle unwrapping & spherical interpolation
- Full R6 pose blending (bones + root displacement)
- Action Priority Matrix (EMERGENCY > REACTION > INTERACTION > LOCOMOTION > GESTURE > IDLE)
- Interruptibility rules and contact-phase protection
- Recovery phase keyframe generation
"""
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ------------------------------------------------------------------ Easing Functions
def linear(t: float) -> float:
    return max(0.0, min(1.0, float(t)))


def ease_in_quad(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * t


def ease_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * (2.0 - t)


def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 2.0 * t * t if t < 0.5 else -1.0 + (4.0 - 2.0 * t) * t


def ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * t * t


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    t -= 1.0
    return t * t * t + 1.0


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    if t < 0.5:
        return 4.0 * t * t * t
    p = 2.0 * t - 2.0
    return 0.5 * p * p * p + 1.0


def ease_in_sine(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - math.cos(t * math.pi * 0.5)


def ease_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return math.sin(t * math.pi * 0.5)


def ease_in_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 0.5 * (1.0 - math.cos(math.pi * t))


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(t: float, s: float = 1.70158) -> float:
    """Overshoot easing: extends slightly past 1.0 before settling."""
    t = max(0.0, min(1.0, float(t)))
    t -= 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


def ease_in_back(t: float, s: float = 1.70158) -> float:
    """Anticipation easing: pulls slightly back before advancing."""
    t = max(0.0, min(1.0, float(t)))
    return t * t * ((s + 1.0) * t - s)


def ease_out_bounce(t: float) -> float:
    """Simulates physical impact bounce on landing."""
    t = max(0.0, min(1.0, float(t)))
    if t < (1.0 / 2.75):
        return 7.5625 * t * t
    elif t < (2.0 / 2.75):
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < (2.5 / 2.75):
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


EASING_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    "linear": linear,
    "ease_in_quad": ease_in_quad,
    "ease_out_quad": ease_out_quad,
    "ease_in_out_quad": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_sine": ease_in_sine,
    "ease_out_sine": ease_out_sine,
    "ease_in_out_sine": ease_in_out_sine,
    "smoothstep": smoothstep,
    "ease_out_back": ease_out_back,
    "ease_in_back": ease_in_back,
    "ease_out_bounce": ease_out_bounce,
}


def get_easing(name_or_fn: Union[str, Callable[[float], float]]) -> Callable[[float], float]:
    if callable(name_or_fn):
        return name_or_fn
    return EASING_FUNCTIONS.get(str(name_or_fn).lower(), ease_in_out_cubic)


# ------------------------------------------------------------------ Angle & Pose Interpolation
def unwrap_angle_deg(a: float, b: float) -> float:
    """
    Unwraps angle `b` relative to `a` (in degrees) to ensure the shortest arc interpolation.
    Prevents 360-degree unnatural spins.
    """
    delta = (b - a) % 360.0
    if delta > 180.0:
        delta -= 360.0
    return a + delta


def unwrap_angle_rad(a: float, b: float) -> float:
    """Unwraps angle `b` relative to `a` (in radians) for shortest arc."""
    delta = (b - a) % (2.0 * math.pi)
    if delta > math.pi:
        delta -= 2.0 * math.pi
    return a + delta


def lerp_angles_deg(
    euler_a: Tuple[float, float, float],
    euler_b: Tuple[float, float, float],
    t: float,
) -> Tuple[float, float, float]:
    """Component-wise shortest-arc linear interpolation of XYZ Euler angles (degrees)."""
    return (
        round(unwrap_angle_deg(euler_a[0], euler_b[0]) * t + euler_a[0] * (1.0 - t), 3),
        round(unwrap_angle_deg(euler_a[1], euler_b[1]) * t + euler_a[1] * (1.0 - t), 3),
        round(unwrap_angle_deg(euler_a[2], euler_b[2]) * t + euler_a[2] * (1.0 - t), 3),
    )


def blend_poses(
    pose_a: Dict[str, Any],
    pose_b: Dict[str, Any],
    t: float,
    easing: Union[str, Callable[[float], float]] = "ease_in_out_cubic",
) -> Dict[str, Any]:
    """
    Blends two R6 pose dictionaries across all bones and special keys (root_z, root_rx, root_ry).
    `t` ranges from 0.0 (100% pose_a) to 1.0 (100% pose_b).
    """
    fn = get_easing(easing)
    w = fn(t)

    all_keys = set(pose_a.keys()).union(pose_b.keys())
    blended: Dict[str, Any] = {}

    for k in all_keys:
        val_a = pose_a.get(k, 0.0 if k.startswith("root_") else (0.0, 0.0, 0.0))
        val_b = pose_b.get(k, 0.0 if k.startswith("root_") else (0.0, 0.0, 0.0))

        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            # Float scalar (e.g. root_z, root_rx, root_ry)
            if "rx" in k or "ry" in k:
                target_b = unwrap_angle_deg(float(val_a), float(val_b))
                blended[k] = round(float(val_a) * (1.0 - w) + target_b * w, 3)
            else:
                blended[k] = round(float(val_a) * (1.0 - w) + float(val_b) * w, 3)
        elif isinstance(val_a, (tuple, list)) and isinstance(val_b, (tuple, list)):
            ea = (float(val_a[0]), float(val_a[1]), float(val_a[2]))
            eb = (float(val_b[0]), float(val_b[1]), float(val_b[2]))
            blended[k] = lerp_angles_deg(ea, eb, w)

    return blended


# ------------------------------------------------------------------ Action Priority Matrix
PRIORITY_EMERGENCY = 100
PRIORITY_REACTION = 75
PRIORITY_INTERACTION = 60
PRIORITY_LOCOMOTION = 50
PRIORITY_GESTURE = 25
PRIORITY_IDLE = 0

ACTION_PRIORITIES: Dict[str, int] = {
    # Emergency / non-interruptible cutscene actions
    "fall_back": PRIORITY_EMERGENCY,
    "poof": PRIORITY_EMERGENCY,
    "pop_in": PRIORITY_EMERGENCY,
    # Reactions
    "surprise_hop": PRIORITY_REACTION,
    "jump": PRIORITY_REACTION,
    "shiver": PRIORITY_REACTION,
    "flinch": PRIORITY_REACTION,
    # Interactions
    "pickup": PRIORITY_INTERACTION,
    "pickup_object": PRIORITY_INTERACTION,
    "drop": PRIORITY_INTERACTION,
    "drop_object": PRIORITY_INTERACTION,
    "pass_prop": PRIORITY_INTERACTION,
    "catch_prop": PRIORITY_INTERACTION,
    "handshake": PRIORITY_INTERACTION,
    "hug": PRIORITY_INTERACTION,
    "open_door": PRIORITY_INTERACTION,
    "push_prop": PRIORITY_INTERACTION,
    "pull_prop": PRIORITY_INTERACTION,
    # Locomotion
    "walk_to": PRIORITY_LOCOMOTION,
    "run_to": PRIORITY_LOCOMOTION,
    "walk_in": PRIORITY_LOCOMOTION,
    "walk_out": PRIORITY_LOCOMOTION,
    "run_out": PRIORITY_LOCOMOTION,
    "turn": PRIORITY_LOCOMOTION,
    "approach": PRIORITY_LOCOMOTION,
    # Gestures / Expressive loops
    "wave": PRIORITY_GESTURE,
    "nod": PRIORITY_GESTURE,
    "shake_head": PRIORITY_GESTURE,
    "look_around": PRIORITY_GESTURE,
    "laugh": PRIORITY_GESTURE,
    "cry": PRIORITY_GESTURE,
    "celebrate": PRIORITY_GESTURE,
    "gestures": PRIORITY_GESTURE,
    "talk": PRIORITY_GESTURE,
    "talk_still": PRIORITY_GESTURE,
    "dance": PRIORITY_GESTURE,
    "spin": PRIORITY_GESTURE,
    "float": PRIORITY_GESTURE,
    # Idle
    "idle": PRIORITY_IDLE,
    "sit_down": PRIORITY_IDLE,
    "stand_up": PRIORITY_IDLE,
    "sleep": PRIORITY_IDLE,
}

# Critical phases during which interactions CANNOT be interrupted (e.g. holding prop during pass)
CONTACT_PROTECTED_ACTIONS = {
    "pickup": (0.35, 0.70),
    "pickup_object": (0.35, 0.70),
    "pass_prop": (0.35, 0.75),
    "catch_prop": (0.35, 0.75),
    "handshake": (0.25, 0.75),
    "hug": (0.20, 0.80),
}


def get_action_priority(action_name: str) -> int:
    """Returns the integer priority for an action (0 to 100)."""
    return ACTION_PRIORITIES.get(action_name, PRIORITY_GESTURE)


def is_interruptible(action_name: str, phase: float = 0.0) -> bool:
    """
    Determines if an action can be interrupted at normalized time `phase` in [0.0, 1.0].
    Emergency actions are never interruptible. Interaction contact phases are protected.
    """
    pri = get_action_priority(action_name)
    if pri >= PRIORITY_EMERGENCY:
        return False

    if action_name in CONTACT_PROTECTED_ACTIONS:
        p_start, p_end = CONTACT_PROTECTED_ACTIONS[action_name]
        if p_start <= phase <= p_end:
            return False

    return True


def can_interrupt(incoming_action: str, current_action: str, current_phase: float = 0.0) -> bool:
    """
    Evaluates whether an incoming action can preempt the currently executing action.
    Rules:
    1. If current action is in a non-interruptible phase, return False.
    2. Incoming action priority must be strictly greater than current action priority.
    """
    if not is_interruptible(current_action, current_phase):
        return False

    p_in = get_action_priority(incoming_action)
    p_cur = get_action_priority(current_action)
    return p_in > p_cur


# ------------------------------------------------------------------ Recovery Phases
DEFAULT_TRANSITION_DURATIONS: Dict[Tuple[str, str], int] = {
    ("run_to", "idle"): 6,
    ("walk_to", "idle"): 5,
    ("surprise_hop", "idle"): 4,
    ("jump", "idle"): 6,
    ("celebrate", "idle"): 6,
    ("fall_back", "stand_up"): 10,
    ("wave", "idle"): 4,
    ("pickup", "idle"): 5,
    ("handshake", "idle"): 5,
    ("hug", "idle"): 6,
}


def get_transition_duration(from_action: str, to_action: str, default: int = 5) -> int:
    """Returns recommended transition duration in frames at 30 fps."""
    if (from_action, to_action) in DEFAULT_TRANSITION_DURATIONS:
        return DEFAULT_TRANSITION_DURATIONS[(from_action, to_action)]
    if (from_action, "idle") in DEFAULT_TRANSITION_DURATIONS and to_action in ("idle", "stand", "relaxed"):
        return DEFAULT_TRANSITION_DURATIONS[(from_action, "idle")]
    return default


def generate_recovery_keyframes(
    from_pose: Dict[str, Any],
    base_pose: Dict[str, Any],
    start_frame: int,
    duration: int = 6,
    easing: str = "ease_out_quad",
) -> List[Tuple[int, Dict[str, Any]]]:
    """
    Generates a sequence of (frame, pose_dict) tuples restoring the rig from `from_pose`
    to `base_pose` over `duration` frames with smooth deceleration.
    """
    keyframes = []
    duration = max(2, duration)
    for step in range(duration + 1):
        t = step / float(duration)
        f = start_frame + step
        blended = blend_poses(from_pose, base_pose, t, easing=easing)
        keyframes.append((f, blended))
    return keyframes
