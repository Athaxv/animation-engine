"""
Roblox Cinematic Cinematography Package.

Exposes:
- Camera intelligence (framing, 180-deg conversational axis, obstacle resolution, quintic trajectories)
- Lighting engine (12 lighting moods, dynamic 3-point character lighting, color grading)
- Atmospheric and story VFX (volumetric fog, weather particles, story effects)
- Composition and continuity coordination
"""

from .camera import (
    FRAME_H,
    LOOK_Z,
    FSTOP,
    AXIS_TRACKER,
    calculate_framing,
    generate_camera_trajectory,
    resolve_camera_obstruction,
    test_obstruction_pure,
    quintic_ease,
    ConversationalAxisTracker,
    Vector,
)

from .lighting import (
    LIGHTING_PRESETS,
    resolve_lighting_mood,
    calculate_three_point_rig,
    apply_three_point_rig,
    apply_world_lighting,
    apply_color_grading,
)

from .vfx import (
    setup_volumetric_fog,
    build_weather_system,
    build_story_vfx,
    simulate_particle_step,
    generate_weather_particles_kinematics,
)

from .composition import (
    resolve_shot_cinematography,
    validate_cinematic_continuity,
)

__all__ = [
    "FRAME_H",
    "LOOK_Z",
    "FSTOP",
    "AXIS_TRACKER",
    "calculate_framing",
    "generate_camera_trajectory",
    "resolve_camera_obstruction",
    "test_obstruction_pure",
    "quintic_ease",
    "ConversationalAxisTracker",
    "Vector",
    "LIGHTING_PRESETS",
    "resolve_lighting_mood",
    "calculate_three_point_rig",
    "apply_three_point_rig",
    "apply_world_lighting",
    "apply_color_grading",
    "setup_volumetric_fog",
    "build_weather_system",
    "build_story_vfx",
    "simulate_particle_step",
    "generate_weather_particles_kinematics",
    "resolve_shot_cinematography",
    "validate_cinematic_continuity",
]
