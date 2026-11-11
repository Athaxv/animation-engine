"""
Comprehensive Test Suite for Phase 03 Roblox Animation Intelligence & Motion System.

Covers:
1. Motion Blending, Easing Curves, and Angle Interpolation
2. Action Priority Matrix and Interruptibility Rules
3. Analytical R6 Kinematics (Single-Bone Shoulder IK, Head Look-At, Spine Compensation)
4. Locomotion, S-Curve Profiles, and Foot-Planting Stride Synchronization
5. Interaction Planning (Pickup, Drop, Pass, Catch, Handshake, Hug)
6. Multi-Character Choreography Coordination
7. Obstacle-Aware 2D Navigation and Pathfinding
8. Engine Vocabulary, Validation, and Backwards Compatibility

Usage:
    python pipeline/test_motion.py
"""
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
for p in (ROOT, PIPE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pipeline.motion as motion
import pipeline.vocab as vocab

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
    return bool(ok)


def group(title: str):
    print(f"\n{title}")


# ------------------------------------------------------------------ 1. Blending & Easing
def test_blending_and_easing():
    group("1. Motion Blending & Easing Curves")

    # Boundary conditions
    for name in ("linear", "ease_in_quad", "ease_out_quad", "ease_in_out_cubic", "smoothstep"):
        fn = motion.get_easing(name)
        check(f"easing_{name}_boundaries", abs(fn(0.0)) < 1e-6 and abs(fn(1.0) - 1.0) < 1e-6)

    # Monotonicity check on ease_in_out_cubic
    cubic = motion.ease_in_out_cubic
    samples = [cubic(i / 20.0) for i in range(21)]
    monotonic = all(samples[i] <= samples[i + 1] + 1e-6 for i in range(20))
    check("easing_cubic_monotonic", monotonic)

    # Shortest-arc angle unwrapping
    # 170 deg to -170 deg should unwrap across 180 (diff = +20 deg), NOT reverse 340 deg
    unwrapped = motion.unwrap_angle_deg(170.0, -170.0)
    diff = unwrapped - 170.0
    check("angle_unwrap_shortest_arc", abs(diff - 20.0) < 1e-4, f"diff was {diff}")

    # Pose blending
    pose_a = {"upper_arm.R": (0.0, 0.0, 0.0), "root_z": 0.0}
    pose_b = {"upper_arm.R": (-90.0, 0.0, 0.0), "root_z": 1.0}
    mid = motion.blend_poses(pose_a, pose_b, 0.5)
    check("pose_blend_midpoint_bone", abs(mid["upper_arm.R"][0] - (-45.0)) < 1.0)
    check("pose_blend_midpoint_root_z", abs(mid["root_z"] - 0.5) < 1e-3)


# ------------------------------------------------------------------ 2. Priority & Interruptibility
def test_priority_matrix():
    group("2. Action Priority Matrix & Interruptibility")

    # Priority ordering
    p_fall = motion.get_action_priority("fall_back")
    p_hop = motion.get_action_priority("surprise_hop")
    p_pass = motion.get_action_priority("pass_prop")
    p_walk = motion.get_action_priority("walk_to")
    p_wave = motion.get_action_priority("wave")
    p_idle = motion.get_action_priority("idle")

    check("priority_hierarchy", p_fall > p_hop > p_pass > p_walk > p_wave > p_idle)

    # Preemption rules
    check("surprise_can_interrupt_wave", motion.can_interrupt("surprise_hop", "wave"))
    check("wave_cannot_interrupt_surprise", not motion.can_interrupt("wave", "surprise_hop"))
    check("emergency_never_interruptible", not motion.can_interrupt("surprise_hop", "fall_back"))

    # Protected interaction contact phase
    # pass_prop is protected between phase 0.35 and 0.75
    check("interaction_protected_at_contact", not motion.is_interruptible("pass_prop", phase=0.50))
    check("interaction_interruptible_before_contact", motion.is_interruptible("pass_prop", phase=0.10))

    # Recovery generation
    rec = motion.generate_recovery_keyframes(
        {"upper_arm.R": (-90.0, 0.0, 0.0)},
        {"upper_arm.R": (0.0, 0.0, 0.0)},
        start_frame=10,
        duration=6,
    )
    check("recovery_keyframes_count", len(rec) == 7)
    check("recovery_ends_at_base", abs(rec[-1][1]["upper_arm.R"][0]) < 1e-3)


# ------------------------------------------------------------------ 3. Analytical Kinematics
def test_kinematics():
    group("3. Analytical R6 Kinematics")

    # Forward arm FK at rest
    hand_rest = motion.forward_arm_fk((0.0, 0.0, 0.0), side="R")
    check("fk_rest_hand_position", abs(hand_rest[0] - (-1.5)) < 1e-2 and abs(hand_rest[2] - 2.0) < 1e-2)

    # Arm IK pointing straight forward
    # Shoulder R is at (-1.5, 0, 3.5). Target at (-1.5, -1.5, 3.5)
    ik_fwd = motion.solve_arm_ik((-1.5, -1.5, 3.5), side="R")
    rx, ry, rz = ik_fwd["upper_arm.R"]
    check("ik_point_forward_pitch", abs(rx - (-90.0)) < 1.0, f"rx={rx}")
    check("ik_point_forward_reachable", ik_fwd["reachable"])
    check("ik_point_forward_contact_dist", ik_fwd["contact_distance"] < 0.05)

    # Arm IK pointing outward to character's left (+X) for Left Arm
    # Shoulder L is at (+1.5, 0, 3.5). Target at (+3.0, 0, 3.5)
    ik_side = motion.solve_arm_ik((3.0, 0.0, 3.5), side="L")
    check("ik_point_side_reachable", ik_side["reachable"])

    # Spine compensation on low object
    ik_low = motion.solve_arm_ik((-1.2, -1.0, 1.2), side="R", allow_spine_lean=True)
    check("ik_low_spine_lean_applied", ik_low["spine"][0] > 10.0, f"spine={ik_low['spine']}")

    # Head look-at tracking
    head_fwd = motion.solve_look_at((0.0, -4.0, 4.0))
    check("head_look_forward", abs(head_fwd["head"][0]) < 1.0 and abs(head_fwd["head"][1]) < 1.0)

    head_up_left = motion.solve_look_at((2.0, -2.0, 6.0))
    check("head_pitch_up", head_up_left["head"][0] < -10.0)  # Tilt up is X < 0
    check("head_yaw_left", head_up_left["head"][1] > 10.0)   # Turn left is Y > 0

    # Mutual facing
    h_a, h_b = motion.solve_mutual_facing((0.0, 0.0, 0.0), (0.0, -5.0, 0.0))
    check("mutual_facing_opposite", abs((h_a - h_b) % 360.0 - 180.0) < 1.0)

    # Coordinate transform round-trip
    world_p = (5.0, 12.0, 3.0)
    root_p = (2.0, 8.0, 0.0)
    root_h = 45.0
    local_p = motion.world_to_local_point(world_p, root_p, root_h)
    reconstructed_w = motion.local_to_world_point(local_p, root_p, root_h)
    rt_err = math.hypot(world_p[0] - reconstructed_w[0], world_p[1] - reconstructed_w[1])
    check("coord_transform_roundtrip", rt_err < 0.01, f"err={rt_err}")


# ------------------------------------------------------------------ 4. Locomotion & Foot Planting
def test_locomotion():
    group("4. R6 Locomotion & Foot Planting")

    # Stride frequency adaptation
    gait_walk = motion.calculate_optimal_gait(6.0, fps=30)
    gait_run = motion.calculate_optimal_gait(14.0, fps=30)
    check("gait_walk_identified", gait_walk["gait"] == "walk")
    check("gait_run_identified", gait_run["gait"] == "run")
    check("run_period_faster_than_walk", gait_run["period"] < gait_walk["period"] or gait_run["stride_length"] > gait_walk["stride_length"])

    # S-curve acceleration profile
    traj = motion.generate_scurve_trajectory(frames=12, dist=10.0, acc_frames=4, dec_frames=4)
    check("scurve_endpoints", traj[0] == 0.0 and abs(traj[-1] - 10.0) < 1e-4)
    check("scurve_monotonically_advances", all(traj[i] <= traj[i + 1] for i in range(len(traj) - 1)))

    # Turning with anticipation
    turns = motion.calculate_turn_telemetry(0.0, 90.0, dur_frames=6)
    check("turn_frames_count", len(turns) == 7)
    check("turn_final_heading", abs(turns[-1]["heading"] - 90.0) < 1.0)
    check("turn_anticipation_head_leads", any(t["head_yaw"] != 0.0 for t in turns[:3]))

    # Foot sliding metric
    zero_slide = motion.measure_foot_sliding((0, 0, 0), (0, -4.52, 0), frames=24, period=12, stride_length=2.26)
    check("foot_sliding_zero_drift", zero_slide < 0.05, f"drift={zero_slide}")


# ------------------------------------------------------------------ 5. Interactions & Choreography
def test_interactions_and_choreography():
    group("5. Interaction & Choreography Planning")

    # Pickup planning
    pk = motion.plan_pickup_keyframes((0, 0, 0), 0.0, (-1.3, -1.0, 2.5), start_frame=1, dur=18)
    check("pickup_contact_frame", pk["contact_frame"] == 8)
    check("pickup_reachable", pk["reachable"])

    # Pass and catch planning
    pc = motion.plan_pass_and_catch_keyframes((0, 0, 0), 0.0, (0, -2.6, 0), 180.0, start_frame=10, dur=24)
    check("pass_contact_frame", pc["contact_frame"] == 20)
    check("pass_both_actors_reachable", pc["giver_reachable"] and pc["receiver_reachable"])

    # Handshake planning
    hs = motion.plan_handshake_keyframes((0, 0, 0), 0.0, (0, -2.8, 0), 180.0, start_frame=5, dur=24)
    check("handshake_shakes_generated", len(hs["shakes"]) >= 3)

    # Hug planning
    hg = motion.plan_hug_keyframes((0, 0, 0), 0.0, (0, -1.9, 0), 180.0, start_frame=1, dur=32)
    check("hug_embrace_and_release", hg["embrace_frame"] < hg["release_frame"])

    # Approach and greet
    ag = motion.plan_approach_and_greet((0, 0, 0), (0, 8.0, 0), start_frame=1, dur=40)
    check("approach_actor_a_stops_before_b", ag["actor_a"]["walk_to"][1] < 8.0)
    check("approach_actor_b_turns", ag["actor_b"]["turn_start_frame"] > 1)

    # Group celebration phase offsets
    gc = motion.plan_group_celebration(["Aiko", "Zephyr", "Theo"], start_frame=10, dur=30)
    check("group_celebration_actors_present", len(gc) == 3)
    check("group_celebration_has_actions", all(c["action"] == "celebrate" for c in gc.values()))


# ------------------------------------------------------------------ 6. Navigation & Environment
def test_navigation():
    group("6. Obstacle-Aware 2D Navigation")

    # Segment box intersection
    box = (-4.0, 3.0, 4.0, 11.0)  # Fountain-like box
    check("segment_box_hits_center", motion.segment_intersects_box((0.0, 0.0), (0.0, 15.0), box))
    check("segment_box_misses_side", not motion.segment_intersects_box((10.0, 0.0), (10.0, 15.0), box))

    # Pathfinding around obstacle
    obs = [{"id": "fountain", "bounds_2d": [-4.0, 3.0, 4.0, 11.0]}]
    start = (-8.0, 7.0)
    goal = (8.0, 7.0)
    check("direct_path_blocked", not motion.line_of_sight(start, goal, obs))

    path = motion.find_path(start, goal, obs)
    check("path_found_around_obstacle", len(path) > 2, f"path={path}")
    check("path_waypoints_clear", all(
        motion.line_of_sight(path[i], path[i + 1], obs) for i in range(len(path) - 1)
    ))

    # Multi-waypoint locomotion timing
    wp_plan = motion.plan_multi_waypoint_locomotion(path, speed=6.0, fps=30)
    check("multi_waypoint_timing_positive", wp_plan["total_frames"] > 0)
    check("multi_waypoint_segments_match", len(wp_plan["segments"]) == len(path) - 1)


# ------------------------------------------------------------------ 7. Vocabulary & Compatibility
def test_vocabulary_and_compatibility():
    group("7. Vocabulary & Backwards Compatibility")

    # Poses presence
    expected_new_poses = {"reach_forward", "receive_prop", "embrace", "handshake", "push", "pickup"}
    check("vocab_contains_new_poses", expected_new_poses.issubset(set(vocab.POSES)))

    # Actions presence
    expected_new_actions = {"handshake", "hug", "pickup", "drop", "pass_prop", "catch_prop", "approach", "push_prop"}
    check("vocab_contains_new_actions", expected_new_actions.issubset(set(vocab.ACTIONS.keys())))

    # Preexisting core actions remain untouched
    legacy_actions = {"idle", "walk_to", "run_to", "jump", "celebrate", "surprise_hop", "wave", "nod"}
    check("vocab_preserves_legacy_actions", legacy_actions.issubset(set(vocab.ACTIONS.keys())))


def main():
    print("=" * 60)
    print("PHASE 03 ROBLOX ANIMATION & MOTION TEST SUITE")
    print("=" * 60)

    test_blending_and_easing()
    test_priority_matrix()
    test_kinematics()
    test_locomotion()
    test_interactions_and_choreography()
    test_navigation()
    test_vocabulary_and_compatibility()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print("\n" + "=" * 60)
    print(f"MOTION TEST RESULTS: {passed}/{total} checks passed.")
    print("=" * 60)

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
