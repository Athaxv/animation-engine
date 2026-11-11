"""
Reusable Roblox R6 accessory assets (Phase 2).

Three zones, each with a verified attachment point and a declared clearance
contract that ``pipeline/characters/checks.py`` enforces:

  head_top  bound to the ``head`` bone, must sit above the brow line
  face      bound to the ``head`` bone, allowed inside the face window (worn on it)
  body      bound to ``spine``/``hips``, must sit outside the torso box

Nothing here replaces or rescales the R6 head; every piece is a child of an
existing bone so it follows locomotion and the expression atlas untouched.

Legacy headwear (``crown``, ``police``, ``cap``) and the legacy ``glasses`` /
``mustache`` extras stay in ``pipeline/roblox_rig.py`` and are untouched.
"""
import math

# accessory id -> (zone, bone, human note)
ACCESSORY_REGISTRY = {
    "beanie":       ("head_top", "head",  "ribbed knit beanie with a folded cuff"),
    "top_hat":      ("head_top", "head",  "tall formal top hat with a ribbon band"),
    "wizard_hat":   ("head_top", "head",  "wide-brim pointed wizard hat with a star"),
    "flower_crown": ("head_top", "head",  "ring of small flowers around the crown"),
    "headband":     ("head_top", "head",  "thin sport headband across the forehead"),
    "headphones":   ("head_top", "head",  "over-ear headphones, band over the crown"),
    "sunglasses":   ("face",     "head",  "dark wrap sunglasses"),
    "mask":         ("face",     "head",  "cloth face mask over nose and mouth"),
    "monocle":      ("face",     "head",  "single round monocle with a chain"),
    "eyepatch":     ("face",     "head",  "eye patch with a head strap"),
    "scarf":        ("body",     "spine", "knitted scarf wrapped at the neck"),
    "backpack":     ("body",     "spine", "two-strap backpack sitting on the back"),
    "satchel":      ("body",     "spine", "shoulder bag resting on the hip"),
    "cape":         ("body",     "spine", "long cape hanging from the shoulders"),
    "wings":        ("body",     "spine", "small pair of fairy wings behind the torso"),
    "amulet":       ("body",     "spine", "pendant on a cord at the chest"),
}

ACCESSORY_ZONES = ["head_top", "face", "body"]


def zone_of(acc_id):
    return ACCESSORY_REGISTRY[acc_id][0]


def build_accessories(K, rig, coll, acc_ids, colors=None, hair_rgb=(0.4, 0.2, 0.1)):
    """Build every accessory in ``acc_ids``. Returns a list of created objects."""
    colors = colors or {}
    strand = K.get("_strand")
    link = K["_link"]
    bind = K["bind"]
    new_mat = K["new_mat"]
    add_bump = K["add_bump"]
    rbox = K["rbox"]
    sphere = K["_sphere_mesh"]
    cylinder = K["_cyl_mesh"]
    torus_add = K["bpy"].ops.mesh.primitive_torus_add
    bsdf = K["_bsdf"]
    srgb = K["srgb"]
    HEAD_CZ = K["HEAD_CZ"]
    HEAD_R = K["HEAD_R"]
    HEAD_H = K["HEAD_H"]

    n = rig.name
    cz, R = HEAD_CZ, HEAD_R
    top_z = cz + HEAD_H / 2
    FY = -0.5

    made = []

    def emit(ob, bone):
        made.append(ob)
        bind(ob, rig, bone)
        return ob

    def mesh(name, me, loc, mat, bone, rot=(0, 0, 0), scale=(1, 1, 1)):
        ob = link(K["bpy"].data.objects.new(f"{n}_{name}", me), coll)
        ob.location = loc
        ob.rotation_euler = rot
        ob.scale = scale
        if not me.materials:
            me.materials.append(mat)
        return emit(ob, bone)

    def ball(name, r, loc, mat, bone, scale=None, segs=20):
        b = link(K["bpy"].data.objects.new(f"{n}_{name}", sphere(f"{n}_{name}", r, segs)), coll)
        b.location = loc
        if scale:
            b.scale = scale
        b.data.materials.append(mat)
        return emit(b, bone)

    def cyl(name, r1, r2, depth, loc, mat, bone, rot=(0, 0, 0), scale=None, segs=40, caps=True):
        ob = link(K["bpy"].data.objects.new(f"{n}_{name}", cylinder(f"{n}_{name}", r1, r2, depth, segs, caps)), coll)
        ob.location = loc
        ob.rotation_euler = rot
        if scale:
            ob.scale = scale
        ob.data.materials.append(mat)
        return emit(ob, bone)

    def torus(name, major, minor, loc, mat, bone, rot=(math.pi / 2, 0, 0), scale=None):
        torus_add(major_radius=major, minor_radius=minor, major_segments=40, minor_segments=8, location=loc,
                  rotation=rot)
        t = K["bpy"].context.active_object
        t.name = f"{n}_{name}"
        for c in t.users_collection:
            c.objects.unlink(t)
        coll.objects.link(t)
        t.data.materials.append(mat)
        if scale:
            t.scale = scale
        for p in t.data.polygons:
            p.use_smooth = True
        return emit(t, bone)

    def box(name, size, loc, mat, bone, bevel=0.04, rot=None):
        ob = rbox(f"{n}_{name}", coll, size, loc, mat, bevel)
        if rot:
            ob.rotation_euler = rot
        return emit(ob, bone)

    head_bone = "head"
    body_bone = "spine"

    for acc in acc_ids:
        if acc not in ACCESSORY_REGISTRY:
            raise KeyError(f"Unknown accessory {acc!r}; available: {sorted(ACCESSORY_REGISTRY)}")
        zone = ACCESSORY_REGISTRY[acc][0]

        # ---------------------------------------------------------- head_top
        if acc == "beanie":
            knit = add_bump(new_mat(f"{n}_Beanie", colors.get("beanie", (0.86, 0.28, 0.30)), 0.95, 0.15), 150, 0.7, 6, tint=0.12)
            cyl("BeanieDome", R + 0.03, R + 0.13, 0.62, (0, 0.01, top_z + 0.14), knit, head_bone, segs=48)
            cyl("BeanieCuff", R + 0.10, R + 0.12, 0.22, (0, 0.01, top_z + 0.10), knit, head_bone, segs=48)
            ball("BeanieBobble", 0.11, (0, 0.01, top_z + 0.50), knit, head_bone)

        elif acc == "top_hat":
            felt = new_mat(f"{n}_TopHat", colors.get("top_hat", (0.09, 0.09, 0.12)), 0.55, 0.35)
            band = new_mat(f"{n}_TopHatBand", colors.get("top_hat_band", (0.55, 0.10, 0.14)), 0.5, 0.4)
            cyl("TopHatBrim", 0.86, 0.86, 0.07, (0, 0.01, top_z + 0.14), felt, head_bone, segs=48)
            cyl("TopHatCrown", R + 0.02, R + 0.06, 0.92, (0, 0.01, top_z + 0.62), felt, head_bone, segs=48)
            cyl("TopHatBand", R + 0.05, R + 0.07, 0.16, (0, 0.01, top_z + 0.28), band, head_bone, segs=48)

        elif acc == "wizard_hat":
            cloth = new_mat(f"{n}_WizHat", colors.get("wizard_hat", (0.28, 0.20, 0.62)), 0.85, 0.2)
            brim = cyl("WizBrim", 1.05, 1.05, 0.06, (0, 0.01, top_z + 0.16), cloth, head_bone, segs=48)
            cyl("WizCone", R + 0.10, 0.02, 1.30, (0, 0.01, top_z + 0.78), cloth, head_bone, segs=24)
            gold = new_mat(f"{n}_WizStar", (1.0, 0.84, 0.30), 0.25, 0.6)
            bsdf(gold).inputs["Metallic"].default_value = 0.8
            b = bsdf_emissive(K, gold, (1.0, 0.84, 0.30), 1.4)
            star_pts = [(0.10 * (1 if k % 2 == 0 else 0.42) * math.sin(math.pi * k / 5),
                         0.10 * (1 if k % 2 == 0 else 0.42) * math.cos(math.pi * k / 5)) for k in range(10)]
            me, th = K["_flat_shape"](f"{n}_WizStarMesh", star_pts)
            ob = link(K["bpy"].data.objects.new(f"{n}_WizStar", me), coll)
            ob.location = (0, -R - 0.10, top_z + 0.72)
            ob.rotation_euler = (math.radians(90), 0, 0)
            me.materials.append(gold)
            so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = th
            emit(ob, head_bone)

        elif acc == "flower_crown":
            ring = add_bump(new_mat(f"{n}_Vine", (0.32, 0.60, 0.28), 0.9, 0.2), 200, 0.5, 4, tint=0.1)
            torus("FlowerVine", R + 0.04, 0.04, (0, 0, top_z + 0.02), ring, head_bone, rot=(0, 0, 0),
                  scale=(1.0, 1.0, 0.35))
            for k in range(10):
                a = 2 * math.pi * k / 10
                x, y = math.cos(a) * (R + 0.05), math.sin(a) * (R + 0.05)
                petal = (0.98, 0.52, 0.72) if k % 2 == 0 else (0.99, 0.87, 0.32)
                fm = new_mat(f"{n}_Flower{k}", petal, 0.7, 0.25)
                ball(f"Flower{k}", 0.135, (x, y, top_z + 0.06), fm, head_bone, scale=(1.0, 1.0, 0.62))
                core = new_mat(f"{n}_FlowerCore{k}", (1.0, 0.96, 0.72), 0.6, 0.3)
                ball(f"FlowerCore{k}", 0.055, (x * 1.02, y * 1.02, top_z + 0.10), core, head_bone,
                     scale=(1.0, 1.0, 0.6))

        elif acc == "headband":
            band = add_bump(new_mat(f"{n}_Headband", colors.get("headband", (0.20, 0.75, 0.92)), 0.8, 0.2),
                            300, 0.25, 4, tint=0.05)
            torus("HeadbandRing", R + 0.03, 0.085, (0, 0, cz + 0.38), band, head_bone, rot=(0, 0, 0),
                  scale=(1.0, 1.0, 0.62))

        elif acc == "headphones":
            shell = new_mat(f"{n}_HpShell", colors.get("headphones", (0.16, 0.17, 0.22)), 0.45, 0.4)
            pad = new_mat(f"{n}_HpPad", (0.10, 0.10, 0.12), 0.9, 0.1)
            torus("HpBand", R + 0.14, 0.06, (0, 0, cz + 0.30), shell, head_bone,
                  rot=(math.pi / 2, 0, 0), scale=(1.0, 1.0, 0.92))
            for sx in (-1, 1):
                cyl(f"HpCup_{sx}", 0.26, 0.26, 0.20, (sx * (R + 0.10), 0, cz + 0.02), shell, head_bone,
                    rot=(0, math.pi / 2, 0), segs=32)
                cyl(f"HpPad_{sx}", 0.20, 0.20, 0.07, (sx * (R + 0.01), 0, cz + 0.02), pad, head_bone,
                    rot=(0, math.pi / 2, 0), segs=32)

        # ------------------------------------------------------------- face
        elif acc == "sunglasses":
            frame = new_mat(f"{n}_SunFrame", colors.get("sunglasses", (0.10, 0.10, 0.12)), 0.2, 0.7, coat=0.5)
            lens = new_mat(f"{n}_SunLens", (0.06, 0.07, 0.10), 0.05, 0.9)
            for sx in (-1, 1):
                ey = -math.sqrt(max(R * R - 0.178 ** 2, 0.01)) - 0.055
                cyl(f"SunLens_{sx}", 0.175, 0.175, 0.035, (sx * 0.178, ey, cz + 0.155), lens, head_bone,
                    rot=(math.pi / 2, 0, 0), segs=28)
                cyl(f"SunRim_{sx}", 0.195, 0.195, 0.025, (sx * 0.178, ey + 0.005, cz + 0.155), frame, head_bone,
                    rot=(math.pi / 2, 0, 0), segs=28)
                box(f"SunArm_{sx}", (0.03, 0.52, 0.03), (sx * (R + 0.02), -0.30, cz + 0.19), frame, head_bone, 0.01)
            box("SunBridge", (0.14, 0.03, 0.03), (0, -R - 0.06, cz + 0.19), frame, head_bone, 0.01)

        elif acc == "mask":
            cloth = add_bump(new_mat(f"{n}_Mask", colors.get("mask", (0.90, 0.93, 0.97)), 0.95, 0.12), 220, 0.6, 6, tint=0.08)
            for k, (zc, w) in enumerate(((cz + 0.02, 0.94), (cz - 0.12, 0.94), (cz - 0.26, 0.86),
                                         (cz - 0.38, 0.72), (cz - 0.46, 0.54))):
                yy = -math.sqrt(max(R * R - (w / 2) ** 2, 0.01)) - 0.045
                box(f"MaskPly{k}", (w, 0.07, 0.14), (0, yy, zc), cloth, head_bone, 0.035)
            for sx in (-1, 1):
                box(f"MaskStrap_{sx}", (0.04, 0.62, 0.05), (sx * (R + 0.01), -0.24, cz + 0.04), cloth, head_bone, 0.01)

        elif acc == "monocle":
            gold = new_mat(f"{n}_MonoGold", (0.97, 0.78, 0.28), 0.2, 0.6)
            bsdf(gold).inputs["Metallic"].default_value = 1.0
            ey = -math.sqrt(max(R * R - 0.178 ** 2, 0.01)) - 0.07
            cyl("MonoRing", 0.165, 0.165, 0.03, (0.178, ey, cz + 0.155), gold, head_bone,
                rot=(math.pi / 2, 0, 0), segs=28, caps=False)
            cyl("MonoRingInner", 0.130, 0.130, 0.02, (0.178, ey - 0.01, cz + 0.155), gold, head_bone,
                rot=(math.pi / 2, 0, 0), segs=28, caps=False)
            # spectacle chain falling from the frame toward the jaw
            for k, (yy, zz) in enumerate(((-0.60, cz - 0.02), (-0.58, cz - 0.22), (-0.50, cz - 0.40))):
                ball(f"MonoChain{k}", 0.022, (0.30, yy, zz), gold, head_bone)

        elif acc == "eyepatch":
            black = new_mat(f"{n}_Patch", (0.05, 0.05, 0.06), 0.85, 0.15)
            ey = -math.sqrt(max(R * R - 0.178 ** 2, 0.01)) - 0.05
            box("PatchPly", (0.38, 0.06, 0.30), (-0.178, ey, cz + 0.155), black, head_bone, 0.09)
            torus("PatchStrap", R + 0.04, 0.028, (0, 0, cz + 0.22), black, head_bone,
                  rot=(0, 0, 0), scale=(1.0, 1.0, 0.5))

        # ------------------------------------------------------------- body
        elif acc == "scarf":
            knit = add_bump(new_mat(f"{n}_Scarf", colors.get("scarf", (0.82, 0.22, 0.24)), 0.95, 0.12), 180, 0.7, 6, tint=0.1)
            torus("ScarfWrap", 0.46, 0.16, (0, 0, cz - 0.56), knit, body_bone, rot=(0, 0, 0), scale=(1.0, 1.0, 0.9))
            box("ScarfTail", (0.30, 0.09, 0.90), (0.30, -0.56, cz - 1.30), knit, body_bone, 0.05)
            box("ScarfTailTip", (0.30, 0.09, 0.10), (0.30, -0.56, cz - 1.74), knit, body_bone, 0.04)

        elif acc == "backpack":
            bag = add_bump(new_mat(f"{n}_Pack", colors.get("backpack", (0.24, 0.44, 0.80)), 0.8, 0.25), 120, 0.3, 6, tint=0.1)
            strap = new_mat(f"{n}_PackStrap", tuple(c * 0.8 for c in colors.get("backpack", (0.24, 0.44, 0.80))), 0.85, 0.2)
            box("PackBody", (1.44, 0.56, 1.56), (0, 0.80, 3.10), bag, body_bone, 0.10)
            box("PackLid", (1.48, 0.60, 0.26), (0, 0.80, 3.92), strap, body_bone, 0.06)
            box("PackPocket", (0.86, 0.14, 0.62), (0, 1.10, 2.86), strap, body_bone, 0.05)
            for sx in (-1, 1):
                box(f"PackStrap_{sx}", (0.16, 0.08, 1.70), (sx * 0.62, -0.56, 3.10), strap, body_bone, 0.03)

        elif acc == "satchel":
            bag = add_bump(new_mat(f"{n}_Satchel", colors.get("satchel", (0.56, 0.36, 0.20)), 0.85, 0.2), 130, 0.4, 6, tint=0.12)
            strap = new_mat(f"{n}_SatchelStrap", (0.40, 0.26, 0.14), 0.9, 0.15)
            box("SatchelBody", (0.72, 0.44, 0.82), (1.28, 0.02, 1.72), bag, body_bone, 0.08)
            box("SatchelFlap", (0.74, 0.46, 0.16), (1.28, 0.02, 2.10), strap, body_bone, 0.05)
            # diagonal strap across the chest (rotation set before binding, so it is world-aligned)
            box("SatchelStrap", (0.14, 0.08, 1.84), (-0.10, -0.56, 3.10), strap, body_bone, 0.02,
                rot=(0, math.radians(-26), 0))

        elif acc == "cape":
            cloth = add_bump(new_mat(f"{n}_Cape", colors.get("cape", (0.42, 0.12, 0.62)), 0.9, 0.2), 110, 0.25, 5, tint=0.1)
            me = K["bpy"].data.meshes.new(f"{n}_CapeMesh")
            import bmesh
            bm = bmesh.new()
            bmesh.ops.create_grid(bm, x_segments=8, y_segments=10, size=1.0)
            for v in bm.verts:
                # the grid is flat in XY, so its Y is the "down the back" axis:
                # 0 at the shoulders, 1 at the hem.
                t = (v.co.y + 1.0) * 0.5
                v.co.x *= 1.05 + 0.30 * t
                v.co.y = 0.60 + 0.24 * t
                v.co.z = 4.02 - 1.95 * t
            bm.to_mesh(me); bm.free()
            for p in me.polygons:
                p.use_smooth = True
            me.materials.append(cloth)
            ob = link(K["bpy"].data.objects.new(f"{n}_Cape", me), coll)
            so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.05
            emit(ob, body_bone)
            box("CapeCollar", (1.34, 0.30, 0.20), (0, 0.42, 4.02), cloth, body_bone, 0.06)

        elif acc == "wings":
            glow = new_mat(f"{n}_Wing", colors.get("wings", (0.72, 0.92, 1.0)), 0.35, 0.6)
            b = bsdf(glow)
            if "Emission Strength" in b.inputs:
                b.inputs["Emission Color"].default_value = (*srgb(colors.get("wings", (0.72, 0.92, 1.0))), 1.0)
                b.inputs["Emission Strength"].default_value = 0.45
            # each wing is an upper teardrop plus a smaller lower lobe, both flattened
            # along Y so they stay thin against the back
            for sx in (-1, 1):
                upper = link(K["bpy"].data.objects.new(f"{n}_WingUp_{sx}", sphere(f"{n}_WingUp_{sx}", 0.60, 24)), coll)
                upper.location = (sx * 0.78, 0.94, 3.78)
                upper.scale = (0.62, 0.09, 1.18)
                upper.rotation_euler = (0.0, math.radians(sx * -20), math.radians(sx * 14))
                upper.data.materials.append(glow)
                emit(upper, body_bone)

                lower = link(K["bpy"].data.objects.new(f"{n}_WingLow_{sx}", sphere(f"{n}_WingLow_{sx}", 0.40, 20)), coll)
                lower.location = (sx * 0.62, 0.96, 2.98)
                lower.scale = (0.60, 0.08, 0.92)
                lower.rotation_euler = (0.0, math.radians(sx * -26), math.radians(sx * 10))
                lower.data.materials.append(glow)
                emit(lower, body_bone)

        elif acc == "amulet":
            cord = new_mat(f"{n}_Cord", (0.28, 0.22, 0.14), 0.9, 0.15)
            gold = new_mat(f"{n}_AmuletGold", (1.0, 0.80, 0.28), 0.2, 0.6)
            bsdf(gold).inputs["Metallic"].default_value = 1.0
            gem = new_mat(f"{n}_AmuletGem", colors.get("amulet", (0.24, 0.86, 0.72)), 0.15, 0.8)
            # V-shaped cord lying on the chest front, not buried inside the torso
            for sx in (-1, 1):
                box(f"AmuletCord_{sx}", (0.035, 0.035, 0.46), (sx * 0.14, FY - 0.055, 3.72),
                    cord, body_bone, 0.012, rot=(0, math.radians(sx * 22), 0))
            cyl("AmuletMount", 0.14, 0.14, 0.05, (0, FY - 0.06, 3.50), gold, body_bone,
                rot=(math.pi / 2, 0, 0), segs=20)
            ball("AmuletGem", 0.11, (0, FY - 0.10, 3.50), gem, body_bone, scale=(1.0, 0.7, 1.25))

    return made


def bsdf_emissive(K, mat, rgb, strength):
    b = K["_bsdf"](mat)
    if "Emission Color" in b.inputs:
        b.inputs["Emission Color"].default_value = (*K["srgb"](rgb), 1.0)
        b.inputs["Emission Strength"].default_value = strength
    return b
