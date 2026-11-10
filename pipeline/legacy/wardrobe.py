"""
Wardrobe: extra hair styles, outfits and accessories for blocky_rig characters.

Load AFTER blocky_rig.py into the same namespace (it overrides build_character):
    ns = {}
    exec(open(".../pipeline/blocky_rig.py").read(), ns)
    exec(open(".../pipeline/wardrobe.py").read(), ns)
    rig = ns["build_character"]("Maya", outfit="hoodie", hair_style="long", lashes=True, ...)

hair_style : spiky | short | side_part | buzz | long | ponytail | bun | curly | cap | bald
outfit     : jacket | hoodie | tshirt | suit | uniform | dress
accessories: glasses | sunglasses | mustache
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

TOP = HEAD_CZ + HEAD_H / 2          # top of head (~5.31)


# ---------------------------------------------------------------- small helpers
def _bound(ob, rig, bone):
    bind(ob, rig, bone)
    return ob


def rbox(rig, coll, name, size, center, mat, bone, bevel=0.06, rot=(0, 0, 0), taper=None):
    ob = box(f"{rig.name}_{name}", coll, size, center, mat, bevel)
    if taper:  # (sx, sy) scale applied to top verts -> tapered skirt etc.
        for v in ob.data.vertices:
            if v.co.z > 0:
                v.co.x *= taper[0]; v.co.y *= taper[1]
    ob.rotation_euler = [math.radians(a) for a in rot]
    return _bound(ob, rig, bone)


def sphere_into(bm, center, r, subdiv=2):
    ret = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    bmesh.ops.translate(bm, vec=Vector(center), verts=ret["verts"])


def mesh_from_bm(rig, coll, name, bm, mat, bone, subsurf=0):
    me = bpy.data.meshes.new(f"{rig.name}_{name}")
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = _link(bpy.data.objects.new(f"{rig.name}_{name}", me), coll)
    if subsurf:
        m = ob.modifiers.new("Subsurf", "SUBSURF"); m.levels = m.render_levels = subsurf
    return _bound(ob, rig, bone)


def torus_obj(rig, coll, name, major, minor, center, mat, rot=(90, 0, 0)):
    me = bpy.data.meshes.new(f"{rig.name}_{name}")
    bm = bmesh.new()
    segs, ssegs = 32, 10
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ring = []
        for j in range(ssegs):
            b = 2 * math.pi * j / ssegs
            x = (major + minor * math.cos(b)) * math.cos(a)
            y = (major + minor * math.cos(b)) * math.sin(a)
            z = minor * math.sin(b)
            ring.append(bm.verts.new((x, y, z)))
        verts.append(ring)
    for i in range(segs):
        for j in range(ssegs):
            a, b = verts[i][j], verts[(i + 1) % segs][j]
            c, d = verts[(i + 1) % segs][(j + 1) % ssegs], verts[i][(j + 1) % ssegs]
            bm.faces.new((a, b, c, d))
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = _link(bpy.data.objects.new(f"{rig.name}_{name}", me), coll)
    ob.location = center
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


# ---------------------------------------------------------------- hair
def _hair_base(rig, coll, m, thick=0.34, fringe=True, sides=True, back=True, seed=1):
    rnd = random.Random(seed)
    rbox(rig, coll, "HairCap", (HEAD_W + 0.08, HEAD_D + 0.08, thick), (0, 0.02, TOP - 0.06), m, "head", 0.14)
    if fringe:
        for x in (-0.42, 0.0, 0.42):
            rbox(rig, coll, f"Fringe_{x:+.1f}", (0.48, 0.13, 0.2), (x, -HEAD_D / 2 - 0.02, TOP - 0.2), m, "head",
                 0.07, rot=(0, rnd.uniform(-8, 8), 0))
    if sides:
        for sx in (-1, 1):
            rbox(rig, coll, f"Sideburn_{sx}", (0.09, 0.5, 0.36), (sx * (HEAD_W / 2 + 0.025), 0.05, TOP - 0.34), m, "head", 0.04)
    if back:
        rbox(rig, coll, "HairBack", (HEAD_W + 0.06, 0.11, 0.55), (0, HEAD_D / 2 + 0.025, TOP - 0.36), m, "head", 0.05)


def build_hair(rig, coll, style, m, accent_m, seed=1):
    rnd = random.Random(seed)
    if style == "spiky":
        build_hair_spiky(rig, coll, m, seed)
    elif style == "short":
        _hair_base(rig, coll, m, seed=seed)
    elif style == "buzz":
        rbox(rig, coll, "HairCap", (HEAD_W + 0.04, HEAD_D + 0.04, 0.16), (0, 0.0, TOP - 0.02), m, "head", 0.07)
        _hair_base(rig, coll, m, thick=0.12, fringe=False, seed=seed)
    elif style == "side_part":
        _hair_base(rig, coll, m, fringe=False, seed=seed)
        rbox(rig, coll, "HairVolume", (HEAD_W - 0.05, HEAD_D * 0.85, 0.28), (0, 0.0, TOP + 0.13), m, "head", 0.13)
        rbox(rig, coll, "Swoosh", (0.95, 0.32, 0.34), (0.18, -HEAD_D / 2 + 0.06, TOP + 0.02), m, "head", 0.14, rot=(18, -10, 0))
        rbox(rig, coll, "SwooshSmall", (0.45, 0.2, 0.22), (-0.45, -HEAD_D / 2 + 0.01, TOP - 0.1), m, "head", 0.09, rot=(10, 12, 0))
    elif style == "long":
        _hair_base(rig, coll, m, fringe=False, sides=False, back=False, seed=seed)
        rbox(rig, coll, "Bangs", (HEAD_W + 0.04, 0.15, 0.2), (0, -HEAD_D / 2 - 0.03, TOP - 0.16), m, "head", 0.08)
        rbox(rig, coll, "LongBack", (HEAD_W + 0.2, 0.36, 2.1), (0, HEAD_D / 2 + 0.1, TOP - 0.92), m, "head", 0.16)
        for sx in (-1, 1):
            rbox(rig, coll, f"LongSide_{sx}", (0.22, HEAD_D * 0.75, 1.55), (sx * (HEAD_W / 2 + 0.1), 0.18, TOP - 0.7), m, "head", 0.1)
    elif style == "ponytail":
        _hair_base(rig, coll, m, seed=seed)
        bm = bmesh.new()
        pyramid(bm, (0, HEAD_D / 2 + 0.15, TOP - 0.12), (0, 0.85, -1.0), 0.42, 1.7, 8)
        sphere_into(bm, (0, HEAD_D / 2 + 0.15, TOP - 0.12), 0.36)
        mesh_from_bm(rig, coll, "Ponytail", bm, m, "head", subsurf=1)
        rbox(rig, coll, "HairTie", (0.34, 0.12, 0.34), (0, HEAD_D / 2 + 0.22, TOP - 0.22), accent_m, "head", 0.08)
    elif style == "bun":
        _hair_base(rig, coll, m, seed=seed)
        bm = bmesh.new()
        sphere_into(bm, (0, 0.18, TOP + 0.36), 0.42, 3)
        mesh_from_bm(rig, coll, "Bun", bm, m, "head")
        rbox(rig, coll, "HairTie", (0.5, 0.5, 0.1), (0, 0.18, TOP + 0.04), accent_m, "head", 0.04)
    elif style == "curly":
        rbox(rig, coll, "HairCap", (HEAD_W + 0.1, HEAD_D + 0.1, 0.36), (0, 0.03, TOP - 0.05), m, "head", 0.15)
        bm = bmesh.new()
        c = Vector((0, 0.06, TOP - 0.1))
        rx, ry, rz = HEAD_W / 2 + 0.18, HEAD_D / 2 + 0.18, 0.62
        n = 0
        while n < 46:
            th = rnd.uniform(0, 2 * math.pi)
            ph = rnd.uniform(0, math.pi * 0.62)
            p = c + Vector((rx * math.sin(ph) * math.cos(th), ry * math.sin(ph) * math.sin(th), rz * math.cos(ph)))
            if p.y < -0.38 and p.z < TOP - 0.02:
                continue
            sphere_into(bm, p, rnd.uniform(0.2, 0.28), 2)
            n += 1
        mesh_from_bm(rig, coll, "Curls", bm, m, "head")
    elif style == "cap":
        _hair_base(rig, coll, m, thick=0.2, fringe=False, seed=seed)
        rbox(rig, coll, "HatDome", (HEAD_W + 0.14, HEAD_D + 0.14, 0.44), (0, 0.02, TOP + 0.02), accent_m, "head", 0.2)
        rbox(rig, coll, "HatBrim", (HEAD_W * 0.92, 0.68, 0.07), (0, -HEAD_D / 2 - 0.28, TOP - 0.12), accent_m, "head", 0.03, rot=(8, 0, 0))
        rbox(rig, coll, "HatButton", (0.14, 0.14, 0.08), (0, 0.02, TOP + 0.25), accent_m, "head", 0.04)
    elif style == "bald":
        pass
    else:
        raise ValueError(f"unknown hair_style {style}")


# ---------------------------------------------------------------- outfits
def build_outfit(rig, coll, outfit, M):
    """Torso, arms, hips and legs. M = material dict."""
    sk = M["skin"]
    rbox(rig, coll, "Head", (HEAD_W, HEAD_D, HEAD_H), (0, 0, HEAD_CZ), sk, "head", 0.2)
    rbox(rig, coll, "Neck", (0.6, 0.6, 0.25), (0, 0, 4.05), sk, "neck", 0.05)
    long_sleeves = outfit in ("jacket", "hoodie", "suit", "uniform")
    top, top2 = M["top"], M["top2"]

    # --- torso
    if outfit == "jacket":
        rbox(rig, coll, "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), top, "spine", 0.07)
        rbox(rig, coll, "ShirtFront", (0.62, 0.05, 1.42), (0, -0.505, 3.2), top2, "spine", 0.02)
        rbox(rig, coll, "Hem", (2.04, 1.04, 0.14), (0, 0, 2.52), M["dark"], "spine", 0.04)
        rbox(rig, coll, "Collar", (1.2, 1.06, 0.16), (0, 0.02, 4.02), M["dark"], "spine", 0.05)
        for sx in (-1, 1):
            rbox(rig, coll, f"Lapel_{sx}", (0.13, 0.07, 1.42), (sx * 0.37, -0.515, 3.22), M["dark"], "spine", 0.025)
            rbox(rig, coll, f"Pocket_{sx}", (0.46, 0.035, 0.34), (sx * 0.68, -0.51, 3.42), top, "spine", 0.02)
            rbox(rig, coll, f"PocketFlap_{sx}", (0.5, 0.06, 0.09), (sx * 0.68, -0.525, 3.6), M["dark"], "spine", 0.02)
            rbox(rig, coll, f"PocketBtn_{sx}", (0.07, 0.04, 0.07), (sx * 0.68, -0.56, 3.56), M["accent"], "spine", 0.02)
        lg = torus_obj(rig, coll, "Logo", 0.15, 0.045, (0, -0.54, 3.05), M["accent"])
        _bound(lg, rig, "spine")
    elif outfit == "hoodie":
        rbox(rig, coll, "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), top, "spine", 0.08)
        rbox(rig, coll, "Pouch", (1.15, 0.06, 0.45), (0, -0.515, 2.86), M["dark"], "spine", 0.04)
        rbox(rig, coll, "Hem", (2.04, 1.04, 0.15), (0, 0, 2.52), M["dark"], "spine", 0.05)
        rbox(rig, coll, "Hood", (1.55, 0.6, 0.55), (0, 0.42, 4.1), top, "spine", 0.22)
        rbox(rig, coll, "Collar", (1.15, 1.05, 0.15), (0, 0.0, 4.02), M["dark"], "spine", 0.05)
        for sx in (-1, 1):
            rbox(rig, coll, f"String_{sx}", (0.05, 0.04, 0.45), (sx * 0.2, -0.53, 3.72), top2, "spine", 0.015)
            rbox(rig, coll, f"StringTip_{sx}", (0.08, 0.06, 0.08), (sx * 0.2, -0.54, 3.47), M["accent"], "spine", 0.02)
    elif outfit == "tshirt":
        rbox(rig, coll, "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), top, "spine", 0.07)
        rbox(rig, coll, "Collar", (0.8, 0.06, 0.12), (0, -0.505, 3.95), M["dark"], "spine", 0.03)
        rbox(rig, coll, "Hem", (2.03, 1.03, 0.1), (0, 0, 2.5), M["dark"], "spine", 0.03)
        lg = disk(f"{rig.name}_Print", coll, 0.32, 0.32, M["accent"])
        lg.location = (0, -0.506, 3.25)
        _bound(lg, rig, "spine")
        st = disk(f"{rig.name}_PrintStar", coll, 0.16, 0.16, top2, 5)
        st.location = (0, -0.51, 3.25)
        _bound(st, rig, "spine")
    elif outfit in ("suit", "uniform"):
        rbox(rig, coll, "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), top, "spine", 0.07)
        rbox(rig, coll, "Hem", (2.03, 1.03, 0.1), (0, 0, 2.5), M["dark"], "spine", 0.03)
        if outfit == "suit":
            rbox(rig, coll, "ShirtV", (0.5, 0.04, 0.85), (0, -0.505, 3.55), top2, "spine", 0.02)
            rbox(rig, coll, "Tie", (0.16, 0.05, 0.72), (0, -0.53, 3.45), M["accent"], "spine", 0.03)
            rbox(rig, coll, "TieKnot", (0.2, 0.06, 0.13), (0, -0.54, 3.88), M["accent"], "spine", 0.03)
            for sx in (-1, 1):
                rbox(rig, coll, f"Lapel_{sx}", (0.15, 0.06, 0.95), (sx * 0.2, -0.53, 3.55), M["dark"], "spine", 0.025, rot=(0, sx * 20, 0))
            for z in (2.95, 2.7):
                rbox(rig, coll, f"Btn_{z}", (0.08, 0.04, 0.08), (0, -0.525, z), M["dark"], "spine", 0.02)
            rbox(rig, coll, "PocketSquare", (0.25, 0.04, 0.1), (0.6, -0.51, 3.6), top2, "spine", 0.02)
        else:  # captain/uniform: double-breasted, gold trims
            rbox(rig, coll, "Collar", (1.2, 1.06, 0.18), (0, 0.02, 4.02), top, "spine", 0.05)
            for sx in (-1, 1):
                rbox(rig, coll, f"Lapel_{sx}", (0.18, 0.06, 0.55), (sx * 0.3, -0.52, 3.72), M["dark"], "spine", 0.025, rot=(0, -sx * 28, 0))
                for z in (3.35, 3.05, 2.75):
                    rbox(rig, coll, f"Btn_{sx}_{z}", (0.11, 0.05, 0.11), (sx * 0.38, -0.53, z), M["accent"], "spine", 0.03)
                rbox(rig, coll, f"Epaulette_{sx}", (0.9, 0.95, 0.08), (sx * 1.5, 0, 4.03), M["accent"], f"upper_arm.{'L' if sx > 0 else 'R'}", 0.03)
    elif outfit == "dress":
        rbox(rig, coll, "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), top, "spine", 0.08)
        rbox(rig, coll, "Neckline", (0.7, 0.05, 0.18), (0, -0.505, 3.88), sk, "spine", 0.04)
        rbox(rig, coll, "Waist", (2.04, 1.04, 0.14), (0, 0, 2.52), M["accent"], "spine", 0.04)
        rbox(rig, coll, "Bow", (0.3, 0.06, 0.16), (0, -0.54, 2.52), M["accent"], "spine", 0.05)
        rbox(rig, coll, "Skirt", (2.35, 1.35, 1.05), (0, 0, 1.95), top, "hips", 0.08, taper=(0.87, 0.78))
    else:
        raise ValueError(f"unknown outfit {outfit}")

    # --- arms
    for s, sx in (("L", 1), ("R", -1)):
        x = sx * 1.5
        if long_sleeves:
            rbox(rig, coll, f"UpperArm_{s}", (0.95, 0.95, 1.06), (x, 0, 3.47), top, f"upper_arm.{s}", 0.07)
            rbox(rig, coll, f"LowerArm_{s}", (0.93, 0.93, 0.66), (x, 0, 2.56), top, f"lower_arm.{s}", 0.06)
            cuff = top2 if outfit in ("suit",) else M["dark"]
            if outfit == "uniform":
                cuff = M["accent"]
            rbox(rig, coll, f"Cuff_{s}", (0.98, 0.98, 0.13), (x, 0, 2.22), cuff, f"lower_arm.{s}", 0.03)
        else:
            rbox(rig, coll, f"Sleeve_{s}", (0.99, 0.99, 0.52), (x, 0, 3.74), top, f"upper_arm.{s}", 0.07)
            rbox(rig, coll, f"SleeveHem_{s}", (1.01, 1.01, 0.08), (x, 0, 3.47), M["dark"] if outfit == "tshirt" else M["accent"], f"upper_arm.{s}", 0.03)
            rbox(rig, coll, f"UpperArm_{s}", (0.86, 0.86, 0.6), (x, 0, 3.17), sk, f"upper_arm.{s}", 0.06)
            rbox(rig, coll, f"LowerArm_{s}", (0.86, 0.86, 0.74), (x, 0, 2.5), sk, f"lower_arm.{s}", 0.06)
        rbox(rig, coll, f"Hand_{s}", (0.78, 0.78, 0.36), (x, 0, 1.96), sk, f"hand.{s}", 0.1)

    # --- hips & legs
    if outfit != "dress":
        rbox(rig, coll, "LowerTorso", (2.0, 1.0, 0.5), (0, 0, 2.2), M["pants"], "hips", 0.05)
        rbox(rig, coll, "Belt", (2.03, 1.03, 0.1), (0, 0, 2.38), M["belt"], "hips", 0.02)
    for s, sx in (("L", 1), ("R", -1)):
        x = sx * 0.5
        rbox(rig, coll, f"UpperLeg_{s}", (0.96, 0.96, 0.93), (x, 0, 1.53), M["pants"], f"upper_leg.{s}", 0.06)
        rbox(rig, coll, f"LowerLeg_{s}", (0.94, 0.94, 0.8), (x, 0, 0.65), M["pants"], f"lower_leg.{s}", 0.06)
        rbox(rig, coll, f"Shoe_{s}", (0.98, 1.22, 0.28), (x, -0.1, 0.16), M["shoes"], f"foot.{s}", 0.09)
        rbox(rig, coll, f"Sole_{s}", (1.0, 1.24, 0.08), (x, -0.1, 0.04), M["sole"], f"foot.{s}", 0.03)


# ---------------------------------------------------------------- face extras
def add_lashes(rig, coll):
    blk = get_mat("Face_Black", (0.03, 0.025, 0.03), 0.35)
    for s, sx in (("L", 1), ("R", -1)):
        eye = bpy.data.objects[f"{rig.name}_Eye_{s}"]
        for i, (a, b) in enumerate((((sx * 0.055, 0.085), (sx * 0.12, 0.13)), ((sx * 0.085, 0.05), (sx * 0.15, 0.075)))):
            st = stroke(f"{rig.name}_Lash_{s}{i}", coll, [a, b], blk, 0.014)
            st.parent = eye
            st.location = (0, -0.013, 0)
            st.visible_shadow = False


def add_glasses(rig, coll, frame_rgb=(0.08, 0.08, 0.1), dark=False):
    face = bpy.data.objects[f"{rig.name}_FaceRoot"]
    fm = get_mat(f"{rig.name}_GlassesFrame", frame_rgb, 0.3, metal=0.3)
    parts = []
    for sx in (-1, 1):
        r = torus_obj(rig, coll, f"Lens_{sx}", 0.165, 0.028, (0, 0, 0), fm)
        r.parent = face; r.location = (sx * 0.22, -0.035, 0.02)
        parts.append(r)
        arm = box(f"{rig.name}_GlassArm_{sx}", coll, (0.3, 0.03, 0.04), (0, 0, 0), fm, 0.01)
        arm.parent = face; arm.location = (sx * 0.52, -0.03, 0.06)
        side = box(f"{rig.name}_GlassSide_{sx}", coll, (0.03, 0.9, 0.04), (0, 0, 0), fm, 0.01)
        side.parent = face; side.location = (sx * (HEAD_W / 2 + 0.02), 0.45, 0.06)
        if dark:
            lens = disk(f"{rig.name}_DarkLens_{sx}", coll, 0.17, 0.15, get_mat("Sunglass_Lens", (0.04, 0.04, 0.06), 0.08, metal=0.5))
            lens.parent = face; lens.location = (sx * 0.22, -0.03, 0.02)
            lens.visible_shadow = False
    br = box(f"{rig.name}_GlassBridge", coll, (0.14, 0.03, 0.035), (0, 0, 0), fm, 0.01)
    br.parent = face; br.location = (0, -0.035, 0.07)


def add_mustache(rig, coll, rgb):
    face = bpy.data.objects[f"{rig.name}_FaceRoot"]
    mm = get_mat(f"{rig.name}_Mustache", rgb, 0.7)
    for sx in (-1, 1):
        b = box(f"{rig.name}_Mustache_{sx}", coll, (0.2, 0.05, 0.08), (0, 0, 0), mm, 0.035)
        b.parent = face
        b.location = (sx * 0.1, -0.025, -0.16)
        b.rotation_euler = (0, math.radians(sx * 12), 0)


# ---------------------------------------------------------------- public API (overrides blocky_rig)
def build_character(name="Hero", location=(0, 0, 0),
                    skin=(1.0, 0.86, 0.68), hair=(0.55, 0.32, 0.17),
                    hair_style="spiky", outfit="jacket",
                    top=(0.86, 0.22, 0.17), top2=(0.97, 0.96, 0.93),
                    pants=(0.16, 0.18, 0.26), shoes=(0.2, 0.2, 0.22),
                    accent=(0.98, 0.78, 0.2), eye_color=(0.18, 0.35, 0.75),
                    lashes=False, accessories=(), hair_seed=1,
                    jacket=None, shirt=None):
    if jacket is not None: top = jacket
    if shirt is not None: top2 = shirt
    scene = bpy.context.scene
    old = bpy.data.collections.get(name)
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)

    rig = build_armature(name, coll)
    rig["is_blocky_rig"] = True
    rig["recipe"] = str(dict(hair_style=hair_style, outfit=outfit, accessories=list(accessories), lashes=lashes))
    skin_m = get_mat(f"{name}_Skin", skin, 0.55)
    M = {
        "skin": skin_m,
        "top": get_mat(f"{name}_Top", top, 0.7),
        "top2": get_mat(f"{name}_Top2", top2, 0.65),
        "dark": get_mat(f"{name}_TopDark", tuple(c * 0.72 for c in top), 0.7),
        "pants": get_mat(f"{name}_Pants", pants, 0.75),
        "shoes": get_mat(f"{name}_Shoes", shoes, 0.5),
        "sole": get_mat("Sole_White", (0.95, 0.95, 0.95), 0.6),
        "accent": get_mat(f"{name}_Accent", accent, 0.35, metal=0.3),
        "belt": get_mat("Belt_Dark", (0.08, 0.07, 0.07), 0.5),
    }
    build_outfit(rig, coll, outfit, M)
    build_face(rig, coll, skin_m, eye_color)
    build_hair(rig, coll, hair_style, get_mat(f"{name}_Hair", hair, 0.6), M["accent"], hair_seed)
    if lashes:
        add_lashes(rig, coll)
    if "glasses" in accessories:
        add_glasses(rig, coll)
    if "sunglasses" in accessories:
        add_glasses(rig, coll, dark=True)
    if "mustache" in accessories:
        add_mustache(rig, coll, hair)
    rig.location = location
    refresh_drivers()
    return rig
