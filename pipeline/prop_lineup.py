"""
Render every prop in one labelled picture: public/roblox/props_lineup.png

    blender -b --factory-startup --python pipeline/prop_lineup.py [-- kind1,kind2 ...]
"""
import bpy, math, os, sys
from mathutils import Vector

ROOT = r"C:\Users\User\Desktop\blender roblox tiktoks"
ns = {}
for f in ("roblox_rig.py", "roblox_motions.py", "roblox_sets.py", "props.py"):
    exec(open(os.path.join(ROOT, "pipeline", f), encoding="utf-8").read(), ns)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
kinds = argv[0].split(",") if argv else ns["PROP_KINDS"]
SAMPLE_TEXT = {"sign": "sign:NO RUNNING", "paper": "paper:F-", "flag": "flag:TEAM"}

bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene
try:
    sc.render.engine = 'BLENDER_EEVEE'
except TypeError:
    pass
sc.view_settings.view_transform = 'Standard'
coll = bpy.data.collections.new("Props"); sc.collection.children.link(coll)
cols = 10
cell = 3.4
rows = (len(kinds) + cols - 1) // cols
for i, k in enumerate(kinds):
    x = (i % cols - (cols - 1) / 2) * cell
    z = -(i // cols) * 4.6
    root = ns["build_prop"](SAMPLE_TEXT.get(k, k), coll, f"P_{k}")
    h = ns["place_in_world"](root, (x, 0, z), 0, 1.0)
    if h > 3.4:
        ns["place_in_world"](root, (x, 0, z), 0, 3.4 / h)
    lab = bpy.data.curves.new(f"L_{k}", 'FONT'); lab.body = k; lab.size = 0.32; lab.align_x = 'CENTER'
    lo = bpy.data.objects.new(f"L_{k}", lab); coll.objects.link(lo)
    lo.location = (x, -0.6, z - 0.45); lo.rotation_euler = (math.pi / 2, 0, 0)
    lab.materials.append(ns["matte"]("LabelInk", (0.08, 0.08, 0.1)))

floor = ns["blk"](coll, "Backdrop", (cols * cell + 4, 0.2, rows * 4.6 + 4), (0, 2.5, -(rows - 1) * 2.3 + 1.2),
                  ns["matte"]("Backdrop", (0.86, 0.88, 0.92)), 0.0)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); coll.objects.link(sun)
sun.data.energy = 3.0; sun.data.use_shadow = False; sun.rotation_euler = (math.radians(55), 0, math.radians(-25))
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[1].default_value = 0.8
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); coll.objects.link(cam)
cam.data.type = 'ORTHO'; cam.data.ortho_scale = cols * cell + 1
cam.location = (0, -30, -(rows - 1) * 2.3 + 1.6); cam.rotation_euler = (math.radians(90), 0, 0)
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 2000, int(2000 * (rows * 4.6 + 1) / (cols * cell + 1))
sc.eevee.taa_render_samples = 16
try:
    sc.render.image_settings.media_type = 'IMAGE'
except Exception:
    pass
sc.render.image_settings.file_format = 'PNG'
out = os.path.join(ROOT, "public", "roblox", "props_lineup.png")
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("DONE", out)
