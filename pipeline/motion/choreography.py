"""
Multi-Character Choreography and Synchronization Coordinator.

Provides declarative coordination for multi-actor storytelling sequences:
- pass_prop: Giver hands prop to Receiver with synchronized contact and eye-contact
- handshake: Mutual reach, clasp, 3-cycle shake rhythm, friendly release
- hug: Mutual approach to 1.8 studs, wrap embrace, hold, release
- approach_and_greet: Actor A approaches Actor B, B turns to face A, A waves, B nods
- point_and_react: Actor A points at prop/target, Actor B tracks gaze, reacts (surprise/laugh)
- group_celebrate: Phase-offset celebratory jumps, gestures and expressions across multiple actors
"""
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from pipeline.motion.interactions import (
    plan_handshake_keyframes,
    plan_hug_keyframes,
    plan_pass_and_catch_keyframes,
    plan_pickup_keyframes,
)
from pipeline.motion.kinematics import solve_mutual_facing


def plan_approach_and_greet(
    pos_a: Tuple[float, float, float],
    pos_b: Tuple[float, float, float],
    start_frame: int,
    dur: int = 40,
    fps: int = 30,
) -> Dict[str, Any]:
    """
    Coordinates Actor A approaching Actor B:
    - Actor A walks from pos_a toward pos_b (stopping at distance ~2.5 studs)
    - Actor B notices A and turns to face A at mid-walk
    - Upon arrival, Actor A waves
    - Actor B smiles and nods
    """
    f0 = start_frame
    dx = pos_b[0] - pos_a[0]
    dy = pos_b[1] - pos_a[1]
    dist = math.sqrt(dx * dx + dy * dy)

    # Stop 2.5 studs away from B
    target_dist = max(0.5, dist - 2.5)
    frac = target_dist / max(1e-3, dist)
    arrive_pos = (
        round(pos_a[0] + dx * frac, 3),
        round(pos_a[1] + dy * frac, 3),
        pos_a[2],
    )

    heading_a, heading_b = solve_mutual_facing(arrive_pos, pos_b)

    # Walk duration based on distance
    walk_frames = max(10, min(dur - 15, int(round((target_dist / 6.0) * fps))))
    f_arrive = f0 + walk_frames
    f_turn_b = f0 + max(2, walk_frames // 2)

    return {
        "start_frame": f0,
        "arrive_frame": f_arrive,
        "end_frame": f0 + dur,
        "actor_a": {
            "walk_to": arrive_pos,
            "walk_frames": walk_frames,
            "final_heading": heading_a,
            "arrive_action": "wave",
            "arrive_face": "smile",
        },
        "actor_b": {
            "turn_start_frame": f_turn_b,
            "target_heading": heading_b,
            "react_frame": f_arrive + 2,
            "react_action": "nod",
            "react_face": "smile",
        },
    }


def plan_point_and_react(
    pos_a: Tuple[float, float, float],
    heading_a: float,
    pos_b: Tuple[float, float, float],
    heading_b: float,
    target_pos: Tuple[float, float, float],
    start_frame: int,
    dur: int = 30,
    reaction: str = "surprise_hop",
) -> Dict[str, Any]:
    """
    Coordinates Actor A pointing at a target, Actor B looking at it and reacting.
    """
    f0 = start_frame
    f_point = f0 + 4
    f_look = f0 + 8
    f_react = f0 + 14

    return {
        "start_frame": f0,
        "end_frame": f0 + dur,
        "actor_a": {
            "point_frame": f_point,
            "pose": "point",
            "face": "confident",
        },
        "actor_b": {
            "look_frame": f_look,
            "react_frame": f_react,
            "action": reaction,
            "face": "shocked" if reaction == "surprise_hop" else "laugh",
        },
    }


def plan_group_celebration(
    actor_names: List[str],
    start_frame: int,
    dur: int = 40,
    seed: int = 42,
) -> Dict[str, Dict[str, Any]]:
    """
    Plans phase-offset celebration routines across a group of actors:
    Varies hop timing, jump heights, arm positions, and expressions
    so actors do not look like synchronized automatons.
    """
    rnd = random.Random(seed)
    plan: Dict[str, Dict[str, Any]] = {}

    for i, name in enumerate(actor_names):
        phase_offset = rnd.randint(0, 6)
        hop_count = rnd.choice([1, 2, 2])
        face = rnd.choice(["laugh", "grin", "smile"])
        arm_style = rnd.choice(["celebrate", "arms_up", "hand_up"])

        plan[name] = {
            "start_frame": start_frame + phase_offset,
            "end_frame": start_frame + dur,
            "action": "celebrate",
            "hops": hop_count,
            "pose": arm_style,
            "face": face,
        }

    return plan
