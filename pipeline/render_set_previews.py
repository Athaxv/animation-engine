"""
Render a still of each bright location with a couple of cast members on its marks.
Output: public/roblox/sets/<set>_<dressing>.png  (540x960)

Run inside Blender:
    exec(open(r"<project>/pipeline/render_set_previews.py", encoding="utf-8").read(), {"ONLY": ["street"]})
"""
import bpy, os, math
from mathutils import Vector

PROJECT = r"C:\Users\User\Desktop\blender roblox tiktoks"
SETS = os.path.join(PROJECT, "public", "roblox", "sets")

# set -> (cast: [(preset, mark, dx, dy, pose, face)], dressings)
SHOTS = {
    "bedroom":   ([("Theo", "center", -2.5, 2.0, "wave", "grin"),
                   ("Mom", "center", 2.0, 3.0, "hands_hips", "angry")], ["day", "night"]),
    "kitchen":   ([("Dad", "center", -2.5, 0, "explain", "talk"),
                   ("Lily", "center", 2.5, 0.5, "shrug", "smirk")], ["day"]),
    "classroom": ([("Officer", "teacher", 1.0, -1.0, "point", "confident"),
                   ("Noob", "board", 3.0, -2.0, "scared", "shocked")], ["day"]),
    "street":    ([("Theo", "sidewalk_b", -2.5, 0, "wave", "laugh"),
                   ("King", "sidewalk_b", 2.5, 0, "hands_hips", "smirk")], ["day", "sunset"]),
}


def load_ns():
    ns = {}
    for f in ("roblox_rig.py", "roblox_motions.py", "roblox_sets.py"):
        exec(open(os.path.join(PROJECT, "pipeline", f), encoding="utf-8").read(), ns)
    return ns


def render_set(name):
    # rebuild the set in place (open_mainfile leaves a stale context when run over MCP)
    bs = {}
    exec(open(os.path.join(PROJECT, "pipeline", "build_sets.py"), encoding="utf-8").read(), bs)
    ns = bs["build_one"](name, save=False)
    sc = bpy.context.scene
    bpy.context.view_layer.update()          # marks' matrix_world is stale right after building
    marks = ns["get_marks"](name)
    cam = sc.camera
    bpy.context.view_layer.objects.active = cam     # mode_set needs an active object
    cast, dressings = SHOTS[name]
    for preset, mk, dx, dy, pz, fc in cast:
        spec = dict(ns["PRESETS"][preset]); spec["face"] = fc
        base = Vector(marks[mk].matrix_world.translation)
        loc = base + Vector((dx, dy, 0))
        rig = ns["build_character"](f"P_{preset}", location=tuple(loc), **spec)
        # turn toward the camera (characters face -Y at heading 0)
        d = Vector(cam.location) - loc
        rig.rotation_euler = (0, 0, math.atan2(d.x, -d.y))
        ns["pose"](rig, pz, 1)
        ns["face"](rig, fc, 1)
    sc.frame_set(1)
    sc.render.resolution_percentage = 50
    sc.render.image_settings.file_format = 'PNG'
    out = []
    for d in dressings:
        ns["apply_dressing"](name, d)
        sc.render.filepath = os.path.join(SETS, f"{name}_{d}.png")
        bpy.ops.render.render(write_still=True)
        out.append(sc.render.filepath)
    return out


if "ONLY" in globals() or __name__ == "__main__":
    for n in globals().get("ONLY") or list(SHOTS):
        print("rendered", render_set(n))
