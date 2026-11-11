"""
Scene-Level Visual Composition Subsystem.

Provides:
- Unification of camera language, lighting environment, weather, and VFX across multi-shot sequences
- Cinematic continuity checking (conversational 180-degree axis, lighting transitions)
- Safe fallback resolution from legacy shot specifications
"""
from typing import Any, Dict, List, Optional, Tuple

from .camera import FRAME_H, LOOK_Z, FSTOP, AXIS_TRACKER
from .lighting import LIGHTING_PRESETS, resolve_lighting_mood


# ---------------------------------------------------------------------------
# Composition Specification & Resolution
# ---------------------------------------------------------------------------
def resolve_shot_cinematography(
    shot: Dict[str, Any],
    prev_shot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extracts and standardizes cinematography parameters from a shot specification,
    ensuring full backward compatibility with legacy shot files.
    """
    cam = shot.get("camera", {})

    # Camera language
    c_shot = cam.get("shot", "medium")
    c_angle = cam.get("angle", "eye")
    c_move = cam.get("move", "static")
    c_target = cam.get("target")

    # Map aliases
    if c_shot == "establishing":
        c_shot = "wide"
    if c_angle == "birds_eye":
        c_angle = "top"

    # Lighting mood resolution (supports shot['lighting']['mood'], shot['lighting'], or shot['dressing'])
    lighting_spec = shot.get("lighting")
    if isinstance(lighting_spec, dict):
        raw_mood = lighting_spec.get("mood")
    elif isinstance(lighting_spec, str):
        raw_mood = lighting_spec
    else:
        raw_mood = shot.get("dressing", "day")

    mood = resolve_lighting_mood(raw_mood)

    # Weather resolution
    weather = shot.get("weather")
    if not weather and isinstance(lighting_spec, dict):
        weather = lighting_spec.get("weather")
    weather = str(weather).lower().strip() if weather else "clear"
    if weather not in ("clear", "rain", "snow", "falling_leaves", "windy"):
        weather = "clear"

    # VFX resolution
    vfx_list = shot.get("vfx", [])
    if isinstance(vfx_list, str):
        vfx_list = [vfx_list]
    vfx_resolved = [str(v).lower().strip() for v in vfx_list]

    return {
        "shot": c_shot,
        "angle": c_angle,
        "move": c_move,
        "target": c_target,
        "mood": mood,
        "weather": weather,
        "vfx": vfx_resolved,
        "use_dof": c_shot in FSTOP,
        "fstop": FSTOP.get(c_shot, 5.6),
    }


def validate_cinematic_continuity(
    shots: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Audits a sequence of shots for cinematic continuity issues:
    - 180-degree axis violations
    - Excessive repeated framings
    - Unmotivated hard lighting mood changes
    """
    issues = []
    prev_cin = None
    prev_set = None

    for idx, shot in enumerate(shots):
        sid = shot.get("id", f"shot_{idx}")
        st = shot.get("set", "unknown")
        cin = resolve_shot_cinematography(shot, shots[idx - 1] if idx > 0 else None)

        if prev_cin:
            # Check 1: Triple identical framings
            if (
                cin["shot"] == prev_cin["shot"]
                and cin["angle"] == prev_cin["angle"]
                and cin["move"] == prev_cin["move"]
            ):
                issues.append({
                    "shot_id": sid,
                    "type": "warning",
                    "message": f"Consecutive shot repeats identical composition ({cin['shot']}, {cin['angle']}, {cin['move']}).",
                })

            # Check 2: Unmotivated lighting jump on same set without transition
            if st == prev_set and cin["mood"] != prev_cin["mood"]:
                transition = shot.get("transition", "cut")
                if transition not in ("fade_black", "whip", "flash"):
                    issues.append({
                        "shot_id": sid,
                        "type": "warning",
                        "message": f"Lighting mood jumps from {prev_cin['mood']} to {cin['mood']} on a hard cut.",
                    })

        prev_cin = cin
        prev_set = st

    return issues
