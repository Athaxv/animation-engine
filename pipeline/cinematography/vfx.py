"""
Atmospheric and Environmental VFX Subsystem.

Provides:
- Deterministic, headless-compatible procedural volumetric fog and distance haze
- Weather systems (Rain streaks, Snow flakes, Falling autumn leaves)
- Story-driven procedural VFX (Sparks/embers, Magical portals, Energy bursts, Impact dust)
- Environmental motion (Wind-swayed foliage, Streetlight flicker)
"""
import math
import random
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from mathutils import Vector, Euler, Matrix
except ImportError:
    from .camera import Vector


# ---------------------------------------------------------------------------
# Pure Python Kinematic Simulation (Deterministic & Testable)
# ---------------------------------------------------------------------------
def simulate_particle_step(
    pos: Tuple[float, float, float],
    vel: Tuple[float, float, float],
    time_sec: float,
    seed: int,
    turbulence: float = 0.0,
) -> Tuple[float, float, float]:
    """
    Computes deterministic position of a particle at time_sec given base velocity and turbulence.
    """
    rng = random.Random(seed)
    phase_x = rng.uniform(0.0, math.pi * 2.0)
    phase_y = rng.uniform(0.0, math.pi * 2.0)

    turb_x = math.sin(time_sec * 3.0 + phase_x) * turbulence
    turb_y = math.cos(time_sec * 2.5 + phase_y) * turbulence

    return (
        pos[0] + vel[0] * time_sec + turb_x,
        pos[1] + vel[1] * time_sec + turb_y,
        pos[2] + vel[2] * time_sec,
    )


def generate_weather_particles_kinematics(
    weather_type: str,
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
    count: int,
    duration_sec: float,
    seed: int = 42,
    fps: int = 30,
) -> List[Dict[str, Any]]:
    """
    Generates deterministic kinematic trajectories for weather particles.
    """
    rng = random.Random(seed)
    (x0, y0, z0), (x1, y1, z1) = bounds
    particles = []

    for i in range(count):
        p_seed = seed + i * 17
        init_pos = (
            rng.uniform(x0, x1),
            rng.uniform(y0, y1),
            rng.uniform(z0, z1),
        )

        if weather_type == "rain":
            vel = (0.3, -0.6, -22.0)
            turb = 0.05
            scale = (0.04, 0.04, 0.45)
            color = (0.75, 0.85, 1.0, 0.6)
        elif weather_type == "snow":
            vel = (0.1, -0.2, -2.8)
            turb = 0.45
            scale = (0.15, 0.15, 0.15)
            color = (0.95, 0.98, 1.0, 0.85)
        elif weather_type == "falling_leaves":
            vel = (0.4, -0.3, -1.8)
            turb = 0.85
            scale = (0.28, 0.28, 0.05)
            leaf_colors = [
                (0.85, 0.35, 0.1, 1.0),   # orange
                (0.92, 0.65, 0.15, 1.0),  # amber
                (0.65, 0.18, 0.12, 1.0),  # crimson
            ]
            color = leaf_colors[i % len(leaf_colors)]
        else:
            vel = (0.0, 0.0, 0.0)
            turb = 0.0
            scale = (0.1, 0.1, 0.1)
            color = (1.0, 1.0, 1.0, 1.0)

        particles.append({
            "id": f"p_{weather_type}_{i}",
            "initial_pos": init_pos,
            "velocity": vel,
            "turbulence": turb,
            "scale": scale,
            "color": color,
            "seed": p_seed,
        })

    return particles


# ---------------------------------------------------------------------------
# Blender Scene VFX Construction Hooks (Headless EEVEE Compatible)
# ---------------------------------------------------------------------------
def setup_volumetric_fog(
    bpy_module,
    scene,
    mood_name: str,
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
    frame_start: int,
    frame_end: int,
):
    """
    Creates or updates an optimized volumetric fog domain cube with a Principled Volume shader.
    """
    bpy = bpy_module
    obj_name = "EP_VolumeFog"
    obj = bpy.data.objects.get(obj_name)

    (x0, y0, z0), (x1, y1, z1) = bounds
    size_x = abs(x1 - x0) + 40.0
    size_y = abs(y1 - y0) + 40.0
    size_z = abs(z1 - z0) + 20.0
    center = ((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5 + 4.0)

    if obj is None:
        mesh = bpy.data.meshes.new(obj_name)
        obj = bpy.data.objects.new(obj_name, mesh)
        scene.collection.objects.link(obj)

        # Generate cube geometry
        hx, hy, hz = size_x * 0.5, size_y * 0.5, size_z * 0.5
        verts = [
            (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
            (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)
        ]
        faces = [
            (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
            (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)
        ]
        mesh.from_pydata(verts, [], faces)
        mesh.update()

    obj.location = center

    # Material setup
    mat_name = "M_VolumeFog"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        out_node = nodes.new("ShaderNodeOutputMaterial")
        vol_node = nodes.new("ShaderNodeVolumePrincipled")
        links.new(vol_node.outputs["Volume"], out_node.inputs["Volume"])

    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat

    # Subtle cinematic density per mood (calibrated for Blender 5 EEVEE distance haze)
    densities = {
        "horror": 0.00006,
        "fantasy_magical": 0.00004,
        "golden_hour": 0.00003,
        "sunset": 0.000035,
        "moonlit_night": 0.000035,
        "blue_hour": 0.00003,
        "nighttime": 0.000025,
        "bright_day": 0.000015,
        "soft_afternoon": 0.00002,
        "indoor_daylight": 0.00001,
        "warm_bedroom": 0.000015,
        "school_office": 0.00001,
    }
    density = densities.get(mood_name, 0.0005)

    nodes = mat.node_tree.nodes
    vol_node = next((n for n in nodes if n.type == 'VOLUME_PRINCIPLED'), None)
    if vol_node:
        vol_node.inputs["Color"].default_value = (0.75, 0.75, 0.80, 1.0)
        vol_node.inputs["Density"].default_value = density
        vol_node.inputs["Anisotropy"].default_value = 0.55  # Subtle forward scattering god rays
        vol_node.inputs["Density"].keyframe_insert("default_value", frame=frame_start)

    # Keyframe visibility so fog domain only renders during shots where fog is requested
    if frame_start > 1:
        obj.hide_render = True
        obj.hide_viewport = True
        obj.keyframe_insert("hide_render", frame=1)
        obj.keyframe_insert("hide_viewport", frame=1)
        obj.keyframe_insert("hide_render", frame=frame_start - 1)
        obj.keyframe_insert("hide_viewport", frame=frame_start - 1)

    obj.hide_render = False
    obj.hide_viewport = False
    obj.keyframe_insert("hide_render", frame=frame_start)
    obj.keyframe_insert("hide_viewport", frame=frame_start)

    obj.hide_render = True
    obj.hide_viewport = True
    obj.keyframe_insert("hide_render", frame=frame_end + 1)
    obj.keyframe_insert("hide_viewport", frame=frame_end + 1)


def build_weather_system(
    bpy_module,
    scene,
    weather_type: str,
    bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]],
    frame_start: int,
    frame_end: int,
    fps: int = 30,
    seed: int = 42,
):
    """
    Instantiates linked mesh particle instances in Blender with deterministic keyframed trajectories.
    """
    bpy = bpy_module
    coll_name = "EP_VFX_Weather"
    coll = bpy.data.collections.get(coll_name)
    if coll is None:
        coll = bpy.data.collections.new(coll_name)
        scene.collection.children.link(coll)

    # Particle counts capped for headless EEVEE thermal safety
    counts = {
        "rain": 140,
        "snow": 85,
        "falling_leaves": 45,
    }
    count = counts.get(weather_type, 50)
    duration_sec = (frame_end - frame_start) / fps

    particles = generate_weather_particles_kinematics(
        weather_type, bounds, count, duration_sec, seed, fps
    )

    # Base mesh for instancing
    mesh_name = f"Mesh_Particle_{weather_type}"
    base_mesh = bpy.data.meshes.get(mesh_name)
    if base_mesh is None:
        base_mesh = bpy.data.meshes.new(mesh_name)
        # Create small primitive
        s = 0.1
        verts = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
                 (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
        faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                 (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
        base_mesh.from_pydata(verts, [], faces)
        base_mesh.update()

    # Base material
    mat_name = f"M_Particle_{weather_type}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            if weather_type == "rain":
                bsdf.inputs["Roughness"].default_value = 0.05
                bsdf.inputs["Transmission Weight"].default_value = 0.85
            elif weather_type == "snow":
                bsdf.inputs["Roughness"].default_value = 0.3
                bsdf.inputs["Base Color"].default_value = (0.95, 0.98, 1.0, 1.0)
            elif weather_type == "falling_leaves":
                bsdf.inputs["Roughness"].default_value = 0.45
                bsdf.inputs["Base Color"].default_value = (0.85, 0.4, 0.1, 1.0)

    for p in particles:
        p_obj_name = p["id"]
        obj = bpy.data.objects.get(p_obj_name)
        if obj is None:
            obj = bpy.data.objects.new(p_obj_name, base_mesh)
            coll.objects.link(obj)
            if not obj.data.materials:
                obj.data.materials.append(mat)

        obj.scale = p["scale"]
        x0, y0, z0 = p["initial_pos"]
        vx, vy, vz = p["velocity"]
        turb = p["turbulence"]
        p_seed = p["seed"]

        # Keyframe start and end positions
        pos_start = simulate_particle_step((x0, y0, z0), (vx, vy, vz), 0.0, p_seed, turb)
        pos_end = simulate_particle_step((x0, y0, z0), (vx, vy, vz), duration_sec, p_seed, turb)

        obj.location = pos_start
        obj.keyframe_insert("location", frame=frame_start)

        obj.location = pos_end
        obj.keyframe_insert("location", frame=frame_end)


def build_story_vfx(
    bpy_module,
    scene,
    vfx_type: str,
    target_pos: Tuple[float, float, float],
    frame_start: int,
    frame_end: int,
    fps: int = 30,
):
    """
    Creates story-driven procedural effects (magical portal, sparks, energy burst, impact dust).
    """
    bpy = bpy_module
    coll_name = "EP_VFX_Story"
    coll = bpy.data.collections.get(coll_name)
    if coll is None:
        coll = bpy.data.collections.new(coll_name)
        scene.collection.children.link(coll)

    tx, ty, tz = target_pos

    if vfx_type == "portal":
        # Swirling emissive torus
        portal_name = "EP_VFX_Portal"
        portal = bpy.data.objects.get(portal_name)
        if portal is None:
            mesh = bpy.data.meshes.new(portal_name)
            portal = bpy.data.objects.new(portal_name, mesh)
            coll.objects.link(portal)

            # Toroid ring vertices
            verts = []
            faces = []
            r_major = 2.4
            r_minor = 0.25
            segs_u = 16
            segs_v = 8
            for u in range(segs_u):
                theta = u * 2.0 * math.pi / segs_u
                for v in range(segs_v):
                    phi = v * 2.0 * math.pi / segs_v
                    vx = (r_major + r_minor * math.cos(phi)) * math.cos(theta)
                    vy = (r_major + r_minor * math.cos(phi)) * math.sin(theta)
                    vz = r_minor * math.sin(phi)
                    verts.append((vx, vy, vz))

            for u in range(segs_u):
                u_next = (u + 1) % segs_u
                for v in range(segs_v):
                    v_next = (v + 1) % segs_v
                    i0 = u * segs_v + v
                    i1 = u_next * segs_v + v
                    i2 = u_next * segs_v + v_next
                    i3 = u * segs_v + v_next
                    faces.append((i0, i1, i2, i3))

            mesh.from_pydata(verts, [], faces)
            mesh.update()

            # Glowing emissive material
            mat = bpy.data.materials.new("M_PortalGlow")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            bsdf = nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Emission Color"].default_value = (0.75, 0.2, 1.0, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 8.5
                bsdf.inputs["Base Color"].default_value = (0.4, 0.1, 0.8, 1.0)
            portal.data.materials.append(mat)

        portal.location = (tx, ty + 3.2, tz + 2.4)
        portal.rotation_euler = (math.radians(90), 0, 0)

        # Keyframe visibility
        if frame_start > 1:
            portal.hide_render = True
            portal.hide_viewport = True
            portal.keyframe_insert("hide_render", frame=1)
            portal.keyframe_insert("hide_viewport", frame=1)
            portal.keyframe_insert("hide_render", frame=frame_start - 1)
            portal.keyframe_insert("hide_viewport", frame=frame_start - 1)

        portal.hide_render = False
        portal.hide_viewport = False
        portal.keyframe_insert("hide_render", frame=frame_start)
        portal.keyframe_insert("hide_viewport", frame=frame_start)

        portal.hide_render = True
        portal.hide_viewport = True
        portal.keyframe_insert("hide_render", frame=frame_end + 1)
        portal.keyframe_insert("hide_viewport", frame=frame_end + 1)

        # Pulse scale and rotation
        portal.scale = (0.1, 0.1, 0.1)
        portal.keyframe_insert("scale", frame=frame_start)
        portal.keyframe_insert("rotation_euler", frame=frame_start)

        mid_frame = (frame_start + frame_end) // 2
        portal.scale = (1.1, 1.1, 1.1)
        portal.rotation_euler = (math.radians(90), 0, math.radians(180))
        portal.keyframe_insert("scale", frame=mid_frame)
        portal.keyframe_insert("rotation_euler", frame=mid_frame)

        portal.scale = (1.0, 1.0, 1.0)
        portal.rotation_euler = (math.radians(90), 0, math.radians(360))
        portal.keyframe_insert("scale", frame=frame_end)
        portal.keyframe_insert("rotation_euler", frame=frame_end)

    elif vfx_type in ("sparks", "energy_burst"):
        # Emissive spark burst
        burst_name = f"EP_VFX_{vfx_type}"
        burst_mesh = bpy.data.meshes.new(burst_name)
        burst_obj = bpy.data.objects.new(burst_name, burst_mesh)
        coll.objects.link(burst_obj)

        s = 0.08
        verts = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
                 (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
        faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                 (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)]
        burst_mesh.from_pydata(verts, [], faces)
        burst_mesh.update()

        mat = bpy.data.materials.new("M_SparkGlow")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.75, 0.2, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 12.0
        burst_obj.data.materials.append(mat)

        # Keyframe visibility
        if frame_start > 1:
            burst_obj.hide_render = True
            burst_obj.hide_viewport = True
            burst_obj.keyframe_insert("hide_render", frame=1)
            burst_obj.keyframe_insert("hide_viewport", frame=1)
            burst_obj.keyframe_insert("hide_render", frame=frame_start - 1)
            burst_obj.keyframe_insert("hide_viewport", frame=frame_start - 1)

        burst_obj.hide_render = False
        burst_obj.hide_viewport = False
        burst_obj.keyframe_insert("hide_render", frame=frame_start)
        burst_obj.keyframe_insert("hide_viewport", frame=frame_start)

        burst_obj.hide_render = True
        burst_obj.hide_viewport = True
        burst_obj.keyframe_insert("hide_render", frame=frame_end + 1)
        burst_obj.keyframe_insert("hide_viewport", frame=frame_end + 1)

        burst_obj.location = (tx, ty + 1.2, tz + 2.0)
        burst_obj.scale = (0.2, 0.2, 0.2)
        burst_obj.keyframe_insert("scale", frame=frame_start)
        burst_obj.keyframe_insert("location", frame=frame_start)

        burst_obj.location = (tx, ty + 1.8, tz + 3.8)
        burst_obj.scale = (1.6, 1.6, 1.6)
        burst_obj.keyframe_insert("scale", frame=frame_end)
        burst_obj.keyframe_insert("location", frame=frame_end)
