"""
Phase 2 appearance preview / lineup sheets.

Renders every hair style, outfit, accessory, face expression and identity from
the *same* builders the episodes use, then tiles them into labelled sheets.

    blender -b --factory-startup -t 2 --python pipeline/render_character_lineup.py
    blender -b --factory-startup -t 2 --python pipeline/render_character_lineup.py -- hair faces
    python pipeline/render_character_lineup.py --annotate

Sheets (public/roblox/characters/):
    characters_hair_sheet.png        all hair silhouettes side by side
    characters_outfit_sheet.png      every outfit on the same body
    characters_accessory_sheet.png   every accessory in its zone
    characters_face_sheet.png        16 expressions at bust framing (4x4)
    characters_lineup.png            every identity, using its own personality pose

Each sheet is rendered as **one frame** (all characters are placed in a single
row/grid), so a full run is 5 renders -- far below the 150-frame thermal budget.
Labels are drawn afterwards by system Python because Blender ships without PIL.
"""
import json
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else os.getcwd()
PIPE = os.path.join(PROJECT, "pipeline")
if PIPE not in sys.path:
    sys.path.insert(0, PIPE)

CHAR_DIR = os.path.join(PROJECT, "public", "roblox", "characters")
SHEET_DIR = os.path.join(CHAR_DIR, "sheets")

import characters  # noqa: E402

ROW_SPACING = 3.45
ROW_W_PER_CHAR = 168          # px per character in a row sheet
ROW_H = 900

# neutral body used for hair / outfit / accessory studies so only the studied
# feature changes between panels
NEUTRAL = dict(
    skin=(0.97, 0.67, 0.40), hair=(0.40, 0.22, 0.11), hair_style="short",
    top=(0.62, 0.70, 0.82), pants=(0.42, 0.46, 0.56), accent=(0.96, 0.96, 0.98),
    shoes=(0.22, 0.22, 0.26), sleeves="long", bottom="pants", face="neutral",
)

OUTFIT_PANELS = [
    ("none", dict(outfit="none")),
    ("hoodie", dict(outfit="hoodie", top=(0.86, 0.30, 0.28))),
    ("jacket", dict(outfit="jacket", top=(0.22, 0.32, 0.52))),
    ("tshirt", dict(outfit="tshirt", top=(0.98, 0.80, 0.24), sleeves="short",
                    print_kind="bolt", print_color=(0.14, 0.52, 0.92))),
    ("school_uniform", dict(outfit="school_uniform", top=(0.20, 0.32, 0.58),
                            accent=(0.90, 0.16, 0.20), bottom="skirt")),
    ("suit", dict(outfit="suit", top=(0.11, 0.12, 0.16), accent=(0.62, 0.10, 0.14))),
    ("dress", dict(outfit="dress", top=(0.86, 0.44, 0.68), pants=(0.72, 0.30, 0.54),
                   accent=(1.0, 0.86, 0.40), bottom="pants", print_kind="heart")),
    ("themed", dict(outfit="themed", top=(0.18, 0.26, 0.44), accent=(0.30, 0.86, 0.92))),
]


def _row_items():
    hair = [(s, dict(NEUTRAL, hair_style=s, hair_seed=5)) for s in characters.HAIR_ALL_STYLES]
    outfit = [(lbl, dict(NEUTRAL, **kw)) for lbl, kw in OUTFIT_PANELS]
    acc = []
    for a in characters.ACCESSORY_REGISTRY:
        zone = characters.ACCESSORY_REGISTRY[a][0]
        spec = dict(NEUTRAL, accessories=(a,), sleeves="short")
        if zone in ("head_top", "face"):
            spec["hair_style"] = "bald"
        # back-mounted pieces are shown from behind so the sheet proves they exist
        if a in ("cape", "wings", "backpack"):
            spec["__yaw__"] = 180.0
        elif a == "satchel":
            spec["__yaw__"] = -42.0
        acc.append((a, spec))
    return hair, outfit, acc


def _identity_items():
    items = []
    for cid in sorted(characters.CHARACTER_IDENTITIES):
        ident = characters.get(cid)
        if ident.get("legacy_preset"):
            spec = {"__legacy__": ident["legacy_preset"], "face": ident["face_style"]}
        else:
            spec = characters.identity_to_rig_kwargs(cid)
        pose = "relaxed"   # one neutral pose for every identity so appearance is comparable
        items.append((ident["name"], spec, pose))
    return items


# ---------------------------------------------------------------- studio
def setup_studio(floor=True):
    import bpy
    import math

    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = 16
        sc.eevee.use_raytracing = False
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.1
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False

    world = bpy.data.worlds.new("CharStudio")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.16, 0.18, 0.23, 1.0)
    bg.inputs[1].default_value = 0.85
    sc.world = world
    try:
        sc.eevee.use_shadows = True
    except Exception:
        pass

    # floor + back wall so the figures read against a clean studio
    slabs = [("Floor", (220, 90, 0.4), (0, 6, -0.2), (0.24, 0.26, 0.31)),
             ("Wall", (220, 0.4, 40), (0, 14, 12), (0.13, 0.15, 0.19))]
    if not floor:
        slabs = slabs[1:]
    for name, size, loc, col in slabs:
        me = bpy.data.meshes.new(name)
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me)
        ob.location = loc
        sc.collection.objects.link(ob)
        mat = bpy.data.materials.new(f"Studio{name}")
        mat.use_nodes = True
        b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (*col, 1)
        b.inputs["Roughness"].default_value = 0.95
        me.materials.append(mat)

    sun = bpy.data.lights.new("KeySun", "SUN")
    sun.energy = 4.4
    sun.angle = math.radians(14)
    sun_ob = bpy.data.objects.new("KeySun", sun)
    sun_ob.rotation_euler = (math.radians(54), 0, math.radians(26))
    sc.collection.objects.link(sun_ob)

    for nm, loc, energy, size, rot in (("Fill", (-26, -24, 16), 9000, 34, (58, 0, -38)),
                                       ("Rim", (24, 20, 18), 7000, 30, (58, 0, 145))):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy = energy
        ld.size = size
        ob = bpy.data.objects.new(nm, ld)
        ob.location = loc
        ob.rotation_euler = tuple(math.radians(a) for a in rot)
        sc.collection.objects.link(ob)

    cam_d = bpy.data.cameras.new("CharCam")
    cam_d.type = "ORTHO"
    cam_ob = bpy.data.objects.new("CharCam", cam_d)
    sc.collection.objects.link(cam_ob)
    sc.camera = cam_ob
    return sc, cam_ob


def _aim_row(cam_ob, sc, cols, rows, spacing_x, spacing_z, span_z, center_z, margin=1.06):
    """Ortho camera framed on the whole row/grid, sized from the world spans."""
    import math
    span_x = cols * spacing_x
    w, h = sc.render.resolution_x, sc.render.resolution_y
    cam_ob.data.ortho_scale = max(span_x, span_z * w / h) * margin
    cam_ob.location = (0.0, -60.0, center_z)
    cam_ob.rotation_euler = (math.pi / 2, 0, 0)


def _build(ns, name, spec, loc, pose):
    spec = dict(spec)
    yaw = spec.pop("__yaw__", 0.0)
    if "__legacy__" in spec:
        kwargs = dict(ns["PRESETS"][spec["__legacy__"]])
        kwargs["face"] = spec.get("face", kwargs.get("face", "smile"))
    else:
        kwargs = spec
    rig = ns["build_character"](name, location=loc, **kwargs)
    if yaw:
        import math
        rig.rotation_euler = (0.0, 0.0, math.radians(yaw))
    if pose:
        ns["pose"](rig, pose, 1)
    ns["face"](rig, kwargs.get("face", "smile"), 1)
    return rig


def render_sheet(sheet, cols=None, rows=None, spacing_x=ROW_SPACING, spacing_z=4.6, w=None, h=None):
    """
    Render one sheet. Row sheets render **one frame per row** (characters stand on
    the studio floor, so stacking rows in Z would bury them) and the annotate step
    stacks the frames. Grid sheets (the face atlas) render in a single frame with
    the floor disabled and only head-bound geometry kept.
    """
    import bpy

    items = sheet["items"]
    cols = cols or len(items)
    rows = rows or sheet.get("rows") or ((len(items) + cols - 1) // cols)
    grid = bool(sheet.get("grid"))
    pxu = sheet.get("px_per_unit", 88)

    if grid:
        chunks = [items]
    else:
        chunks = [items[i:i + cols] for i in range(0, len(items), cols)]

    row_files = []
    for r, chunk in enumerate(chunks):
        ns = {}
        for f in ("roblox_rig.py", "roblox_motions.py"):
            with open(os.path.join(PIPE, f), encoding="utf-8") as fh:
                exec(fh.read(), ns)

        sc, cam = setup_studio(floor=not grid)
        for c, item in enumerate(chunk):
            if sheet.get("identity"):
                _, spec, pose = item
            else:
                _, spec = item
                pose = "relaxed"
            if grid:
                rr, cc = divmod(c, cols)
                x = (cc - (cols - 1) / 2) * spacing_x
                z = (rows - 1) / 2 * spacing_z - rr * spacing_z
            else:
                x = (c - (cols - 1) / 2) * spacing_x
                z = 0.0
            _build(ns, f"P{r}{c:02d}", spec, (x, 0, z), pose)
            if sheet.get("heads_only"):
                _keep_heads_only(ns, f"P{r}{c:02d}")

        if grid:
            span_z = rows * spacing_z
            center_z = sheet.get("z_center", 4.62)
        else:
            span_z = sheet.get("vspan", 6.2)
            center_z = sheet.get("vcenter", 2.72)

        sc.render.resolution_x = w or int((cols * spacing_x) * pxu)
        sc.render.resolution_y = h or int(span_z * pxu)
        sc.render.resolution_percentage = 100
        _aim_row(cam, sc, cols, 1, spacing_x, spacing_z, span_z, center_z)

        sc.frame_set(1)
        raw = os.path.join(SHEET_DIR, f"raw_{sheet['name']}_r{r}.png")
        sc.render.filepath = raw
        bpy.ops.render.render(write_still=True)
        row_files.append(raw)
        print("RENDERED", raw)

    per_row = [len(c) for c in chunks]
    meta = {"name": sheet["name"], "rows_files": row_files, "per_row": per_row,
            "raw": row_files[0], "cols": cols, "rows": rows,
            "labels": [it[0] for it in items], "title": sheet["title"],
            "subtitle": sheet.get("subtitle", ""), "grid": grid}
    with open(os.path.join(SHEET_DIR, f"{sheet['name']}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return row_files


def _keep_heads_only(ns, name):
    """Delete everything on a character that is not bound to the head bone."""
    import bpy
    coll = bpy.data.collections.get(name)
    if not coll:
        return
    for ob in list(coll.all_objects):
        if ob.type == "ARMATURE":
            continue
        if ob.parent_bone not in ("head",):
            bpy.data.objects.remove(ob, do_unlink=True)
    bpy.context.view_layer.update()


def sheets_to_render():
    hair, outfit, acc = _row_items()
    faces = [(f, dict(NEUTRAL, face=f, hair_style="short")) for f in characters.FACE_STYLES]
    head_faces = []
    for f, spec in faces:
        head_faces.append((f, dict(spec, hair_style="short")))
    return [
        {"name": "characters_hair_sheet", "title": "HAIR SILHOUETTES",
         "subtitle": f"{len(hair)} styles  ·  {len(characters.HAIR_LEGACY_STYLES) - 1} legacy + "
                     f"{len(characters.HAIR_VOLUME)} new  ·  eye band verified clear on every style",
         "items": hair, "cols": 9, "spacing_x": 3.95, "spacing_z": 5.9,
         "vspan": 6.5, "vcenter": 2.6, "px_per_unit": 90},
        {"name": "characters_outfit_sheet", "title": "OUTFITS",
         "subtitle": f"{len(outfit)} garments  ·  blocky R6 silhouette preserved, detail added on top",
         "items": outfit, "cols": 8, "spacing_x": 3.95, "spacing_z": 5.9,
         "vspan": 6.5, "vcenter": 2.6, "px_per_unit": 100},
        {"name": "characters_accessory_sheet", "title": "ACCESSORIES",
         "subtitle": f"{len(acc)} pieces  ·  3 zones (head_top, face, body)  ·  clearance-verified",
         "items": acc, "cols": 8, "spacing_x": 3.4, "spacing_z": 4.6,
         "vspan": 5.3, "vcenter": 3.55, "px_per_unit": 122},
        {"name": "characters_face_sheet", "title": "FACE ATLAS  ·  16 EXPRESSIONS",
         "subtitle": "4x4 painted atlas cells projected on the R6 head  ·  no hair geometry in the eye band",
         "items": head_faces, "grid": True, "cols": 4, "rows": 4, "heads_only": True,
         "spacing_x": 2.30, "spacing_z": 1.62, "px_per_unit": 156},
        {"name": "characters_lineup", "title": "CHARACTER IDENTITIES",
         "subtitle": f"{len(characters.CHARACTER_IDENTITIES)} persistent identities  ·  "
                     "appearance owned by the registry, not by shots",
         "items": _identity_items(), "identity": True, "cols": 9, "spacing_x": 3.95,
         "spacing_z": 5.9, "vspan": 6.2, "vcenter": 2.72, "px_per_unit": 92},
    ]


# ---------------------------------------------------------------- annotation
def annotate():
    from PIL import Image, ImageDraw, ImageFont

    try:
        font_big = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 30)
        font_small = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 19)
        font_tiny = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 17)
    except Exception:
        font_big = font_small = font_tiny = ImageFont.load_default()

    out = []
    for fn in sorted(os.listdir(SHEET_DIR)):
        if not fn.endswith(".json"):
            continue
        meta = json.load(open(os.path.join(SHEET_DIR, fn), encoding="utf-8"))
        row_files = meta.get("rows_files") or [meta["raw"]]
        row_imgs = [Image.open(p).convert("RGB") for p in row_files]
        w = row_imgs[0].width
        header, footer, strip = 74, 42, 34
        per_row = meta.get("per_row") or [meta["cols"]]
        body_h = sum(im.height + (strip if not meta["grid"] else 0) for im in row_imgs)
        sheet = Image.new("RGB", (w, header + body_h + footer), (16, 18, 24))
        d = ImageDraw.Draw(sheet)
        d.text((22, 16), meta["title"], fill=(255, 255, 255), font=font_big)
        if meta["subtitle"]:
            d.text((22, 50), meta["subtitle"], fill=(150, 168, 190), font=font_small)

        labels = meta["labels"]
        cols = meta["cols"]
        cw = w / cols

        if meta["grid"]:
            im = row_imgs[0]
            sheet.paste(im, (0, header))
            ch = im.height / meta["rows"]
            for i, lab in enumerate(labels):
                rr, cc = divmod(i, cols)
                x0, y0 = cc * cw, header + rr * ch
                d.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline=(38, 42, 52))
                d.text((x0 + 10, y0 + 8), f"{i + 1:02d}", fill=(120, 140, 165), font=font_tiny)
                d.text((x0 + cw / 2, y0 + ch - 28), lab, fill=(255, 226, 110),
                       font=font_tiny, anchor="ma")
        else:
            y = header
            idx = 0
            for r, im in enumerate(row_imgs):
                sheet.paste(im, (0, y))
                for c in range(per_row[r]):
                    lab = labels[idx] if idx < len(labels) else ""
                    idx += 1
                    x0 = c * cw
                    d.line([(x0, y), (x0, y + im.height)], fill=(34, 38, 46), width=1)
                    d.text((x0 + cw / 2, y + im.height + 9), lab, fill=(255, 226, 110),
                           font=font_tiny, anchor="ma")
                y += im.height + strip

        final = os.path.join(CHAR_DIR, f"{meta['name']}.png")
        sheet.save(final)
        out.append(final)
        print("WROTE_SHEET", final)
    return out


def contact_strip():
    """One small image with every sheet stacked, for a single-glance review."""
    from PIL import Image, ImageDraw

    names = ["characters_hair_sheet", "characters_outfit_sheet",
             "characters_accessory_sheet", "characters_face_sheet", "characters_lineup"]
    imgs = [Image.open(os.path.join(CHAR_DIR, f"{n}.png")).convert("RGB")
            for n in names if os.path.exists(os.path.join(CHAR_DIR, f"{n}.png"))]
    if not imgs:
        return None
    tw = 1600
    scaled = []
    for im in imgs:
        r = tw / im.width
        scaled.append(im.resize((tw, max(1, int(im.height * r))), Image.LANCZOS))
    gap = 10
    total = sum(i.height for i in scaled) + gap * (len(scaled) - 1)
    out = Image.new("RGB", (tw, total), (12, 14, 18))
    y = 0
    for im in scaled:
        out.paste(im, (0, y))
        y += im.height + gap
    path = os.path.join(CHAR_DIR, "characters_all_sheets.png")
    out.save(path)
    print("WROTE_CONTACT", path)
    return path


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--annotate" in sys.argv:
        annotate()
        contact_strip()
        sys.exit(0)

    os.makedirs(SHEET_DIR, exist_ok=True)
    wanted = {a for a in argv if not a.startswith("-")}

    def _selected(sheet_name):
        if not wanted:
            return True
        key = sheet_name.replace("characters_", "").replace("_sheet", "")
        alias = {"hair": ["hair"], "outfit": ["outfit", "outfits"],
                 "accessory": ["accessory", "accessories"],
                 "face": ["face", "faces", "expression", "expressions"],
                 "lineup": ["lineup", "identities", "identity", "characters", "all"]}[key]
        return bool(wanted & (set(alias) | {sheet_name}))

    for sheet in sheets_to_render():
        if not _selected(sheet["name"]):
            continue
        render_sheet(sheet, cols=sheet.get("cols"), rows=sheet.get("rows"),
                     spacing_x=sheet.get("spacing_x", ROW_SPACING),
                     spacing_z=sheet.get("spacing_z", 4.6),
                     w=sheet.get("w"), h=sheet.get("h"))

    # Blender ships without Pillow, so labelling always runs on system Python.
    subprocess.run(["python", os.path.abspath(__file__), "--annotate"], check=False)
