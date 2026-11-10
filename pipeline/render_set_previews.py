"""
Render a still of each bright location with a couple of cast members on its marks.
Output: public/roblox/sets/<set>_<dressing>.png  (540x960)
Also supports rendering a 6-panel town_square showcase contact sheet:
    blender -b --factory-startup -t 2 --python pipeline/render_set_previews.py -- town_square --sheet
"""
import os, math, sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else os.getcwd()
SETS = os.path.join(PROJECT, "public", "roblox", "sets")

# set -> (cast: [(preset, mark, dx, dy, pose, face)], dressings)
SHOTS = {
    "bedroom":     ([("Theo", "center", -2.5, 2.0, "wave", "grin"),
                     ("Mom", "center", 2.0, 3.0, "hands_hips", "angry")], ["day", "night"]),
    "kitchen":     ([("Dad", "center", -2.5, 0, "explain", "talk"),
                     ("Lily", "center", 2.5, 0.5, "shrug", "smirk")], ["day"]),
    "classroom":   ([("Officer", "teacher", 1.0, -1.0, "point", "confident"),
                     ("Noob", "board", 3.0, -2.0, "scared", "shocked")], ["day"]),
    "street":      ([("Theo", "sidewalk_b", -2.5, 0, "wave", "laugh"),
                     ("King", "sidewalk_b", 2.5, 0, "hands_hips", "smirk")], ["day", "sunset"]),
    "town_square": ([("Theo", "plaza_left", 0.0, 0.0, "wave", "grin"),
                     ("Lily", "center", 0.0, 0.0, "arms_up", "laugh"),
                     ("King", "plaza_right", 0.0, 0.0, "hands_hips", "confident")], ["day", "sunset", "night"]),
}

SHOWCASE_ANGLES = [
    ("01_plaza_wide_day",       "day",    (0.0, -16.5, 5.4),   (0.0, 10.0, 6.5),  24),
    ("02_bakery_bench_day",     "day",    (-9.8, -5.8, 4.2),   (-9.6, 10.0, 4.2), 21),
    ("03_portal_bridge_day",    "day",    (14.5, -6.5, 4.6),   (14.0, 10.5, 4.2), 24),
    ("04_fountain_hero_day",    "day",    (0.0, -9.2, 4.0),    (0.0, 4.5, 3.8),   30),
    ("05_sunset_plaza",         "sunset", (2.5, -17.0, 5.6),   (0.0, 12.0, 7.0),  24),
    ("06_night_lanterns_magic", "night",  (-2.5, -16.5, 5.2),  (2.0, 11.0, 6.5),  24),
]


def stitch_showcase_sheet():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.run(["python", os.path.abspath(__file__), "--stitch-sheet"], check=True)
        return os.path.join(SETS, "town_square_showcase_sheet.png")

    panel_paths = [(lbl, dr, os.path.join(SETS, f"ts_{lbl}.png")) for lbl, dr, *_ in SHOWCASE_ANGLES]
    w, h = Image.open(panel_paths[0][2]).size
    cols, rows = 3, 2
    bar = 44
    sheet = Image.new("RGB", (w * cols, (h + bar) * rows), (18, 20, 26))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    for idx, (label, dress, p_path) in enumerate(panel_paths):
        x0 = (idx % cols) * w
        y0 = (idx // cols) * (h + bar)
        sheet.paste(Image.open(p_path).convert("RGB"), (x0, y0))
        draw.text((x0 + 12, y0 + h + 10), f"{label}  [{dress}]", fill=(255, 230, 95), font=font)
    sheet_out = os.path.join(SETS, "town_square_showcase_sheet.png")
    sheet.save(sheet_out)
    print("WROTE_SHOWCASE_SHEET", sheet_out)
    return sheet_out


def render_set(name):
    import bpy
    from mathutils import Vector

    bs = {}
    exec(open(os.path.join(PROJECT, "pipeline", "build_sets.py"), encoding="utf-8").read(), bs)
    ns = bs["build_one"](name, save=False)
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    marks = ns["get_marks"](name)
    cam = sc.camera
    bpy.context.view_layer.objects.active = cam
    cast, dressings = SHOTS[name]
    for preset, mk, dx, dy, pz, fc in cast:
        spec = dict(ns["PRESETS"][preset]); spec["face"] = fc
        base = Vector(marks[mk].matrix_world.translation)
        loc = base + Vector((dx, dy, 0))
        rig = ns["build_character"](f"P_{preset}", location=tuple(loc), **spec)
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
    if "--stitch-sheet" in sys.argv:
        stitch_showcase_sheet()
        sys.exit(0)
    import bpy
    from mathutils import Vector

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    want_sheet = "--sheet" in argv
    names = [a for a in argv if not a.startswith("-")] or globals().get("ONLY") or list(SHOTS)
    for n in names:
        print("rendered", render_set(n))
    if want_sheet and "town_square" in names:
        bs = {}
        exec(open(os.path.join(PROJECT, "pipeline", "build_sets.py"), encoding="utf-8").read(), bs)
        ns = bs["build_one"]("town_square", save=False)
        sc = bpy.context.scene
        bpy.context.view_layer.update()
        marks = ns["get_marks"]("town_square")
        cam = sc.camera
        bpy.context.view_layer.objects.active = cam

        showcase_cast = [
            ("Theo", "plaza_left", 0.0, 0.0, "wave", "grin"),
            ("Lily", "center", 0.0, 0.0, "arms_up", "laugh"),
            ("King", "plaza_right", 0.0, 0.0, "hands_hips", "confident"),
            ("Dad", "shop_front", 0.0, 0.0, "explain", "talk"),
            ("Mom", "bench_sit", 0.0, 0.0, "sit", "smile"),
            ("Noob", "portal_spot", 0.0, 0.0, "scared", "shocked"),
        ]
        for preset, mk, dx, dy, pz, fc in showcase_cast:
            spec = dict(ns["PRESETS"][preset]); spec["face"] = fc
            m_ob = marks[mk]
            base = Vector(m_ob.matrix_world.translation)
            seat_z = (float(m_ob.get("seat", 2.0)) - 2.0) if pz == "sit" else 0.0
            loc = base + Vector((dx, dy, seat_z))
            rig = ns["build_character"](f"SC_{preset}", location=tuple(loc), **spec)
            d = Vector(cam.location) - loc
            rig.rotation_euler = (0, 0, math.atan2(d.x, -d.y))
            ns["pose"](rig, pz, 1)
            ns["face"](rig, fc, 1)

        sc.frame_set(1)
        sc.render.resolution_percentage = 50
        sc.render.image_settings.file_format = 'PNG'
        for label, dress, cam_pos, look_at, lens in SHOWCASE_ANGLES:
            ns["apply_dressing"]("town_square", dress)
            cam.data.lens = lens
            cp = Vector(cam_pos)
            lk = Vector(look_at)
            cam.location = cp
            cam.rotation_euler = (lk - cp).to_track_quat('-Z', 'Y').to_euler()
            out_p = os.path.join(SETS, f"ts_{label}.png")
            sc.render.filepath = out_p
            bpy.ops.render.render(write_still=True)
        stitch_showcase_sheet()
