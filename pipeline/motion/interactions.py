"""
R6 Interaction, Contact, and Dynamic Prop Choreography Subsystem.

Provides:
- Dynamic prop state machine & seamless handoff via animated ChildOf constraints
- Coordinated physical actions:
  * pickup_object (bend waist, reach arm, snap prop, lift to hold)
  * drop_object (release prop with gravity drop and bounce)
  * pass_and_catch (synchronized giver-to-receiver handoff with eye tracking)
  * handshake (mutual arm extension, 3-cycle shake rhythm, release)
  * hug (mutual approach, arm wrap, hold, release)
  * open_door (reach handle, hinge rotation, step through)
  * push_pull_prop (hand contact, torso lean, synchronous prop translation)
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from pipeline.motion.blending import blend_poses, ease_in_out_cubic, ease_out_bounce, ease_out_quad
from pipeline.motion.kinematics import (
    ARM_LENGTH,
    GRIP_REACH,
    SHOULDER_L,
    SHOULDER_R,
    local_to_world_point,
    solve_arm_ik,
    solve_look_at,
    solve_mutual_facing,
    world_to_local_point,
)

try:
    import bpy
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False


def plan_pickup_keyframes(
    char_pos: Tuple[float, float, float],
    char_heading_deg: float,
    prop_world_pos: Tuple[float, float, float],
    start_frame: int,
    dur: int = 18,
    side: str = "R",
) -> Dict[str, Any]:
    """
    Computes keyframe schedule and bone transforms for picking up an object from the world.
    Returns:
      {
        "contact_frame": int,
        "end_frame": int,
        "reachable": bool,
        "keyframes": list of (frame, pose_dict)
      }
    """
    f0 = start_frame
    f_contact = f0 + int(dur * 0.4)
    f_lift = f0 + int(dur * 0.75)
    f_end = f0 + dur

    prop_local = world_to_local_point(prop_world_pos, char_pos, char_heading_deg)
    ik_reach = solve_arm_ik(prop_local, side=side, allow_spine_lean=True)
    look_reach = solve_look_at(prop_local)

    arm_bone = f"upper_arm.{side.upper()}"
    reach_pose = {
        arm_bone: ik_reach[arm_bone],
        "spine": ik_reach["spine"],
        "head": look_reach["head"],
    }

    # Lift pose: prop raised to chest/belly height
    hold_arm = (-50.0, -20.0 if side.upper() == "R" else 20.0, 0.0)
    lift_pose = {
        arm_bone: hold_arm,
        "spine": (0.0, 0.0, 0.0),
        "head": (-8.0, 0.0, 0.0),
    }

    settle_pose = {
        "upper_arm.L": (-50.0, 20.0, 0.0),
        "upper_arm.R": (-50.0, -20.0, 0.0),
        "spine": (0.0, 0.0, 0.0),
        "head": (0.0, 0.0, 0.0),
    }

    return {
        "start_frame": f0,
        "contact_frame": f_contact,
        "lift_frame": f_lift,
        "end_frame": f_end,
        "reachable": ik_reach["reachable"],
        "contact_distance": ik_reach["contact_distance"],
        "reach_pose": reach_pose,
        "lift_pose": lift_pose,
        "settle_pose": settle_pose,
    }


def plan_pass_and_catch_keyframes(
    giver_pos: Tuple[float, float, float],
    giver_heading_deg: float,
    receiver_pos: Tuple[float, float, float],
    receiver_heading_deg: float,
    start_frame: int,
    dur: int = 24,
    giver_hand: str = "R",
    receiver_hand: str = "L",
) -> Dict[str, Any]:
    """
    Computes synchronized interaction timeline for Giver passing a prop to Receiver.
    Finds optimal mutual midpoint, reach poses, and handoff contact frame.
    By default, Giver passes with Right hand and Receiver receives with Left hand,
    creating a natural facing contact corridor.
    """
    f0 = start_frame
    f_contact = f0 + int(dur * 0.42)
    f_end = f0 + dur

    g_pivot = SHOULDER_R if giver_hand == "R" else SHOULDER_L
    r_pivot = SHOULDER_L if receiver_hand == "L" else SHOULDER_R

    sg = local_to_world_point(g_pivot, giver_pos, giver_heading_deg)
    sr = local_to_world_point(r_pivot, receiver_pos, receiver_heading_deg)

    # Mutual midpoint between reaching shoulders at chest height (~2.9 studs)
    mid_world = (
        (sg[0] + sr[0]) * 0.5,
        (sg[1] + sr[1]) * 0.5,
        2.9,
    )

    # Convert midpoint to local coordinates of both characters
    mid_local_giver = world_to_local_point(mid_world, giver_pos, giver_heading_deg)
    mid_local_recv = world_to_local_point(mid_world, receiver_pos, receiver_heading_deg)

    giver_ik = solve_arm_ik(mid_local_giver, side=giver_hand, allow_spine_lean=True)
    recv_ik = solve_arm_ik(mid_local_recv, side=receiver_hand, allow_spine_lean=True)

    giver_look = solve_look_at(mid_local_giver)
    recv_look = solve_look_at(mid_local_recv)

    giver_reach_pose = {
        f"upper_arm.{giver_hand}": giver_ik[f"upper_arm.{giver_hand}"],
        "spine": giver_ik["spine"],
        "head": giver_look["head"],
    }
    recv_reach_pose = {
        f"upper_arm.{receiver_hand}": recv_ik[f"upper_arm.{receiver_hand}"],
        "spine": recv_ik["spine"],
        "head": recv_look["head"],
    }
    # Complementary arm framing
    if receiver_hand == "L":
        recv_reach_pose["upper_arm.R"] = (-35.0, -15.0, 0.0)

    giver_settle = {
        "upper_arm.R": (0.0, 0.0, 3.0),
        "upper_arm.L": (0.0, 0.0, -3.0),
        "spine": (0.0, 0.0, 0.0),
        "head": (0.0, 0.0, 0.0),
    }
    recv_settle = {
        "upper_arm.L": (-50.0, 20.0, 0.0),
        "upper_arm.R": (-50.0, -20.0, 0.0),
        "spine": (0.0, 0.0, 0.0),
        "head": (0.0, 0.0, 0.0),
    }

    return {
        "start_frame": f0,
        "contact_frame": f_contact,
        "end_frame": f_end,
        "midpoint_world": mid_world,
        "giver_reachable": giver_ik["reachable"],
        "receiver_reachable": recv_ik["reachable"],
        "giver_reach_pose": giver_reach_pose,
        "receiver_reach_pose": recv_reach_pose,
        "giver_settle_pose": giver_settle,
        "receiver_settle_pose": recv_settle,
    }


def plan_handshake_keyframes(
    pos_a: Tuple[float, float, float],
    heading_a: float,
    pos_b: Tuple[float, float, float],
    heading_b: float,
    start_frame: int,
    dur: int = 24,
) -> Dict[str, Any]:
    """
    Computes keyframe schedule and rhythmic bone shakes for two characters shaking hands.
    """
    f0 = start_frame
    f_reach = f0 + 6
    f_end = f0 + dur

    mid_world = (
        (pos_a[0] + pos_b[0]) * 0.5,
        (pos_a[1] + pos_b[1]) * 0.5,
        (pos_a[2] + pos_b[2]) * 0.5 + 2.8,
    )

    ik_a = solve_arm_ik(world_to_local_point(mid_world, pos_a, heading_a), side="R")
    ik_b = solve_arm_ik(world_to_local_point(mid_world, pos_b, heading_b), side="R")

    base_rot_a = ik_a["upper_arm.R"]
    base_rot_b = ik_b["upper_arm.R"]

    shakes = []
    # 3 cycles of shake between f_reach and f_end - 4
    shake_dur = f_end - 4 - f_reach
    shake_steps = max(3, shake_dur // 4)
    for i in range(shake_steps):
        f = f_reach + i * 4
        d = 4.0 if i % 2 == 0 else -4.0
        pose_a = {"upper_arm.R": (base_rot_a[0] + d, base_rot_a[1], base_rot_a[2])}
        pose_b = {"upper_arm.R": (base_rot_b[0] + d, base_rot_b[1], base_rot_b[2])}
        shakes.append((f, pose_a, pose_b))

    return {
        "start_frame": f0,
        "reach_frame": f_reach,
        "end_frame": f_end,
        "shakes": shakes,
        "base_pose_a": {"upper_arm.R": base_rot_a, "spine": (0.0, 0.0, 0.0)},
        "base_pose_b": {"upper_arm.R": base_rot_b, "spine": (0.0, 0.0, 0.0)},
    }


def plan_hug_keyframes(
    pos_a: Tuple[float, float, float],
    heading_a: float,
    pos_b: Tuple[float, float, float],
    heading_b: float,
    start_frame: int,
    dur: int = 32,
) -> Dict[str, Any]:
    """
    Computes keyframe schedule for a coordinated two-character hug.
    """
    f0 = start_frame
    f_embrace = f0 + 8
    f_hold_end = f0 + dur - 8
    f_end = f0 + dur

    # Arms wrap around partner torso:
    # Character A wraps high, Character B wraps mid
    hug_pose_a = {
        "upper_arm.L": (-75.0, 42.0, -10.0),
        "upper_arm.R": (-75.0, -42.0, 10.0),
        "spine": (6.0, 0.0, 0.0),
        "head": (12.0, -15.0, 0.0),
    }
    hug_pose_b = {
        "upper_arm.L": (-65.0, 45.0, -8.0),
        "upper_arm.R": (-65.0, -45.0, 8.0),
        "spine": (6.0, 0.0, 0.0),
        "head": (12.0, 15.0, 0.0),
    }

    return {
        "start_frame": f0,
        "embrace_frame": f_embrace,
        "release_frame": f_hold_end,
        "end_frame": f_end,
        "hug_pose_a": hug_pose_a,
        "hug_pose_b": hug_pose_b,
    }


# ------------------------------------------------------------------ Blender Integration
if HAVE_BPY:
    def setup_prop_child_of(
        prop_obj: bpy.types.Object,
        rig: bpy.types.Object,
        bone_name: str,
        active_from_frame: int,
        active_to_frame: Optional[int] = None,
    ) -> bpy.types.Constraint:
        """
        Creates and keyframes a ChildOf constraint on `prop_obj` targeting `rig[bone_name]`.
        Calculates exact inverse matrix to prevent position jumps.
        """
        bpy.context.view_layer.update()
        con_name = f"ChildOf_{rig.name}_{bone_name}"
        con = prop_obj.constraints.get(con_name) or prop_obj.constraints.new('CHILD_OF')
        con.name = con_name
        con.target = rig
        con.subtarget = bone_name

        # Calculate inverse matrix in current evaluated pose
        pb = rig.pose.bones.get(bone_name)
        if pb:
            bone_mw = rig.matrix_world @ pb.matrix
            con.inverse_matrix = bone_mw.inverted() @ prop_obj.matrix_world

        # Keyframe influence
        con.influence = 0.0
        con.keyframe_insert("influence", frame=max(1, active_from_frame - 1))
        con.influence = 1.0
        con.keyframe_insert("influence", frame=active_from_frame)

        if active_to_frame is not None:
            con.influence = 1.0
            con.keyframe_insert("influence", frame=active_to_frame - 1)
            con.influence = 0.0
            con.keyframe_insert("influence", frame=active_to_frame)

        return con
