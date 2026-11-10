"""
Blocky character rig generator (Roblox-like stylized, not Roblox assets).

Usage inside Blender (via MCP or Text Editor):
    ns = {}
    exec(open(r"<path>/pipeline/blocky_rig.py").read(), ns)
    rig = ns["build_character"]("Hero", location=(0,0,0), jacket=(0.8,0.1,0.08))
    ns["set_expression"](rig, "surprised", frame=10)
    ns["talk"](rig, start=10, end=60)

Units: ~1 unit = 1 Roblox stud. Character is ~5.6 units tall. Front faces -Y.
"""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix


# ---------------------------------------------------------------- helpers
def srgb(c):
    """sRGB 0-1 tuple -> linear (Blender base color)."""
    f = lambda x: x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c)


def get_mat(name, rgb_srgb, rough=0.55, emit=0.0, metal=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    col = (*srgb(rgb_srgb), 1.0)
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = col
        b.inputs["Emission Strength"].default_value = emit
    m.diffuse_color = col
    return m


def _link(ob, coll):
    coll.objects.link(ob)
    return ob


def box(name, coll, size, center, mat, bevel=0.06, segs=3):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bm.to_mesh(me); bm.free()
    ob = _link(bpy.data.objects.new(name, me), coll)
    ob.location = center
    me.materials.append(mat)
    if bevel:
        md = ob.modifiers.new("Bevel", "BEVEL"); md.width = bevel; md.segments = segs
        md.limit_method = 'NONE'
        for p in me.polygons: p.use_smooth = True
        try:
            ob.modifiers.new("Smooth", "WEIGHTED_NORMAL")
        except Exception:
            pass
    return ob


def disk(name, coll, rx, rz, mat, segs=32):
    """Flat ellipse in the XZ plane (faces -Y)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=segs)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx, 0.0, v.co.y * rz))
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    return _link(bpy.data.objects.new(name, me), coll)


def poly(name, coll, pts_xz, mat):
    """Flat filled polygon in the XZ plane."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x, 0.0, z)) for x, z in pts_xz]
    bm.faces.new(vs)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    return _link(bpy.data.objects.new(name, me), coll)


def stroke(name, coll, pts_xz, mat, width=0.017):
    """Rounded line drawn on the face (bezier curve in XZ plane)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = '3D'
    cu.bevel_depth = width
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts_xz) - 1)
    for bp, (x, z) in zip(sp.bezier_points, pts_xz):
        bp.co = (x, 0.0, z)
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.materials.append(mat)
    return _link(bpy.data.objects.new(name, cu), coll)


def pyramid(bm, base_center, direction, radius, height, segs=5, twist=0.0):
    """Add a cone/pyramid into bm pointing along direction."""
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                radius1=radius, radius2=0.0, depth=height)
    d = Vector(direction).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    tw = Matrix.Rotation(twist, 4, 'Z')
    # cone is centred on origin: shift so base sits at base_center
    m = Matrix.Translation(Vector(base_center)) @ rot @ tw @ Matrix.Translation((0, 0, height / 2))
    bmesh.ops.transform(bm, matrix=m, verts=ret["verts"])


def add_prop(rig, name, value, lo, hi, desc=""):
    rig[name] = value
    try:
        rig.id_properties_ui(name).update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=desc)
    except Exception:
        pass


def drive(ob, path, index, expr, rig, props):
    fc = ob.driver_add(path, index) if index is not None else ob.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    for p in props:
        v = d.variables.new()
        v.name = p
        v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'OBJECT'
        v.targets[0].id = rig
        v.targets[0].data_path = f'["{p}"]'
    d.expression = expr
    return fc


# ---------------------------------------------------------------- skeleton
BONES = {
    # name: (head, tail, parent)
    "root":        ((0, 0, 0),       (0, 1.6, 0),      None),
    "hips":        ((0, 0, 2.0),     (0, 0, 2.45),     "root"),
    "spine":       ((0, 0, 2.45),    (0, 0, 4.0),      "hips"),
    "neck":        ((0, 0, 4.0),     (0, 0, 4.12),     "spine"),
    "head":        ((0, 0, 4.12),    (0, 0, 5.4),      "neck"),
    "upper_arm.L": ((1.5, 0, 3.72),  (1.5, 0, 2.92),   "spine"),
    "lower_arm.L": ((1.5, 0, 2.92),  (1.5, 0, 2.12),   "upper_arm.L"),
    "hand.L":      ((1.5, 0, 2.12),  (1.5, 0, 1.8),    "lower_arm.L"),
    "upper_arm.R": ((-1.5, 0, 3.72), (-1.5, 0, 2.92),  "spine"),
    "lower_arm.R": ((-1.5, 0, 2.92), (-1.5, 0, 2.12),  "upper_arm.R"),
    "hand.R":      ((-1.5, 0, 2.12), (-1.5, 0, 1.8),   "lower_arm.R"),
    "upper_leg.L": ((0.5, 0, 2.0),   (0.5, -0.02, 1.07), "hips"),
    "lower_leg.L": ((0.5, -0.02, 1.07), (0.5, 0, 0.22), "upper_leg.L"),
    "foot.L":      ((0.5, 0, 0.22),  (0.5, -0.55, 0.1), "lower_leg.L"),
    "upper_leg.R": ((-0.5, 0, 2.0),  (-0.5, -0.02, 1.07), "hips"),
    "lower_leg.R": ((-0.5, -0.02, 1.07), (-0.5, 0, 0.22), "upper_leg.R"),
    "foot.R":      ((-0.5, 0, 0.22), (-0.5, -0.55, 0.1), "lower_leg.R"),
    # IK controls
    "foot_ik.L":   ((0.5, 0, 0.22),  (0.5, -0.55, 0.1), "root"),
    "foot_ik.R":   ((-0.5, 0, 0.22), (-0.5, -0.55, 0.1), "root"),
    "knee_pole.L": ((0.5, -3.0, 1.07), (0.5, -3.4, 1.07), "root"),
    "knee_pole.R": ((-0.5, -3.0, 1.07), (-0.5, -3.4, 1.07), "root"),
}
DEFORM = [b for b in BONES if not (b.startswith("foot_ik") or b.startswith("knee_pole") or b == "root")]


def build_armature(name, coll):
    arm = bpy.data.armatures.new(name + "_Armature")
    rig = _link(bpy.data.objects.new(name, arm), coll)
    arm.display_type = 'STICK'
    rig.show_in_front = True
    vl = bpy.context.view_layer
    vl.update()
    for o in list(vl.objects):
        if o is not None:
            o.select_set(False)
    vl.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    for bn, (h, t, p) in BONES.items():
        b = eb.new(bn)
        b.head, b.tail = h, t
        b.roll = 0.0
        if p:
            b.parent = eb[p]
            b.use_connect = False
        b.use_deform = False
    bpy.ops.object.mode_set(mode='POSE')
    # leg IK
    for s in "LR":
        pb = rig.pose.bones["lower_leg." + s]
        c = pb.constraints.new("IK")
        c.target = rig; c.subtarget = "foot_ik." + s
        c.pole_target = rig; c.pole_subtarget = "knee_pole." + s
        c.pole_angle = math.radians(-90)
        c.chain_count = 2
        f = rig.pose.bones["foot." + s].constraints.new("COPY_ROTATION")
        f.target = rig; f.subtarget = "foot_ik." + s
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def bind(ob, rig, bone):
    if ob.parent is None:
        mw = Matrix.LocRotScale(ob.location, ob.rotation_euler, ob.scale)
    else:
        bpy.context.view_layer.update()
        mw = ob.matrix_world.copy()
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw


# ---------------------------------------------------------------- face
HEAD_W, HEAD_D, HEAD_H, HEAD_CZ = 1.32, 1.3, 1.18, 4.72


def build_face(rig, coll, skin_mat, eye_color=(0.18, 0.35, 0.75)):
    n = rig.name
    BLACK = get_mat("Face_Black", (0.03, 0.025, 0.03), 0.35)
    WHITE = get_mat("Face_White", (1, 1, 1), 0.4)
    HL = get_mat("Face_Highlight", (1, 1, 1), 0.3, emit=1.5)
    IRIS = get_mat(f"{n}_Iris", eye_color, 0.35)
    MOUTH = get_mat("Face_MouthDark", (0.18, 0.04, 0.05), 0.5)
    TONGUE = get_mat("Face_Tongue", (0.95, 0.45, 0.5), 0.5)
    BLUSH = get_mat("Face_Blush", (1.0, 0.6, 0.62), 0.6)

    face = _link(bpy.data.objects.new(f"{n}_FaceRoot", None), coll)
    face.empty_display_size = 0.2
    face.location = (0, -HEAD_D / 2 - 0.001, HEAD_CZ)
    bind(face, rig, "head")

    def child(ob, parent, loc, y=0.0):
        ob.parent = parent
        ob.location = (loc[0], y, loc[1])
        return ob

    # ---- properties
    add_prop(rig, "eye_open", 1.0, 0, 1, "1 open, 0 closed (blink)")
    add_prop(rig, "eye_wide", 0.0, 0, 1, "0 dot eyes, 1 big white eyes")
    add_prop(rig, "lid", 0.0, 0, 1, "upper lid down (annoyed/sleepy)")
    add_prop(rig, "lid_angle", 0.0, -30, 30, "+ angry lids, - sad lids")
    add_prop(rig, "look_x", 0.0, -1, 1, "pupils left/right")
    add_prop(rig, "look_y", 0.0, -1, 1, "pupils up/down")
    add_prop(rig, "brow_show", 0.0, 0, 1, "show eyebrows")
    add_prop(rig, "brow_up", 0.0, -1, 1, "eyebrow height")
    add_prop(rig, "brow_angle", 0.0, -35, 35, "+ angry, - sad/worried")
    add_prop(rig, "mouth", 0, 0, 7, "0 smile,1 flat,2 frown,3 O,4 open smile,5 smirk,6 shout,7 grin")
    add_prop(rig, "blush", 0.0, 0, 1, "cheek blush")

    EYE_X, EYE_Z = 0.22, 0.02
    for s, sx in (("L", 1), ("R", -1)):
        eye = _link(bpy.data.objects.new(f"{n}_Eye_{s}", None), coll)
        eye.empty_display_size = 0.05
        child(eye, face, (sx * EYE_X, EYE_Z))
        drive(eye, "scale", 2, "max(0.06, eye_open)", rig, ["eye_open"])

        scl = child(disk(f"{n}_Sclera_{s}", coll, 0.15, 0.17, WHITE), eye, (0, 0), -0.003)
        for i in range(3):
            drive(scl, "scale", i, "max(0.001, eye_wide)", rig, ["eye_wide"])

        pup = _link(bpy.data.objects.new(f"{n}_PupilGrp_{s}", None), coll)
        pup.empty_display_size = 0.03
        child(pup, eye, (0, 0))
        drive(pup, "location", 0, "look_x*0.05", rig, ["look_x"])
        drive(pup, "location", 2, "look_y*0.05", rig, ["look_y"])
        iris = child(disk(f"{n}_Iris_{s}", coll, 0.095, 0.105, IRIS), pup, (0, 0), -0.006)
        for i in range(3):
            drive(iris, "scale", i, "max(0.001, eye_wide)", rig, ["eye_wide"])
        dot = child(disk(f"{n}_Pupil_{s}", coll, 0.068, 0.1, BLACK), pup, (0, 0), -0.009)
        for i, ax in ((0, "x"), (2, "z")):
            drive(dot, "scale", i, "1 - 0.25*eye_wide", rig, ["eye_wide"])
        hl = child(disk(f"{n}_Highlight_{s}", coll, 0.026, 0.026, HL, 16), pup, (0.022, 0.04), -0.012)

        # upper lid: skin card that slides down over the eye
        lid = _link(bpy.data.objects.new(f"{n}_LidGrp_{s}", None), coll)
        lid.empty_display_size = 0.03
        child(lid, face, (sx * EYE_X, EYE_Z))
        drive(lid, "location", 2, f"{EYE_Z} + 0.19 - lid*0.2", rig, ["lid"])
        drive(lid, "rotation_euler", 1, f"{-sx}*radians(lid_angle)", rig, ["lid_angle"])
        card = child(poly(f"{n}_Lid_{s}", coll, [(-0.19, 0), (0.19, 0), (0.19, 0.26), (-0.19, 0.26)], skin_mat), lid, (0, 0), -0.016)
        for i in range(3):
            drive(card, "scale", i, "1.0 if lid > 0.01 else 0.0", rig, ["lid"])
        line = child(box(f"{n}_LidLine_{s}", coll, (0.34, 0.01, 0.028), (0, 0, 0), BLACK, 0.012, 2), lid, (0, 0.0), -0.019)
        for i in (0, 2):
            drive(line, "scale", i, "min(1, lid*12)", rig, ["lid"])

        # brow
        brow = child(disk(f"{n}_Brow_{s}", coll, 0.12, 0.032, BLACK), face, (sx * EYE_X, EYE_Z + 0.23), -0.022)
        drive(brow, "location", 2, f"{EYE_Z + 0.23} + brow_up*0.08", rig, ["brow_up"])
        drive(brow, "rotation_euler", 1, f"{-sx}*radians(brow_angle)", rig, ["brow_angle"])
        for i in range(3):
            drive(brow, "scale", i, "max(0.001, brow_show)", rig, ["brow_show"])

        # blush
        bl = child(disk(f"{n}_Blush_{s}", coll, 0.11, 0.06, BLUSH), face, (sx * 0.4, -0.14), -0.004)
        for i in range(3):
            drive(bl, "scale", i, "max(0.001, blush)", rig, ["blush"])

    # ---- mouths
    mz = -0.27
    mouths = [
        stroke(f"{n}_Mouth0_smile", coll, [(-0.09, 0.025), (0, -0.022), (0.09, 0.025)], BLACK),
        stroke(f"{n}_Mouth1_flat", coll, [(-0.07, 0.0), (0.07, 0.0)], BLACK),
        stroke(f"{n}_Mouth2_frown", coll, [(-0.08, -0.025), (0, 0.018), (0.08, -0.025)], BLACK),
    ]
    o = disk(f"{n}_Mouth3_O", coll, 0.055, 0.07, MOUTH)
    mouths.append(o)
    # open smile (D shape) with tongue
    pts = [(-0.12, 0.03)] + [(0.12 * math.cos(a), 0.03 - 0.13 * math.sin(a))
                             for a in [math.pi * i / 16 for i in range(0, 17)]][::-1][1:]
    pts = [(-0.12, 0.03), (0.12, 0.03)] + [(0.12 * math.cos(math.pi * i / 16), 0.03 - 0.12 * math.sin(math.pi * i / 16)) for i in range(1, 16)]
    d = poly(f"{n}_Mouth4_open", coll, pts, MOUTH)
    t = disk(f"{n}_Mouth4_tongue", coll, 0.07, 0.035, TONGUE)
    t.parent = d; t.location = (0, -0.002, -0.06)
    mouths.append(d)
    mouths.append(stroke(f"{n}_Mouth5_smirk", coll, [(-0.08, -0.005), (0.03, -0.012), (0.1, 0.035)], BLACK))
    sh = disk(f"{n}_Mouth6_shout", coll, 0.1, 0.12, MOUTH)
    t2 = disk(f"{n}_Mouth6_tongue", coll, 0.065, 0.04, TONGUE)
    t2.parent = sh; t2.location = (0, -0.002, -0.07)
    mouths.append(sh)
    gr = box(f"{n}_Mouth7_grin", coll, (0.24, 0.01, 0.075), (0, 0, 0), WHITE, 0.03, 3)
    gl = stroke(f"{n}_Mouth7_line", coll, [(-0.11, 0.0), (0.11, 0.0)], BLACK, 0.008)
    gl.parent = gr; gl.location = (0, -0.008, 0)
    mouths.append(gr)

    mgrp = _link(bpy.data.objects.new(f"{n}_MouthGrp", None), coll)
    mgrp.empty_display_size = 0.05
    child(mgrp, face, (0, mz))
    for i, m in enumerate(mouths):
        child(m, mgrp, (0, 0), -0.006)
        for ax in range(3):
            drive(m, "scale", ax, f"1.0 if round(mouth)=={i} else 0.0", rig, ["mouth"])
    # face decals are painted-on: no shadows, otherwise outlines show
    for ob in coll.objects:
        if ob.type in {'MESH', 'CURVE'} and any(ob.name.startswith(f"{n}_{k}") for k in
               ("Sclera", "Iris", "Pupil", "Highlight", "Lid", "Brow", "Blush", "Mouth")):
            ob.visible_shadow = False
    return face


# ---------------------------------------------------------------- hair
def build_hair_spiky(rig, coll, mat, seed=1):
    rnd = random.Random(seed)
    top = HEAD_CZ + HEAD_H / 2
    # cap (separate rounded box, so subsurf doesn't shrink it)
    cap = box(rig.name + "_HairCap", coll, (HEAD_W + 0.1, HEAD_D + 0.1, 0.42), (0, 0.02, top - 0.05), mat, 0.16, 4)
    bind(cap, rig, "head")
    me = bpy.data.meshes.new(rig.name + "_Hair")
    bm = bmesh.new()
    # top spikes: tall, swept back, pointed (subsurf softens them ~40%)
    for ix in (-0.45, -0.15, 0.15, 0.45):
        for iy in (-0.4, -0.05, 0.3):
            dirv = Vector((ix * 1.1 + rnd.uniform(-.2, .2), 0.35 + iy * 0.6 + rnd.uniform(-.15, .15), 1.0))
            pyramid(bm, (ix + rnd.uniform(-.06, .06), iy, top + 0.02), dirv,
                    rnd.uniform(0.24, 0.3), rnd.uniform(0.9, 1.2), 4, rnd.uniform(0, 1))
    # front quiff spikes leaning forward/up
    for x in (-0.4, -0.12, 0.16, 0.42):
        pyramid(bm, (x, -HEAD_D / 2 + 0.15, top + 0.02), (rnd.uniform(-.3, .3), -0.9, 1.0),
                rnd.uniform(0.24, 0.28), rnd.uniform(0.85, 1.0), 4, rnd.uniform(0, 1))
    # swept fringe (front, hanging over forehead, all leaning one way)
    for x in (-0.48, -0.16, 0.16, 0.48):
        pyramid(bm, (x, -HEAD_D / 2 + 0.04, top + 0.02),
                (0.45 + rnd.uniform(-.1, .1), -0.35, -1.0), rnd.uniform(0.22, 0.26), rnd.uniform(0.6, 0.75), 4, rnd.uniform(0, 1))
    # side tufts
    for sx in (-1, 1):
        for y in (-0.35, 0.05, 0.4):
            pyramid(bm, (sx * (HEAD_W / 2 + 0.02), y, top - 0.02), (sx * 0.7, 0.2, -1.0),
                    0.2, rnd.uniform(0.35, 0.45), 4, rnd.uniform(0, 1))
    # back
    for x in (-0.4, 0.0, 0.4):
        pyramid(bm, (x, HEAD_D / 2 + 0.02, top - 0.05), (0, 0.8, -0.6), 0.24, 0.5, 4, rnd.uniform(0, 1))
    bm.to_mesh(me); bm.free()
    ob = _link(bpy.data.objects.new(rig.name + "_Hair", me), coll)
    me.materials.append(mat)
    sub = ob.modifiers.new("Subsurf", "SUBSURF"); sub.levels = 1; sub.render_levels = 1
    for p in me.polygons: p.use_smooth = True
    bind(ob, rig, "head")
    return ob


# ---------------------------------------------------------------- body + outfit
def build_body(rig, coll, skin, jacket, shirt, pants, shoes, accent, logo=True):
    n = rig.name
    jd = tuple(c * 0.75 for c in jacket)
    M = {
        "skin": skin,
        "jacket": get_mat(f"{n}_Jacket", jacket, 0.7),
        "jacket_dark": get_mat(f"{n}_JacketDark", jd, 0.7),
        "shirt": get_mat(f"{n}_Shirt", shirt, 0.65),
        "pants": get_mat(f"{n}_Pants", pants, 0.75),
        "shoes": get_mat(f"{n}_Shoes", shoes, 0.5),
        "sole": get_mat("Sole_White", (0.95, 0.95, 0.95), 0.6),
        "accent": get_mat(f"{n}_Accent", accent, 0.3, metal=0.4),
        "belt": get_mat("Belt_Dark", (0.08, 0.07, 0.07), 0.5),
    }
    P = []

    def part(bone, name, size, center, mat, bevel=0.06):
        ob = box(f"{n}_{name}", coll, size, center, M[mat] if isinstance(mat, str) else mat, bevel)
        P.append((ob, bone))
        return ob

    # head + neck
    part("head", "Head", (HEAD_W, HEAD_D, HEAD_H), (0, 0, HEAD_CZ), "skin", 0.2)
    part("neck", "Neck", (0.6, 0.6, 0.25), (0, 0, 4.05), "skin", 0.05)
    # torso
    part("spine", "UpperTorso", (2.0, 1.0, 1.55), (0, 0, 3.225), "jacket", 0.07)
    part("spine", "ShirtFront", (0.62, 0.05, 1.42), (0, -0.505, 3.2), "shirt", 0.02)
    part("spine", "Hem", (2.04, 1.04, 0.14), (0, 0, 2.52), "jacket_dark", 0.04)
    part("spine", "Collar", (1.2, 1.06, 0.16), (0, 0.02, 4.02), "jacket_dark", 0.05)
    for sx in (-1, 1):
        part("spine", f"Lapel_{sx}", (0.13, 0.07, 1.42), (sx * 0.37, -0.515, 3.22), "jacket_dark", 0.025)
        part("spine", f"Pocket_{sx}", (0.46, 0.035, 0.34), (sx * 0.68, -0.51, 3.42), "jacket", 0.02)
        part("spine", f"PocketFlap_{sx}", (0.5, 0.06, 0.09), (sx * 0.68, -0.525, 3.6), "jacket_dark", 0.02)
        part("spine", f"PocketBtn_{sx}", (0.07, 0.04, 0.07), (sx * 0.68, -0.56, 3.56), "accent", 0.02)
    if logo:
        me = bpy.data.meshes.new(f"{n}_Logo")
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=False, radius=0.17, segments=32)
        # make ring via torus-ish: inset a disk
        bm.free()
        bpy.ops.mesh.primitive_torus_add(major_radius=0.15, minor_radius=0.045,
                                         location=(0, -0.54, 3.05), rotation=(math.pi / 2, 0, 0))
        lg = bpy.context.active_object
        lg.name = f"{n}_Logo"
        for c in lg.users_collection: c.objects.unlink(lg)
        coll.objects.link(lg)
        lg.data.materials.append(M["accent"])
        P.append((lg, "spine"))
    # lower torso
    part("hips", "LowerTorso", (2.0, 1.0, 0.5), (0, 0, 2.2), "pants", 0.05)
    part("hips", "Belt", (2.03, 1.03, 0.1), (0, 0, 2.38), "belt", 0.02)
    # arms
    for s, sx in (("L", 1), ("R", -1)):
        x = sx * 1.5
        part(f"upper_arm.{s}", f"UpperArm_{s}", (0.95, 0.95, 1.06), (x, 0, 3.47), "jacket", 0.07)
        part(f"lower_arm.{s}", f"LowerArm_{s}", (0.93, 0.93, 0.66), (x, 0, 2.56), "jacket", 0.06)
        part(f"lower_arm.{s}", f"Cuff_{s}", (0.98, 0.98, 0.13), (x, 0, 2.22), "jacket_dark", 0.03)
        part(f"hand.{s}", f"Hand_{s}", (0.78, 0.78, 0.36), (x, 0, 1.96), "skin", 0.1)
    # legs
    for s, sx in (("L", 1), ("R", -1)):
        x = sx * 0.5
        part(f"upper_leg.{s}", f"UpperLeg_{s}", (0.96, 0.96, 0.93), (x, 0, 1.53), "pants", 0.06)
        part(f"lower_leg.{s}", f"LowerLeg_{s}", (0.94, 0.94, 0.8), (x, 0, 0.65), "pants", 0.06)
        part(f"foot.{s}", f"Shoe_{s}", (0.98, 1.22, 0.28), (x, -0.1, 0.16), "shoes", 0.09)
        part(f"foot.{s}", f"Sole_{s}", (1.0, 1.24, 0.08), (x, -0.1, 0.04), "sole", 0.03)

    for ob, bone in P:
        bind(ob, rig, bone)
    return M


# ---------------------------------------------------------------- public API
def build_character(name="Hero", location=(0, 0, 0),
                    skin=(1.0, 0.86, 0.68), hair=(0.55, 0.32, 0.17),
                    jacket=(0.86, 0.22, 0.17), shirt=(0.97, 0.96, 0.93),
                    pants=(0.16, 0.18, 0.26), shoes=(0.2, 0.2, 0.22),
                    accent=(0.98, 0.78, 0.2), eye_color=(0.18, 0.35, 0.75),
                    hair_seed=1, logo=True):
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
    skin_m = get_mat(f"{name}_Skin", skin, 0.55)
    build_body(rig, coll, skin_m, jacket, shirt, pants, shoes, accent, logo)
    build_face(rig, coll, skin_m, eye_color)
    build_hair_spiky(rig, coll, get_mat(f"{name}_Hair", hair, 0.6), hair_seed)
    rig.location = location
    refresh_drivers()
    return rig


def refresh_drivers():
    """Drivers created in a script start flagged invalid; re-arm them."""
    bpy.context.view_layer.update()
    for ob in bpy.data.objects:
        ad = ob.animation_data
        if ad:
            for fc in ad.drivers:
                fc.driver.is_valid = True
                fc.driver.expression = fc.driver.expression
    bpy.context.view_layer.update()


EXPRESSIONS = {
    #             eye_open eye_wide lid lid_ang look_x look_y brow_show brow_up brow_ang mouth blush
    "neutral":    (1, 0, 0,    0,   0,    0,    0, 0,    0,   1, 0),
    "happy":      (1, 0, 0,    0,   0,    0,    0, 0,    0,   0, 0),
    "big_smile":  (1, 0, 0.25, -8,  0,    0,    1, 0.4, -8,   4, 0.6),
    "surprised":  (1, 1, 0,    0,   0,    0,    1, 0.8,  -5,  3, 0),
    "shocked":    (1, 1, 0,    0,   0,    0.1,  1, 1.0, -12,  6, 0),
    "angry":      (1, 0, 0.35, 18,  0,    0,    1, -0.5, 28,  2, 0),
    "furious":    (1, 1, 0.3,  22,  0,    0,    1, -0.6, 32,  6, 0),
    "sad":        (1, 0, 0.3, -14,  0,   -0.4,  1, 0.2, -22,  2, 0),
    "worried":    (1, 1, 0,    0,   0,    0,    1, 0.5, -25,  2, 0),
    "side_eye":   (1, 0, 0.5,  4,   0.8,  0,    1, -0.1, 10,  1, 0),
    "suspicious": (1, 0, 0.55, 10, -0.7,  0,    1, -0.2, 14,  5, 0),
    "smug":       (1, 0, 0.45, -4,  0,    0,    1, 0.2,  -6,  5, 0),
    "sleepy":     (1, 0, 0.8,  0,   0,   -0.3,  0, 0,    0,   1, 0),
    "shy":        (1, 0, 0.2, -6,  -0.6, -0.5,  1, 0.3, -15,  0, 1),
    "determined": (1, 0, 0.2,  12,  0,    0,    1, -0.3, 20,  7, 0),
}
FACE_PROPS = ["eye_open", "eye_wide", "lid", "lid_angle", "look_x", "look_y",
              "brow_show", "brow_up", "brow_angle", "mouth", "blush"]


def set_expression(rig, name, frame=None, hold_mouth=False):
    vals = EXPRESSIONS[name]
    for p, v in zip(FACE_PROPS, vals):
        if hold_mouth and p == "mouth":
            continue
        rig[p] = int(v) if p == "mouth" else float(v)
        if frame is not None:
            rig.keyframe_insert(f'["{p}"]', frame=frame)
    if frame is not None:
        _constant_mouth(rig)


def _iter_fcurves(rig):
    ad = rig.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _constant_mouth(rig):
    for fc in _iter_fcurves(rig):
        if fc.data_path in ('["mouth"]',):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def blink(rig, frame, length=4):
    for f, v in ((frame - 1, 1.0), (frame + length // 2, 0.0), (frame + length, 1.0)):
        rig["eye_open"] = v
        rig.keyframe_insert('["eye_open"]', frame=f)


def talk(rig, start, end, rate=3, seed=0, shapes=(1, 3, 4, 0, 3, 1, 4)):
    """Simple lip flap: switch mouth shapes every `rate` frames, close at end."""
    rnd = random.Random(seed)
    f = start
    last = None
    while f < end:
        m = rnd.choice([s for s in shapes if s != last])
        rig["mouth"] = m
        rig.keyframe_insert('["mouth"]', frame=f)
        last = m
        f += rate + rnd.choice([0, 0, 1])
    rig["mouth"] = 1
    rig.keyframe_insert('["mouth"]', frame=end)
    _constant_mouth(rig)
