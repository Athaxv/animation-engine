"""
Build every bright location into its own file: public/roblox/sets/<name>.blend

Run inside Blender (MCP or Text Editor):
    exec(open(r"<project>/pipeline/build_sets.py", encoding="utf-8").read(), {"ONLY": ["street"]})
or headless:
    blender -b --python pipeline/build_sets.py
Each file gets the set, its default dressing and a preview camera at mark cam_default.
"""
import bpy, os, math
from mathutils import Vector

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else os.getcwd()
OUT = os.path.join(PROJECT, "public", "roblox", "sets")


def setup_scene():
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = -0.2
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.fps = 30
    sc.eevee.use_raytracing = True
    return sc


def load_ns():
    ns = {}
    for f in ("roblox_rig.py", "roblox_motions.py", "roblox_sets.py"):
        exec(open(os.path.join(PROJECT, "pipeline", f), encoding="utf-8").read(), ns)
    return ns


def build_one(name, save=True):
    sc = setup_scene()
    ns = load_ns()
    ns["face_atlas"]()          # shared expression atlas lives in every set file
    coll = ns["build_set"](name)
    marks = ns["get_marks"](name)
    cam = bpy.data.objects.new("SetCam", bpy.data.cameras.new("SetCam"))
    coll.objects.link(cam)
    cam.data.lens = 24
    m = marks["cam_default"]
    cam.location = m.location
    tgt = marks.get("center") or marks.get("sidewalk_b")
    aim = Vector(tgt.location) + Vector((0, 0, 3.0))
    cam.rotation_euler = (aim - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    if save:
        os.makedirs(OUT, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{name}.blend"), compress=True)
    return ns


if __name__ == "__main__" or "ONLY" in globals():
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = globals().get("ONLY") or argv or ["bedroom", "kitchen", "classroom", "street", "town_square"]
    for n in names:
        build_one(n)
        print("built", n)
