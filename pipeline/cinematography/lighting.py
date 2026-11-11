"""
Cinematic Lighting Engine Subsystem.

Provides:
- 12 distinct atmospheric lighting environments (day, golden hour, blue hour, horror, fantasy, etc.)
- Dynamic 3-point character lighting rig (Key, Fill, Rim) for crisp actor readability
- Environment-aware exterior/interior lighting transitions
- View transform and color grading management (AgX/Filmic, exposure, contrast)
"""
import math
from typing import Any, Dict, Optional, Tuple, Union

try:
    from mathutils import Vector, Euler
except ImportError:
    from .camera import Vector


# ---------------------------------------------------------------------------
# 12 Cinematic Lighting Presets
# ---------------------------------------------------------------------------
# Format:
#   sky_rgb: Camera-visible background sky color (sRGB)
#   light_rgb: Irradiance / ambient bounce color
#   ambient_strength: World ambient energy multiplier
#   sun_elev_deg: Sun/primary directional light elevation in degrees
#   sun_azim_deg: Sun/primary directional light azimuth in degrees
#   sun_color: Sun direct light color
#   sun_energy: Base key energy
#   view_look: Color management look ("Medium High Contrast", "High Contrast", etc.)
#   exposure: Exposure compensation EV
LIGHTING_PRESETS: Dict[str, Dict[str, Any]] = {
    "bright_day": {
        "sky_rgb": (0.42, 0.72, 1.00),
        "light_rgb": (0.85, 0.92, 1.00),
        "ambient_strength": 0.55,
        "sun_elev_deg": 65.0,
        "sun_azim_deg": 135.0,
        "sun_color": (1.00, 0.98, 0.92),
        "sun_energy": 180.0,
        "view_look": "Medium High Contrast",
        "exposure": 0.0,
    },
    "soft_afternoon": {
        "sky_rgb": (0.50, 0.70, 0.95),
        "light_rgb": (0.90, 0.88, 0.82),
        "ambient_strength": 0.50,
        "sun_elev_deg": 40.0,
        "sun_azim_deg": 150.0,
        "sun_color": (1.00, 0.92, 0.80),
        "sun_energy": 150.0,
        "view_look": "Medium High Contrast",
        "exposure": 0.0,
    },
    "golden_hour": {
        "sky_rgb": (0.82, 0.58, 0.40),
        "light_rgb": (1.00, 0.80, 0.55),
        "ambient_strength": 0.48,
        "sun_elev_deg": 14.0,
        "sun_azim_deg": 170.0,
        "sun_color": (1.00, 0.72, 0.35),
        "sun_energy": 160.0,
        "view_look": "High Contrast",
        "exposure": 0.1,
    },
    "sunset": {
        "sky_rgb": (1.00, 0.45, 0.28),
        "light_rgb": (0.95, 0.60, 0.45),
        "ambient_strength": 0.45,
        "sun_elev_deg": 4.0,
        "sun_azim_deg": 185.0,
        "sun_color": (1.00, 0.50, 0.20),
        "sun_energy": 120.0,
        "view_look": "High Contrast",
        "exposure": -0.1,
    },
    "blue_hour": {
        "sky_rgb": (0.12, 0.18, 0.45),
        "light_rgb": (0.25, 0.35, 0.65),
        "ambient_strength": 0.38,
        "sun_elev_deg": -6.0,
        "sun_azim_deg": 195.0,
        "sun_color": (0.40, 0.50, 0.85),
        "sun_energy": 45.0,
        "view_look": "Medium Contrast",
        "exposure": -0.2,
    },
    "nighttime": {
        "sky_rgb": (0.04, 0.06, 0.14),
        "light_rgb": (0.15, 0.20, 0.35),
        "ambient_strength": 0.32,
        "sun_elev_deg": -30.0,
        "sun_azim_deg": 210.0,
        "sun_color": (0.20, 0.25, 0.45),
        "sun_energy": 25.0,
        "view_look": "High Contrast",
        "exposure": -0.3,
    },
    "moonlit_night": {
        "sky_rgb": (0.05, 0.08, 0.18),
        "light_rgb": (0.20, 0.30, 0.50),
        "ambient_strength": 0.35,
        "sun_elev_deg": 55.0,
        "sun_azim_deg": 45.0,
        "sun_color": (0.65, 0.80, 1.00),
        "sun_energy": 75.0,
        "view_look": "High Contrast",
        "exposure": -0.15,
    },
    "indoor_daylight": {
        "sky_rgb": (0.60, 0.75, 0.95),
        "light_rgb": (0.90, 0.92, 0.95),
        "ambient_strength": 0.60,
        "sun_elev_deg": 50.0,
        "sun_azim_deg": 90.0,
        "sun_color": (1.00, 0.96, 0.90),
        "sun_energy": 130.0,
        "view_look": "Medium Contrast",
        "exposure": 0.0,
    },
    "warm_bedroom": {
        "sky_rgb": (0.20, 0.15, 0.10),
        "light_rgb": (1.00, 0.85, 0.60),
        "ambient_strength": 0.42,
        "sun_elev_deg": 25.0,
        "sun_azim_deg": 120.0,
        "sun_color": (1.00, 0.78, 0.45),
        "sun_energy": 90.0,
        "view_look": "Medium High Contrast",
        "exposure": 0.05,
    },
    "school_office": {
        "sky_rgb": (0.70, 0.75, 0.80),
        "light_rgb": (0.85, 0.88, 0.92),
        "ambient_strength": 0.55,
        "sun_elev_deg": 80.0,
        "sun_azim_deg": 0.0,
        "sun_color": (0.92, 0.95, 1.00),
        "sun_energy": 110.0,
        "view_look": "Medium Contrast",
        "exposure": 0.0,
    },
    "horror": {
        "sky_rgb": (0.05, 0.12, 0.08),
        "light_rgb": (0.18, 0.38, 0.26),
        "ambient_strength": 0.44,
        "sun_elev_deg": -10.0,
        "sun_azim_deg": 180.0,
        "sun_color": (0.30, 0.85, 0.50),
        "sun_energy": 85.0,
        "view_look": "High Contrast",
        "exposure": -0.05,
    },
    "fantasy_magical": {
        "sky_rgb": (0.35, 0.15, 0.50),
        "light_rgb": (0.60, 0.30, 0.80),
        "ambient_strength": 0.52,
        "sun_elev_deg": 35.0,
        "sun_azim_deg": 225.0,
        "sun_color": (0.85, 0.40, 1.00),
        "sun_energy": 125.0,
        "view_look": "High Contrast",
        "exposure": 0.1,
    },
}

# Legacy mapping for backward compatibility
LEGACY_DRESSING_MAP = {
    "day": "bright_day",
    "sunset": "sunset",
    "night": "nighttime",
}


def resolve_lighting_mood(mood_or_dressing: Optional[str]) -> str:
    """Resolves any mood name or legacy dressing string into a valid lighting preset key."""
    if not mood_or_dressing:
        return "bright_day"
    m = str(mood_or_dressing).lower().strip()
    if m in LIGHTING_PRESETS:
        return m
    if m in LEGACY_DRESSING_MAP:
        return LEGACY_DRESSING_MAP[m]
    return "bright_day"


# ---------------------------------------------------------------------------
# Dynamic 3-Point Character Rig Math
# ---------------------------------------------------------------------------
def calculate_three_point_rig(
    cam_pos: Vector,
    look_pos: Vector,
    mood_name: str = "bright_day",
    interior: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes 3-point light positions, orientations, colors, and energies relative to subject and camera.

    Returns dict with keys: 'key', 'fill', 'rim'.
    """
    mood = LIGHTING_PRESETS[resolve_lighting_mood(mood_name)]
    d = look_pos - cam_pos
    dist = max(1.0, d.length)

    # Unit vectors in horizontal plane
    fwd = Vector((d.x, d.y, 0.0)).normalized()
    if fwd.length < 1e-4:
        fwd = Vector((0.0, 1.0, 0.0))
    right = Vector((fwd.y, -fwd.x, 0.0))

    base_e = mood["sun_energy"] * (0.85 if interior else 1.0) * max(1.0, dist / 8.0) ** 1.8 * 0.45

    # 1. Key Light (42 deg off-camera to subject's right, elevated 32 deg)
    key_offset = (right * 0.7 + fwd * 0.4).normalized() * min(3.8, 0.35 * dist + 1.2)
    key_pos = cam_pos + key_offset + Vector((0.0, 0.0, min(3.5, 0.28 * dist + 1.2)))
    key_dir = (look_pos - key_pos).normalized()

    # 2. Fill Light (Opposite key: -35 deg to subject's left, lower elevation 15 deg, softer intensity)
    fill_offset = (-right * 0.65 + fwd * 0.45).normalized() * min(3.5, 0.32 * dist + 1.0)
    fill_pos = cam_pos + fill_offset + Vector((0.0, 0.0, min(2.5, 0.18 * dist + 0.8)))
    fill_dir = (look_pos - fill_pos).normalized()
    fill_e = base_e * 0.38
    fill_color = tuple((c + 0.15) / 1.15 for c in mood["light_rgb"])

    # 3. Rim / Kicker Light (Behind subject at ~155 deg, elevated 45 deg, aimed at back of head/shoulders)
    rim_offset = (fwd * 0.85 + right * 0.3).normalized() * min(3.2, 0.3 * dist + 1.0)
    rim_pos = look_pos + rim_offset + Vector((0.0, 0.0, min(3.0, 0.25 * dist + 1.5)))
    rim_dir = (look_pos - rim_pos).normalized()
    rim_e = base_e * 1.25
    # Tint rim with sky or sun color for crisp edge specular highlight
    rim_color = mood["sun_color"]

    return {
        "key": {
            "pos": key_pos,
            "dir": key_dir,
            "color": mood["sun_color"],
            "energy": base_e,
            "size": 4.5,
        },
        "fill": {
            "pos": fill_pos,
            "dir": fill_dir,
            "color": fill_color,
            "energy": fill_e,
            "size": 6.0,
        },
        "rim": {
            "pos": rim_pos,
            "dir": rim_dir,
            "color": rim_color,
            "energy": rim_e,
            "size": 3.0,
        },
    }


# ---------------------------------------------------------------------------
# Blender Scene Integration Hooks
# ---------------------------------------------------------------------------
def apply_three_point_rig(
    bpy_module,
    cam_pos: Vector,
    look_pos: Vector,
    frame: int,
    mood_name: str = "bright_day",
    interior: bool = False,
):
    """
    Instantiates or updates the 3-point dynamic lighting rig in Blender for the current frame.
    """
    bpy = bpy_module
    rig_data = calculate_three_point_rig(cam_pos, look_pos, mood_name, interior)

    # Ensure collection exists
    coll_name = "EP_CinematicLights"
    coll = bpy.data.collections.get(coll_name)
    if coll is None:
        coll = bpy.data.collections.new(coll_name)
        bpy.context.scene.collection.children.link(coll)

    lamp_configs = [
        ("EP_KeyLight", rig_data["key"]),
        ("EP_FillLight", rig_data["fill"]),
        ("EP_RimLight", rig_data["rim"]),
    ]

    for lamp_name, cfg in lamp_configs:
        obj = bpy.data.objects.get(lamp_name)
        if obj is None:
            light_data = bpy.data.lights.new(lamp_name, 'AREA')
            obj = bpy.data.objects.new(lamp_name, light_data)
            coll.objects.link(obj)

        obj.data.size = cfg["size"]
        obj.data.color = cfg["color"]
        obj.data.energy = cfg["energy"]
        obj.location = cfg["pos"]

        # Track toward look target
        track_quat = (look_pos - cfg["pos"]).to_track_quat('-Z', 'Y')
        obj.rotation_euler = track_quat.to_euler()

        # Keyframe
        obj.keyframe_insert("location", frame=frame)
        obj.keyframe_insert("rotation_euler", frame=frame)
        obj.data.keyframe_insert("energy", frame=frame)
        obj.data.keyframe_insert("color", frame=frame)


def apply_world_lighting(
    bpy_module,
    world,
    mood_name: str,
    frame: int,
):
    """
    Applies atmospheric sky and ambient lighting to Blender's world node tree.
    """
    bpy = bpy_module
    mood = LIGHTING_PRESETS[resolve_lighting_mood(mood_name)]
    N = world.node_tree.nodes

    cam_bg = N.get("CamBG")
    light_bg = N.get("LightBG")

    if cam_bg and light_bg:
        # sRGB to linear conversion helper
        def srgb_to_lin(rgb):
            return tuple(pow(c, 2.2) for c in rgb)

        cam_bg.inputs[0].default_value = (*srgb_to_lin(mood["sky_rgb"]), 1.0)
        light_bg.inputs[0].default_value = (*srgb_to_lin(mood["light_rgb"]), 1.0)
        light_bg.inputs[1].default_value = mood["ambient_strength"]

        cam_bg.inputs[0].keyframe_insert("default_value", frame=frame)
        light_bg.inputs[0].keyframe_insert("default_value", frame=frame)
        light_bg.inputs[1].keyframe_insert("default_value", frame=frame)


def apply_color_grading(bpy_module, scene, mood_name: str):
    """
    Configures Blender scene color management (view transform, look, exposure).
    """
    bpy = bpy_module
    mood = LIGHTING_PRESETS[resolve_lighting_mood(mood_name)]
    cm = scene.view_settings

    # Select best supported view transform
    supported_views = [e.identifier for e in cm.bl_rna.properties['view_transform'].enum_items]
    if "AgX" in supported_views:
        cm.view_transform = "AgX"
    elif "Filmic" in supported_views:
        cm.view_transform = "Filmic"
    else:
        cm.view_transform = "Standard"

    # Supported looks
    supported_looks = [e.identifier for e in cm.bl_rna.properties['look'].enum_items]
    desired_look = mood["view_look"]
    if desired_look in supported_looks:
        cm.look = desired_look
    elif "Medium High Contrast" in supported_looks:
        cm.look = "Medium High Contrast"
    else:
        cm.look = "None"

    cm.exposure = mood["exposure"]
