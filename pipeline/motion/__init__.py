"""
Roblox R6 Animation Intelligence & Motion System (Phase 03).

Provides:
- Blending, Easing Curves, and Action Priority Resolution
- Analytical Single-Bone R6 Kinematics (Shoulder Aiming, Look-At)
- Natural Locomotion with S-Curve Acceleration and Stride Synchronization
- Coordinated Prop Interactions (Pickup, Pass, Catch, Drop)
- Character-to-Character Choreography (Handshakes, Hugs, Approach & Greet)
- Obstacle-Aware Waypoint Pathfinding (Phase 01 Environment Integration)
"""

__version__ = "3.0.0"

from pipeline.motion.blending import (
    ACTION_PRIORITIES,
    blend_poses,
    can_interrupt,
    ease_in_out_cubic,
    ease_in_quad,
    ease_out_back,
    ease_out_bounce,
    ease_out_cubic,
    ease_out_quad,
    generate_recovery_keyframes,
    get_action_priority,
    get_easing,
    get_transition_duration,
    is_interruptible,
    lerp_angles_deg,
    linear,
    smoothstep,
    unwrap_angle_deg,
    unwrap_angle_rad,
)
from pipeline.motion.choreography import (
    plan_approach_and_greet,
    plan_group_celebration,
    plan_point_and_react,
)
from pipeline.motion.interactions import (
    plan_handshake_keyframes,
    plan_hug_keyframes,
    plan_pass_and_catch_keyframes,
    plan_pickup_keyframes,
)
from pipeline.motion.kinematics import (
    ARM_LENGTH,
    GRIP_REACH,
    LEG_LENGTH,
    forward_arm_fk,
    local_to_world_point,
    solve_arm_ik,
    solve_look_at,
    solve_mutual_facing,
    world_to_local_point,
)
from pipeline.motion.locomotion import (
    calculate_optimal_gait,
    calculate_turn_telemetry,
    generate_scurve_trajectory,
    measure_foot_sliding,
)
from pipeline.motion.navigation import (
    find_path,
    line_of_sight,
    plan_multi_waypoint_locomotion,
    segment_intersects_box,
)

__all__ = [
    "__version__",
    "linear",
    "ease_in_quad",
    "ease_out_quad",
    "ease_out_cubic",
    "ease_in_out_cubic",
    "smoothstep",
    "ease_out_back",
    "ease_out_bounce",
    "get_easing",
    "unwrap_angle_deg",
    "unwrap_angle_rad",
    "lerp_angles_deg",
    "blend_poses",
    "get_action_priority",
    "is_interruptible",
    "can_interrupt",
    "get_transition_duration",
    "generate_recovery_keyframes",
    "ACTION_PRIORITIES",
    "ARM_LENGTH",
    "GRIP_REACH",
    "LEG_LENGTH",
    "forward_arm_fk",
    "solve_arm_ik",
    "solve_look_at",
    "solve_mutual_facing",
    "world_to_local_point",
    "local_to_world_point",
    "calculate_optimal_gait",
    "generate_scurve_trajectory",
    "calculate_turn_telemetry",
    "measure_foot_sliding",
    "plan_pickup_keyframes",
    "plan_pass_and_catch_keyframes",
    "plan_handshake_keyframes",
    "plan_hug_keyframes",
    "plan_approach_and_greet",
    "plan_point_and_react",
    "plan_group_celebration",
    "segment_intersects_box",
    "line_of_sight",
    "find_path",
    "plan_multi_waypoint_locomotion",
]
