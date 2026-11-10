"""
Roblox-style R6 character generator (bright "In this town" look, see STYLE_REFERENCE.md).

Classic R6 proportions in studs (1 unit = 1 stud): legs 2, torso 2x2x1, arms 1x2x1,
rounded cylinder head ~1.25. Front faces -Y. Rigid parts parented to bones, like R6.

Faces are a painted decal atlas (4x4 expressions) projected on the head; the rig's
["face"] property picks the cell, so expressions are keyframeable and switch instantly.

Usage inside Blender:
    ns = {}
    exec(open(r"<project>/pipeline/roblox_rig.py", encoding="utf-8").read(), ns)
    rig = ns["build_character"]("Theo", **ns["PRESETS"]["theo"])
    ns["set_face"](rig, "worried", frame=10)
    ns["talk"](rig, 10, 60)
"""
import bpy, bmesh, math, random, os
import numpy as np
from mathutils import Vector, Matrix

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in dir() else None


# ------------------------------------------------------------------ helpers
def srgb(c):
    f = lambda x: x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c)


def _bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def new_mat(name, rgb, rough=0.5, spec=0.35, coat=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"}:
            nt.nodes.remove(n)
    b = _bsdf(m)
    col = (*srgb(rgb), 1.0)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    for k in ("Specular IOR Level", "Specular"):
        if k in b.inputs:
            b.inputs[k].default_value = spec
            break
    if coat and "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.25
    m.diffuse_color = col
    return m


def add_bump(m, scale=60.0, strength=0.12, detail=4.0, kind="noise", tint=0.0):
    """Fabric / plastic micro detail. tint darkens the base colour where the noise is low."""
    nt = m.node_tree
    b = _bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if kind == "wave":
        tx = nt.nodes.new("ShaderNodeTexWave")
        tx.inputs["Scale"].default_value = scale
        tx.inputs["Distortion"].default_value = 6.0
        tx.inputs["Detail"].default_value = detail
        try:
            tx.bands_direction = 'Z'
        except Exception:
            pass
    else:
        tx = nt.nodes.new("ShaderNodeTexNoise")
        tx.inputs["Scale"].default_value = scale
        tx.inputs["Detail"].default_value = detail
    nt.links.new(tc.outputs["Object"], tx.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = 0.02
    nt.links.new(tx.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    if tint:
        base = tuple(b.inputs["Base Color"].default_value)
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = tuple(c * (1 - tint) for c in base[:3]) + (1,)
        ramp.color_ramp.elements[1].color = base
        nt.links.new(tx.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def _link(ob, coll):
    coll.objects.link(ob)
    return ob


def rbox(name, coll, size, center, mat, bevel=0.06, segs=4):
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
        md.limit_method = 'NONE'; md.harden_normals = False
    for p in me.polygons:
        p.use_smooth = True
    return ob


def add_prop(rig, name, value, lo, hi, desc=""):
    rig[name] = value
    try:
        rig.id_properties_ui(name).update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=desc)
    except Exception:
        pass


# ------------------------------------------------------------------ face atlas
FACE_NAMES = [
    "smile", "grin", "worried", "shocked",
    "laugh", "sleep", "angry", "sad",
    "neutral", "blink", "talk", "smirk",
    "surprised", "confident", "cry", "nervous",
]
FACE_INDEX = {n: i for i, n in enumerate(FACE_NAMES)}
ATLAS_N = 4
CELL = 512
FACE_SPAN = 1.55        # head-space width/height (studs) covered by one atlas cell


class Canvas:
    """Tiny anti-aliased painter on an RGBA float cell (y up, coords 0..1)."""

    def __init__(self, n=CELL):
        self.n = n
        t = (np.arange(n) + 0.5) / n
        self.X, self.Y = np.meshgrid(t, t)
        self.rgba = np.zeros((n, n, 4), np.float32)
        self.aa = 1.4 / n

    def _paint(self, cov, col, a=1.0):
        cov = np.clip(cov, 0, 1)[..., None] * a
        c = np.array([*col, 1.0], np.float32)
        self.rgba = self.rgba * (1 - cov) + c * cov

    def ellipse(self, cx, cy, rx, ry, col, rot=0.0, a=1.0):
        dx, dy = self.X - cx, self.Y - cy
        cr, sr = math.cos(rot), math.sin(rot)
        u, v = dx * cr + dy * sr, -dx * sr + dy * cr
        d = (np.sqrt((u / rx) ** 2 + (v / ry) ** 2) - 1.0) * min(rx, ry)
        self._paint(0.5 - d / self.aa, col, a)

    def _dist_poly(self, pts):
        d = np.full(self.X.shape, 9.0, np.float32)
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            vx, vy = x1 - x0, y1 - y0
            L = vx * vx + vy * vy or 1e-9
            t = np.clip(((self.X - x0) * vx + (self.Y - y0) * vy) / L, 0, 1)
            px, py = x0 + t * vx - self.X, y0 + t * vy - self.Y
            d = np.minimum(d, np.sqrt(px * px + py * py))
        return d

    def line(self, pts, w, col, a=1.0):
        d = self._dist_poly(pts) - w
        self._paint(0.5 - d / self.aa, col, a)

    def fill(self, pts, col, a=1.0):
        """Filled polygon (even-odd) with AA edge."""
        inside = np.zeros(self.X.shape, bool)
        P = pts + [pts[0]]
        for (x0, y0), (x1, y1) in zip(P[:-1], P[1:]):
            cond = (y0 > self.Y) != (y1 > self.Y)
            xi = x0 + (self.Y - y0) * (x1 - x0) / ((y1 - y0) or 1e-9)
            inside ^= cond & (self.X < xi)
        d = self._dist_poly(P)
        cov = np.where(inside, 0.5 + d / self.aa, 0.5 - d / self.aa)
        self._paint(cov, col, a)


def arc(cx, cy, r, a0, a1, n=24, ry=None):
    ry = ry or r
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


INK = (0.04, 0.035, 0.04)
WHITE = (1, 1, 1)
MOUTH_IN = (0.32, 0.06, 0.08)
TONGUE = (0.95, 0.42, 0.45)
TEAR = (0.45, 0.78, 1.0)
EX, EY = 0.385, 0.6      # eye centres (mirrored)


def _oval_eyes(c, hl=True, ry=0.075, rx=0.042, dy=0.0):
    for x in (EX, 1 - EX):
        c.ellipse(x, EY + dy, rx, ry, INK)
        if hl:
            c.ellipse(x + 0.012, EY + dy + 0.035, 0.013, 0.017, WHITE)


def _white_eyes(c, r=0.07, pupil=0.034, look=(0, 0), outline=0.011):
    for x in (EX, 1 - EX):
        c.ellipse(x, EY, r + outline, r * 1.12 + outline, INK)
        c.ellipse(x, EY, r, r * 1.12, WHITE)
        c.ellipse(x + look[0], EY + look[1], pupil, pupil * 1.15, INK)
        c.ellipse(x + look[0] + pupil * 0.35, EY + look[1] + pupil * 0.45, pupil * 0.32, pupil * 0.36, WHITE)


def _brows(c, inner_dy, outer_dy, y=0.73, w=0.016, curve=0.0):
    for s in (1, -1):
        xi, xo = 0.5 - s * 0.05, 0.5 - s * 0.175
        xm = (xi + xo) / 2
        c.line([(xo, y + outer_dy), (xm, y + (inner_dy + outer_dy) / 2 + curve), (xi, y + inner_dy)], w, INK)


def _smile(c, r=0.15, cy=0.47, w=0.014, a0=205, a1=335):
    c.line(arc(0.5, cy, r, math.radians(a0), math.radians(a1)), w, INK)


def _open_mouth(c, cy=0.42, rx=0.13, ry=0.1, teeth=True, tongue=True):
    top = cy + 0.035
    pts = [(0.5 - rx, top)] + arc(0.5, top, rx, math.pi, 2 * math.pi, 28, ry)[1:-1] + [(0.5 + rx, top)]
    c.fill(pts, MOUTH_IN)
    if tongue:
        c.ellipse(0.5, top - ry * 0.78, rx * 0.55, ry * 0.32, TONGUE)
    if teeth:
        c.fill([(0.5 - rx * 0.92, top), (0.5 + rx * 0.92, top), (0.5 + rx * 0.85, top - ry * 0.28), (0.5 - rx * 0.85, top - ry * 0.28)], WHITE)
    c.line(pts + [pts[0]], 0.011, INK)


def draw_face(name):
    c = Canvas()
    if name == "smile":
        _oval_eyes(c); _smile(c)
    elif name == "grin":
        _oval_eyes(c); _brows(c, 0.01, 0.0); _open_mouth(c)
    elif name == "worried":
        _white_eyes(c, look=(0, -0.008)); _brows(c, 0.045, -0.01, y=0.74)
        c.line([(0.42, 0.43), (0.45, 0.445), (0.48, 0.43), (0.51, 0.445), (0.54, 0.43), (0.57, 0.445)], 0.011, INK)
    elif name == "shocked":
        _white_eyes(c, r=0.082, pupil=0.022); _brows(c, 0.05, 0.03, y=0.77)
        c.ellipse(0.5, 0.42, 0.06, 0.085, INK); c.ellipse(0.5, 0.42, 0.047, 0.071, MOUTH_IN)
    elif name == "laugh":
        for x in (EX, 1 - EX):
            c.line(arc(x, EY - 0.03, 0.05, math.radians(20), math.radians(160)), 0.016, INK)
        _brows(c, 0.02, 0.0, y=0.74)
        _open_mouth(c, cy=0.44, rx=0.15, ry=0.12)
    elif name == "sleep":
        for x in (EX, 1 - EX):
            c.line(arc(x, EY + 0.02, 0.045, math.radians(200), math.radians(340)), 0.013, INK)
        c.ellipse(0.5, 0.44, 0.03, 0.035, INK)
    elif name == "angry":
        _oval_eyes(c, ry=0.06, dy=-0.01); _brows(c, -0.035, 0.03, y=0.71, w=0.02)
        c.line(arc(0.5, 0.36, 0.11, math.radians(35), math.radians(145)), 0.015, INK)
    elif name == "sad":
        _oval_eyes(c); _brows(c, 0.04, -0.02, y=0.73)
        c.line(arc(0.5, 0.37, 0.09, math.radians(35), math.radians(145)), 0.014, INK)
        c.ellipse(EX - 0.01, 0.47, 0.014, 0.024, TEAR)
    elif name == "neutral":
        _oval_eyes(c); c.line([(0.43, 0.44), (0.57, 0.44)], 0.013, INK)
    elif name == "blink":
        for x in (EX, 1 - EX):
            c.line([(x - 0.045, EY), (x + 0.045, EY)], 0.013, INK)
        _smile(c)
    elif name == "talk":
        _oval_eyes(c)
        c.ellipse(0.5, 0.43, 0.075, 0.06, INK); c.ellipse(0.5, 0.43, 0.062, 0.047, MOUTH_IN)
        c.ellipse(0.5, 0.405, 0.04, 0.018, TONGUE)
    elif name == "smirk":
        _oval_eyes(c); _brows(c, 0.0, 0.035, y=0.73)
        c.line([(0.43, 0.445), (0.52, 0.44), (0.58, 0.475)], 0.014, INK)
    elif name == "surprised":
        _oval_eyes(c, ry=0.085); _brows(c, 0.05, 0.04, y=0.77)
        c.ellipse(0.5, 0.42, 0.04, 0.05, INK); c.ellipse(0.5, 0.42, 0.028, 0.038, MOUTH_IN)
    elif name == "confident":
        _oval_eyes(c); _brows(c, -0.005, 0.02, y=0.74, w=0.018)
        top = 0.48
        pts = [(0.36, top)] + arc(0.5, top, 0.14, math.pi, 2 * math.pi, 28, 0.09)[1:-1] + [(0.64, top)]
        c.fill(pts, WHITE); c.line([(0.37, top - 0.03), (0.63, top - 0.03)], 0.006, (0.75, 0.75, 0.78))
        c.line(pts + [pts[0]], 0.012, INK)
    elif name == "cry":
        for x in (EX, 1 - EX):
            c.line(arc(x, EY + 0.025, 0.05, math.radians(200), math.radians(340)), 0.016, INK)
            c.fill([(x - 0.025, EY - 0.02), (x + 0.025, EY - 0.02), (x + 0.03, 0.2), (x - 0.03, 0.2)], TEAR, 0.9)
        _brows(c, 0.05, -0.015, y=0.74)
        _open_mouth(c, cy=0.4, rx=0.1, ry=0.1, teeth=False)
    elif name == "nervous":
        _white_eyes(c, r=0.066, pupil=0.028); _brows(c, 0.05, -0.01, y=0.75)
        top = 0.47
        pts = [(0.38, top), (0.62, top), (0.62, top - 0.08), (0.38, top - 0.08)]
        c.fill(pts, WHITE)
        for x in (0.44, 0.5, 0.56):
            c.line([(x, top), (x, top - 0.08)], 0.004, INK)
        c.line([(0.38, top - 0.04), (0.62, top - 0.04)], 0.004, INK)
        c.line(pts + [pts[0]], 0.011, INK)
        c.ellipse(0.64, 0.66, 0.016, 0.026, TEAR)
    return c.rgba


def face_atlas(path=None, force=False):
    """Build (or load) the expression atlas image."""
    img = bpy.data.images.get("RobloxFaces")
    if img and not force:
        return img
    N = ATLAS_N * CELL
    atlas = np.zeros((N, N, 4), np.float32)
    for i, name in enumerate(FACE_NAMES):
        col, row = i % ATLAS_N, i // ATLAS_N
        atlas[row * CELL:(row + 1) * CELL, col * CELL:(col + 1) * CELL] = draw_face(name)
    if img is None:
        img = bpy.data.images.new("RobloxFaces", N, N, alpha=True)
    elif tuple(img.size) != (N, N):
        img.scale(N, N)
    img.colorspace_settings.name = "sRGB"
    img.alpha_mode = 'STRAIGHT'
    img.pixels.foreach_set(atlas.ravel())
    img.update()
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
    img.pack()
    return img


def head_material(rig, skin):
    """Skin + projected face decal; the decal cell follows rig['face']."""
    n = rig.name
    m = new_mat(f"{n}_Head", skin, rough=0.42, spec=0.4)
    nt = m.node_tree
    b = _bsdf(m)
    L = nt.links
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sep.inputs[0])

    def math_node(op, a=None, b=None, va=0.0, vb=0.0, clamp=False):
        nd = N.new("ShaderNodeMath"); nd.operation = op; nd.use_clamp = clamp
        nd.inputs[0].default_value = va; nd.inputs[1].default_value = vb
        if a is not None: L.new(a, nd.inputs[0])
        if b is not None: L.new(b, nd.inputs[1])
        return nd.outputs[0]

    # local uv in [0,1] across the face span
    u = math_node("ADD", math_node("DIVIDE", sep.outputs["X"], vb=FACE_SPAN), vb=0.5)
    v = math_node("ADD", math_node("DIVIDE", sep.outputs["Z"], vb=FACE_SPAN), vb=0.5)
    idx = N.new("ShaderNodeValue"); idx.name = "FaceIdx"; idx.label = "FaceIdx"
    col = math_node("FLOORED_MODULO", idx.outputs[0], vb=ATLAS_N)
    row = math_node("FLOOR", math_node("DIVIDE", idx.outputs[0], vb=ATLAS_N))
    uc = math_node("MINIMUM", math_node("MAXIMUM", u, vb=0.002), vb=0.998)
    vc = math_node("MINIMUM", math_node("MAXIMUM", v, vb=0.002), vb=0.998)
    U = math_node("DIVIDE", math_node("ADD", uc, col), vb=ATLAS_N)
    V = math_node("DIVIDE", math_node("ADD", vc, row), vb=ATLAS_N)
    comb = N.new("ShaderNodeCombineXYZ"); L.new(U, comb.inputs[0]); L.new(V, comb.inputs[1])
    tex = N.new("ShaderNodeTexImage"); tex.image = face_atlas(); tex.extension = 'EXTEND'
    tex.interpolation = 'Cubic'
    L.new(comb.outputs[0], tex.inputs["Vector"])
    # only on the front half, and only inside the cell
    front = math_node("LESS_THAN", sep.outputs["Y"], vb=-0.05)
    inside_u = math_node("MULTIPLY", math_node("GREATER_THAN", u, vb=0.0), math_node("LESS_THAN", u, vb=1.0))
    inside_v = math_node("MULTIPLY", math_node("GREATER_THAN", v, vb=0.0), math_node("LESS_THAN", v, vb=1.0))
    mask = math_node("MULTIPLY", math_node("MULTIPLY", inside_u, inside_v), front)
    alpha = math_node("MULTIPLY", tex.outputs["Alpha"], mask)
    mix = N.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    L.new(alpha, mix.inputs["Factor"])
    mix.inputs[6].default_value = b.inputs["Base Color"].default_value
    L.new(tex.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    # decal is a bit glossier (printed sticker look)
    rmix = math_node("ADD", math_node("MULTIPLY", alpha, vb=-0.15), vb=0.42)
    L.new(rmix, b.inputs["Roughness"])
    # driver: FaceIdx <- rig["face"]
    fc = idx.outputs[0].driver_add("default_value")
    d = fc.driver; d.type = 'AVERAGE'
    var = d.variables.new(); var.type = 'SINGLE_PROP'
    var.targets[0].id_type = 'OBJECT'; var.targets[0].id = rig; var.targets[0].data_path = '["face"]'
    return m


# ------------------------------------------------------------------ skeleton (R6)
HEAD_CZ = 4.62
HEAD_R = 0.64
HEAD_H = 1.24

BONES = {
    "root":        ((0, 0, 0),     (0, 1.5, 0),     None),
    "hips":        ((0, 0, 2.0),   (0, 0, 2.3),     "root"),
    "spine":       ((0, 0, 2.3),   (0, 0, 4.0),     "hips"),
    "neck":        ((0, 0, 4.0),   (0, 0, 4.1),     "spine"),
    "head":        ((0, 0, 4.1),   (0, 0, 5.2),     "neck"),
    "upper_arm.L": ((1.5, 0, 3.5), (1.5, 0, 2.0),   "spine"),
    "upper_arm.R": ((-1.5, 0, 3.5), (-1.5, 0, 2.0), "spine"),
    "upper_leg.L": ((0.5, 0, 2.0), (0.5, 0, 0.1),   "hips"),
    "upper_leg.R": ((-0.5, 0, 2.0), (-0.5, 0, 0.1), "hips"),
}


def build_armature(name, coll):
    arm = bpy.data.armatures.new(name + "_Armature")
    rig = _link(bpy.data.objects.new(name, arm), coll)
    arm.display_type = 'STICK'
    rig.show_in_front = True
    vl = bpy.context.view_layer
    vl.update()
    for o in list(vl.objects):
        o.select_set(False)
    vl.objects.active = rig
    rig.select_set(True)
    # explicit override: after read_homefile/open_mainfile over MCP the context can be stale
    win = bpy.context.window or bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=win, active_object=rig, object=rig,
                                   selected_objects=[rig], selected_editable_objects=[rig]):
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.edit_bones
        for bn, (h, t, p) in BONES.items():
            b = eb.new(bn); b.head, b.tail = h, t; b.roll = 0.0
            if p:
                b.parent = eb[p]; b.use_connect = False
            b.use_deform = False
        bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    return rig


def bind(ob, rig, bone):
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = mw


# ------------------------------------------------------------------ head
def build_head(rig, coll, mat):
    n = rig.name
    me = bpy.data.meshes.new(f"{n}_Head")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64,
                          radius1=HEAD_R, radius2=HEAD_R, depth=HEAD_H)
    bm.to_mesh(me); bm.free()
    ob = _link(bpy.data.objects.new(f"{n}_Head", me), coll)
    ob.location = (0, 0, HEAD_CZ)
    me.materials.append(mat)
    bv = ob.modifiers.new("Bevel", "BEVEL"); bv.width = 0.3; bv.segments = 8
    bv.limit_method = 'ANGLE'; bv.angle_limit = math.radians(60); bv.profile = 0.6
    for p in me.polygons:
        p.use_smooth = True
    bind(ob, rig, "head")
    return ob


# ------------------------------------------------------------------ hair (tapered strand clumps)
def _strand(cu, pts, r0, r1=0.02):
    sp = cu.splines.new('NURBS')
    sp.points.add(len(pts) - 1)
    k = len(pts)
    for i, (p, pt) in enumerate(zip(pts, sp.points)):
        pt.co = (*p, 1.0)
        t = i / (k - 1)
        pt.radius = r0 * (1 - t) ** 0.8 + r1 * t
    sp.order_u = min(4, k)
    sp.use_endpoint_u = True
    sp.resolution_u = 8


def _hair_cap(rig, coll, mat, volume=1.0, cut_z=0.1, slope=0.42):
    """Squashed sphere over the skull, cut by a slanted plane (higher at the forehead)."""
    n, cz, R = rig.name, HEAD_CZ, HEAD_R
    me = bpy.data.meshes.new(f"{n}_HairCap")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * (R + 0.07), v.co.y * (R + 0.08) + 0.02, v.co.z * 0.62 * volume + cz + 0.2))
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, cz + cut_z),
                           plane_no=Vector((0, slope, 1)).normalized(), clear_inner=True)
    bm.to_mesh(me); bm.free()
    cap = _link(bpy.data.objects.new(f"{n}_HairCap", me), coll)
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    so = cap.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.05; so.offset = -1
    bind(cap, rig, "head")
    return cz + 0.2 + 0.62 * volume


HAIR_VOLUME = {"messy": 1.0, "short": 0.72, "under_cap": 0.7, "swept": 0.82, "long": 0.92, "pigtails": 0.88}


def build_hair(rig, coll, mat, style="messy", seed=3, fringe_dir=1.0):
    if style in (None, "bald"):
        return None
    n, cz, R = rig.name, HEAD_CZ, HEAD_R
    rnd = random.Random(seed)
    j = lambda a: rnd.uniform(-a, a)
    s = fringe_dir
    # the cap always fully covers the skull; volume only changes how high the clumps sit
    _hair_cap(rig, coll, mat, 1.0, cut_z=0.1 if style != "long" else -0.05)
    top = cz + 0.2 + 0.62 * HAIR_VOLUME[style]
    cu = bpy.data.curves.new(f"{n}_Hair", 'CURVE')
    cu.dimensions = '3D'; cu.bevel_depth = 0.11; cu.bevel_resolution = 5; cu.use_fill_caps = True

    def sides(z_end=0.02, r=1.5, ys=(-0.35, -0.05, 0.25)):
        for sx in (-1, 1):
            for y in ys:
                _strand(cu, [(sx * (R - 0.05), y, cz + 0.42), (sx * (R + 0.09), y + 0.06, cz + 0.22),
                             (sx * (R + 0.07), y + 0.1 + j(.04), cz + z_end + j(.05))], r, 0.1)

    def back(z_end=-0.15, r=1.8, xs=(-0.42, -0.14, 0.14, 0.42), y_out=0.12):
        for x in xs:
            _strand(cu, [(x, R - 0.1, top - 0.2), (x * 1.1, R + y_out, cz + 0.2),
                         (x * 1.1 + j(.05), R + y_out - 0.04, cz + z_end + j(.05))], r, 0.2)

    if style == "messy":
        for x in (-0.46, -0.2, 0.06, 0.3, 0.52):
            _strand(cu, [(x * 0.7, 0.05, top + 0.02), (x + s * 0.05 + j(.04), -0.5, top - 0.02 + j(.04)),
                         (x + s * 0.15 + j(.05), -0.75, cz + 0.5 + j(.05)), (x + s * 0.3 + j(.06), -0.72, cz + 0.3 + j(.06))],
                    2.5 + j(.3), 0.05)
        for x, y in ((-0.35, -0.05), (0.0, -0.15), (0.32, 0.0), (-0.15, 0.3), (0.2, 0.32)):
            _strand(cu, [(x + j(.05), y, top - 0.15), (x * 1.2 + j(.08), y + 0.15, top + 0.1 + j(.05)),
                         (x * 1.4 + j(.1), y + 0.4 + j(.08), top + 0.22 + j(.08))], 2.3 + j(.3), 0.05)
        sides(); back()
    elif style == "short":
        for x in (-0.42, -0.21, 0.0, 0.21, 0.42):
            _strand(cu, [(x * 0.8, -0.1, top), (x + s * 0.06 + j(.03), -0.6, top - 0.06),
                         (x + s * 0.12 + j(.03), -0.72, cz + 0.52 + j(.03))], 1.6, 0.25)
        sides(z_end=0.18, r=1.1); back(z_end=0.0, r=1.4, y_out=0.06)
    elif style == "under_cap":
        # only what shows below a hat: sideburns and the back
        sides(z_end=0.18, r=1.1, ys=(-0.25, 0.05, 0.3)); back(z_end=0.0, r=1.4, y_out=0.06)
    elif style == "swept":
        # neat side part, smooth clumps sweeping across the forehead
        for i, x in enumerate((0.45, 0.25, 0.05, -0.15, -0.35)):
            _strand(cu, [(0.3 * s, -0.05, top + 0.02), (x * s, -0.45, top + 0.02),
                         ((x - 0.25) * s, -0.72, cz + 0.6 + j(.02)), ((x - 0.42) * s, -0.72, cz + 0.45 + j(.03))],
                    2.1, 0.15)
        for x in (-0.3, 0.0, 0.3):
            _strand(cu, [(x, -0.1, top - 0.05), (x * 1.1, 0.25, top + 0.06), (x * 1.15, 0.6, top - 0.15)], 2.2, 0.4)
        sides(z_end=0.15, r=1.2); back(z_end=-0.05, r=1.6, y_out=0.08)
    elif style == "long":
        # center-parted curtain fringe + long hair down the back and over the shoulders
        for sx in (-1, 1):
            for k, x in enumerate((0.08, 0.28, 0.48)):
                _strand(cu, [(sx * 0.04, -0.2, top + 0.03), (sx * x, -0.62, top - 0.1),
                             (sx * (x + 0.12), -0.72, cz + 0.4 - 0.08 * k)], 1.9, 0.2)
            # side locks: down past the cheeks, over the shoulder, onto the chest
            for k, y in enumerate((-0.25, 0.05)):
                _strand(cu, [(sx * (R - 0.05), y, cz + 0.45), (sx * (R + 0.1), y - 0.05, cz - 0.2),
                             (sx * (0.72 + 0.12 * k), -0.45 - 0.05 * k, 4.12),
                             (sx * (0.72 + 0.12 * k), -0.62, 3.75), (sx * (0.7 + 0.12 * k) + j(.03), -0.6, 3.35 + j(.06))],
                        1.9, 0.5)
            _strand(cu, [(sx * (R - 0.05), 0.35, cz + 0.4), (sx * (R + 0.12), 0.4, cz - 0.2),
                         (sx * (R + 0.15), 0.6, 4.1), (sx * (R + 0.1), 0.62, 3.4)], 2.0, 0.6)
        # back: a full curtain down to mid-back
        for x in (-0.55, -0.3, -0.05, 0.2, 0.45):
            _strand(cu, [(x, R - 0.15, top - 0.1), (x * 1.1, R + 0.22, cz + 0.1), (x * 1.15, R + 0.05, 4.1),
                         (x * 1.15, 0.62, 3.7), (x * 1.1 + j(.05), 0.62, 3.25 + j(.06))], 2.2, 0.7)
    elif style == "pigtails":
        for x in (-0.45, -0.27, -0.09, 0.09, 0.27, 0.45):     # straight bangs
            _strand(cu, [(x * 0.8, -0.1, top + 0.02), (x, -0.62, top - 0.08), (x + j(.02), -0.73, cz + 0.42)], 1.5, 0.5)
        sides(z_end=0.1, r=1.2); back(z_end=-0.05, r=1.6)
        tie = new_mat(f"{n}_HairTie", (0.98, 0.35, 0.55), 0.4, 0.4)
        for sx in (-1, 1):
            base = (sx * (R + 0.08), 0.12, cz + 0.38)
            b = _link(bpy.data.objects.new(f"{n}_Tie_{sx}", _sphere_mesh(f"{n}_Tie_{sx}", 0.12)), coll)
            b.location = base; b.data.materials.append(tie); bind(b, rig, "head")
            for k in range(3):
                _strand(cu, [base, (sx * (R + 0.35), 0.15 + 0.06 * k, cz + 0.3), (sx * (R + 0.55), 0.18 + 0.05 * k, cz - 0.05),
                             (sx * (R + 0.5 + j(.05)), 0.2 + 0.05 * k, cz - 0.5 + j(.05))], 2.0, 0.15)
    hair = _link(bpy.data.objects.new(f"{n}_Hair", cu), coll)
    cu.materials.append(mat)
    bind(hair, rig, "head")
    return hair


def _sphere_mesh(name, r, segs=24):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _cyl_mesh(name, r1, r2, depth, segs=48, caps=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs, radius1=r1, radius2=r2, depth=depth)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _flat_shape(name, pts, thickness=0.04):
    """Flat polygon in XZ (convex or star: fan from centroid), solidified towards -Y."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
    c = bm.verts.new((cx, 0, cz))
    ring = [bm.verts.new((x, 0, z)) for x, z in pts]
    for a, b in zip(ring, ring[1:] + ring[:1]):
        bm.faces.new((c, b, a))
    bm.to_mesh(me); bm.free()
    return me, thickness


# ------------------------------------------------------------------ hats + face extras
def build_hat(rig, coll, kind, color=None):
    if not kind:
        return
    n, cz, R = rig.name, HEAD_CZ, HEAD_R
    top_z = cz + HEAD_H / 2
    objs = []

    def add(name, me, loc, mat, rot=(0, 0, 0), scale=(1, 1, 1)):
        ob = _link(bpy.data.objects.new(f"{n}_{name}", me), coll)
        ob.location = loc; ob.rotation_euler = rot; ob.scale = scale
        if not me.materials:
            me.materials.append(mat)
        objs.append(ob); return ob

    if kind == "crown":
        gold = new_mat("Gold", (1.0, 0.76, 0.18), 0.22, 0.6)
        _bsdf(gold).inputs["Metallic"].default_value = 1.0
        ruby = new_mat("Ruby", (0.9, 0.05, 0.12), 0.1, 0.8, coat=1.0)
        sapph = new_mat("Sapphire", (0.1, 0.35, 0.95), 0.1, 0.8, coat=1.0)
        zc = top_z + 0.12
        ring = add("Crown", _cyl_mesh(f"{n}_Crown", R + 0.05, R + 0.1, 0.3, 64, caps=False), (0, 0, zc), gold)
        so = ring.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.06
        bv = ring.modifiers.new("Bevel", "BEVEL"); bv.width = 0.02; bv.segments = 2
        for i in range(8):
            a = 2 * math.pi * i / 8 - math.pi / 2
            x, y = math.cos(a) * (R + 0.1), math.sin(a) * (R + 0.1)
            add(f"Spike{i}", _cyl_mesh(f"{n}_Spike{i}", 0.14, 0.0, 0.34, 4), (x, y, zc + 0.32), gold,
                rot=(0, 0, a + math.pi / 4), scale=(1, 0.45, 1))
            add(f"Ball{i}", _sphere_mesh(f"{n}_Ball{i}", 0.055), (x, y, zc + 0.5), gold)
            add(f"Gem{i}", _sphere_mesh(f"{n}_Gem{i}", 0.065), (x * 1.04, y * 1.04, zc), ruby if i % 2 == 0 else sapph,
                rot=(0, 0, a), scale=(0.6, 1, 1))
    elif kind == "police":
        navy = add_bump(new_mat(f"{n}_CapNavy", color or (0.1, 0.16, 0.36), 0.6, 0.3), 80, 0.12, 4)
        black = new_mat("GlossBlack", (0.03, 0.03, 0.04), 0.15, 0.6, coat=0.6)
        gold = new_mat("Gold", (1.0, 0.76, 0.18), 0.22, 0.6)
        _bsdf(gold).inputs["Metallic"].default_value = 1.0
        zc = top_z + 0.1
        crown = add("CapCrown", _cyl_mesh(f"{n}_CapCrown", R + 0.07, R + 0.2, 0.42, 64), (0, 0.02, zc + 0.12), navy)
        bv = crown.modifiers.new("Bevel", "BEVEL"); bv.width = 0.06; bv.segments = 3
        add("CapBand", _cyl_mesh(f"{n}_CapBand", R + 0.085, R + 0.1, 0.12, 64), (0, 0.02, zc - 0.03), black)
        brim = add("CapBrim", _cyl_mesh(f"{n}_CapBrim", 0.55, 0.55, 0.05, 48), (0, -R + 0.05, zc - 0.07), black,
                   rot=(math.radians(-14), 0, 0), scale=(1.0, 0.75, 1))
        star = [(0.11 * (1 if k % 2 == 0 else 0.45) * math.sin(math.pi * k / 5),
                 0.11 * (1 if k % 2 == 0 else 0.45) * math.cos(math.pi * k / 5)) for k in range(10)]
        me, th = _flat_shape(f"{n}_CapBadge", star)
        b = add("CapBadge", me, (0, -R - 0.13, zc + 0.12), gold, rot=(math.radians(10), 0, 0))
        sm = b.modifiers.new("Solid", "SOLIDIFY"); sm.thickness = th
    elif kind == "cap":
        col = new_mat(f"{n}_CapCol", color or (0.9, 0.15, 0.15), 0.6, 0.3)
        d = add("CapDome", _sphere_mesh(f"{n}_CapDome", 1.0, 48), (0, 0.02, top_z - 0.05), col, scale=(R + 0.08, R + 0.1, 0.45))
        add("CapBrim", _cyl_mesh(f"{n}_CapBrim", 0.5, 0.5, 0.05, 48), (0, -R - 0.05, top_z - 0.08), col,
            rot=(math.radians(-8), 0, 0), scale=(1.0, 0.8, 1))
    for ob in objs:
        bind(ob, rig, "head")


def _face_xyz(u, v, out=0.03):
    """Head-space position of an atlas-cell coordinate (u,v in 0..1) on the head surface."""
    x = (u - 0.5) * FACE_SPAN
    z = (v - 0.5) * FACE_SPAN
    y = -math.sqrt(max(HEAD_R ** 2 - x * x, 0.01)) - out
    return x, y, HEAD_CZ + z


def build_extras(rig, coll, extras, hair_rgb):
    n = rig.name
    for ex in extras or ():
        if ex == "mustache":
            mat = new_mat(f"{n}_Stache", tuple(c * 0.8 for c in hair_rgb), 0.5, 0.4)
            cu = bpy.data.curves.new(f"{n}_Mustache", 'CURVE')
            cu.dimensions = '3D'; cu.bevel_depth = 0.07; cu.bevel_resolution = 4; cu.use_fill_caps = True
            for sx in (-1, 1):
                p0 = _face_xyz(0.5, 0.5, 0.06)
                p1 = _face_xyz(0.5 + sx * 0.08, 0.5, 0.06)
                p2 = _face_xyz(0.5 + sx * 0.16, 0.465, 0.05)
                p3 = _face_xyz(0.5 + sx * 0.21, 0.42, 0.03)
                _strand(cu, [p0, p1, p2, p3], 1.5, 0.15)
            ob = _link(bpy.data.objects.new(f"{n}_Mustache", cu), coll)
            cu.materials.append(mat); bind(ob, rig, "head")
        elif ex == "glasses":
            mat = new_mat("GlassesFrame", (0.05, 0.05, 0.06), 0.25, 0.5, coat=0.5)
            for sx in (-1, 1):
                u = 0.5 + sx * (0.5 - EX)
                x, y, z = _face_xyz(u, EY, 0.07)
                bpy.ops.mesh.primitive_torus_add(major_radius=0.135, minor_radius=0.022, major_segments=48, minor_segments=10,
                                                 location=(x, y, z), rotation=(math.pi / 2, 0, 0))
                t = bpy.context.active_object; t.name = f"{n}_Lens_{sx}"
                for c in t.users_collection: c.objects.unlink(t)
                coll.objects.link(t); t.data.materials.append(mat)
                for p in t.data.polygons: p.use_smooth = True
                bind(t, rig, "head")
                arm = rbox(f"{n}_GlassArm_{sx}", coll, (0.035, 0.6, 0.035), (sx * (HEAD_R + 0.01), -0.3, z + 0.02), mat, 0.01, 2)
                bind(arm, rig, "head")
            x, y, z = _face_xyz(0.5, EY + 0.01, 0.09)
            br = rbox(f"{n}_GlassBridge", coll, (0.12, 0.03, 0.03), (x, y, z), mat, 0.01, 2)
            bind(br, rig, "head")
        elif ex == "monster":
            # Terrifying horror monster features: 3D glowing red eyes, fanged maw, demon horns, shoulder spikes & claws
            black_void = new_mat(f"{n}_VoidBlack", (0.01, 0.01, 0.015), 0.9, 0.1)
            horn_mat = new_mat(f"{n}_HornBlack", (0.04, 0.02, 0.03), 0.35, 0.6, coat=0.4)
            fang_mat = new_mat(f"{n}_FangWhite", (0.96, 0.94, 0.88), 0.25, 0.7, coat=0.5)
            red_glow = new_mat(f"{n}_RedEyeGlow", (1.0, 0.0, 0.0), 0.15, 0.8)
            b_glow = _bsdf(red_glow)
            b_glow.inputs["Emission Color"].default_value = (1.0, 0.0, 0.0, 1.0)
            b_glow.inputs["Emission Strength"].default_value = 6.0
            pupil_glow = new_mat(f"{n}_PupilGlow", (0.02, 0.0, 0.0), 0.1, 0.9)

            # 1) Sunken dark eye sockets + large glowing red 3D eyes + slit pupils + angry brow ridges
            for sx in (-1, 1):
                u = 0.5 + sx * (0.5 - EX + 0.02)
                x, y, z = _face_xyz(u, EY + 0.02, 0.055)
                sock = _link(bpy.data.objects.new(f"{n}_EyeSock_{sx}", _sphere_mesh(f"{n}_EyeSock_{sx}", 1.0, 24)), coll)
                sock.location = (x, y + 0.015, z); sock.scale = (0.155, 0.06, 0.13)
                sock.data.materials.append(black_void); bind(sock, rig, "head")

                eye = _link(bpy.data.objects.new(f"{n}_GlowEye_{sx}", _sphere_mesh(f"{n}_GlowEye_{sx}", 1.0, 24)), coll)
                eye.location = (x, y - 0.015, z); eye.scale = (0.125, 0.055, 0.095)
                eye.rotation_euler = (0, math.radians(-sx * 14), 0)
                eye.data.materials.append(red_glow); bind(eye, rig, "head")

                slit = rbox(f"{n}_Slit_{sx}", coll, (0.026, 0.03, 0.14), (x, y - 0.055, z), pupil_glow, 0.005, 2)
                bind(slit, rig, "head")

                brow = rbox(f"{n}_MonsterBrow_{sx}", coll, (0.28, 0.09, 0.06), (x, y - 0.03, z + 0.105), black_void, 0.01, 2)
                brow.rotation_euler = (0, math.radians(-sx * 26), 0)
                bind(brow, rig, "head")

            # 2) Wide gaping monster maw + jagged 3D white fangs
            mx, my, mz = _face_xyz(0.5, 0.34, 0.04)
            maw = rbox(f"{n}_MonsterMaw", coll, (0.78, 0.08, 0.36), (mx, my + 0.02, mz), black_void, 0.04, 3)
            bind(maw, rig, "head")
            for k in range(6):
                fx = -0.30 + k * 0.12
                fy = -math.sqrt(max(HEAD_R ** 2 - fx * fx, 0.01)) - 0.085
                # Upper fang pointing down
                uf = _link(bpy.data.objects.new(f"{n}_UFang_{k}", _cyl_mesh(f"{n}_UFang_{k}", 0.045, 0.004, 0.15, 12)), coll)
                uf.location = (fx, fy, mz + 0.095); uf.rotation_euler = (math.pi, 0, 0)
                uf.data.materials.append(fang_mat); bind(uf, rig, "head")
                # Lower fang pointing up
                lf = _link(bpy.data.objects.new(f"{n}_LFang_{k}", _cyl_mesh(f"{n}_LFang_{k}", 0.040, 0.004, 0.13, 12)), coll)
                lf.location = (fx + 0.03, fy, mz - 0.095)
                lf.data.materials.append(fang_mat); bind(lf, rig, "head")

            # 3) Curved demonic horns on the head with glowing red tips
            top_z = HEAD_CZ + HEAD_H / 2
            for sx in (-1, 1):
                h_base = _link(bpy.data.objects.new(f"{n}_HornBase_{sx}", _cyl_mesh(f"{n}_HornBase_{sx}", 0.16, 0.09, 0.55, 16)), coll)
                h_base.location = (sx * 0.48, -0.05, top_z + 0.12)
                h_base.rotation_euler = (math.radians(-15), math.radians(sx * 32), 0)
                h_base.data.materials.append(horn_mat); bind(h_base, rig, "head")

                h_tip = _link(bpy.data.objects.new(f"{n}_HornTip_{sx}", _cyl_mesh(f"{n}_HornTip_{sx}", 0.09, 0.005, 0.55, 16)), coll)
                h_tip.location = (sx * 0.68, -0.14, top_z + 0.52)
                h_tip.rotation_euler = (math.radians(-28), math.radians(sx * 12), 0)
                h_tip.data.materials.append(red_glow); bind(h_tip, rig, "head")

            # 4) Jagged shoulder spikes & long sharp hand claws
            for s_name, sx in (("L", 1), ("R", -1)):
                for k, dz in enumerate((0.18, 0.0, -0.18)):
                    sp = _link(bpy.data.objects.new(f"{n}_ShSpike_{s_name}_{k}", _cyl_mesh(f"{n}_ShSpike_{s_name}_{k}", 0.10, 0.005, 0.42, 12)), coll)
                    sp.location = (sx * 1.95, dz, 3.95)
                    sp.rotation_euler = (0, math.radians(sx * 42), 0)
                    sp.data.materials.append(horn_mat); bind(sp, rig, f"upper_arm.{s_name}")
                for c_idx, dx_off in enumerate((-0.28, 0.0, 0.28)):
                    cl = _link(bpy.data.objects.new(f"{n}_Claw_{s_name}_{c_idx}", _cyl_mesh(f"{n}_Claw_{s_name}_{c_idx}", 0.055, 0.004, 0.55, 12)), coll)
                    cl.location = (sx * 1.5 + dx_off, -0.18, 1.78)
                    cl.rotation_euler = (math.radians(165), 0, 0)
                    cl.data.materials.append(red_glow if c_idx == 1 else fang_mat)
                    bind(cl, rig, f"upper_arm.{s_name}")


# ------------------------------------------------------------------ body + outfit
def build_body(rig, coll, skin, top_col, pants_col, details=(), accent=(0.95, 0.95, 0.95),
               sleeves="long", bottom="pants", shoes=None, emblem=(0.99, 0.80, 0.22), fabric=True):
    n = rig.name
    fab = (lambda m: add_bump(m, 90, 0.18, 6, tint=0.06)) if fabric else (lambda m: m)
    M = {
        "skin": new_mat(f"{n}_Skin", skin, 0.45, 0.4),
        "top": fab(new_mat(f"{n}_Top", top_col, 0.78, 0.25)),
        "pants": fab(new_mat(f"{n}_Pants", pants_col, 0.8, 0.25)),
        "trim": fab(new_mat(f"{n}_Trim", tuple(c * 0.86 for c in top_col), 0.8, 0.2)),
        "accent": fab(new_mat(f"{n}_Accent", accent, 0.6, 0.3)),
    }
    P = []

    def part(bone, name, size, center, mat, bevel=0.06):
        ob = rbox(f"{n}_{name}", coll, size, center, M[mat] if isinstance(mat, str) else mat, bevel)
        P.append((ob, bone)); return ob

    def shape(bone, name, pts, center, mat, th=0.04, rot=(0, 0, 0)):
        me, _ = _flat_shape(f"{n}_{name}", pts)
        ob = _link(bpy.data.objects.new(f"{n}_{name}", me), coll)
        ob.location = center; ob.rotation_euler = rot
        me.materials.append(M[mat] if isinstance(mat, str) else mat)
        so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = th
        P.append((ob, bone)); return ob

    D = set(details)
    part("neck", "Neck", (0.55, 0.55, 0.2), (0, 0, 4.02), "skin", 0.04)
    part("spine", "Torso", (2.0, 1.0, 2.0), (0, 0, 3.0), "top", 0.08)
    FY = -0.5   # torso front plane
    if "collar" in D:
        for sx in (-1, 1):
            shape("spine", f"Collar_{sx}", [(0, 0), (sx * 0.42, 0.04), (sx * 0.3, -0.3)], (sx * 0.06, FY - 0.03, 3.97), "accent", 0.035)
    elif "robe" not in D and "hood" not in D:
        part("spine", "CrewNeck", (0.9, 0.06, 0.12), (0, FY - 0.005, 3.93), "trim", 0.03)
    if "buttons" in D:
        for k in range(3):
            b = _link(bpy.data.objects.new(f"{n}_Btn{k}", _cyl_mesh(f"{n}_Btn{k}", 0.05, 0.05, 0.03, 16)), coll)
            b.location = (0, FY - 0.03, 3.6 - 0.32 * k); b.rotation_euler = (math.pi / 2, 0, 0)
            b.data.materials.append(M["accent"]); P.append((b, "spine"))
    if "tie" in D:
        part("spine", "TieKnot", (0.16, 0.06, 0.14), (0, FY - 0.04, 3.86), "accent", 0.03)
        shape("spine", "Tie", [(-0.08, 0), (0.08, 0), (0.12, -0.9), (0, -1.05), (-0.12, -0.9)], (0, FY - 0.04, 3.8), "accent", 0.04)
    if "badge" in D:
        gold = new_mat("Gold", (1.0, 0.76, 0.18), 0.22, 0.6); _bsdf(gold).inputs["Metallic"].default_value = 1.0
        star = [(0.16 * (1 if k % 2 == 0 else 0.45) * math.sin(math.pi * k / 5),
                 0.16 * (1 if k % 2 == 0 else 0.45) * math.cos(math.pi * k / 5)) for k in range(10)]
        shape("spine", "Badge", star, (-0.5, FY - 0.01, 3.45), gold, 0.05)
    if "belt" in D:
        part("spine", "Belt", (2.03, 1.03, 0.16), (0, 0, 2.1), new_mat("BeltBlack", (0.05, 0.05, 0.06), 0.35, 0.5), 0.03)
        gold = new_mat("Gold", (1.0, 0.76, 0.18), 0.22, 0.6); _bsdf(gold).inputs["Metallic"].default_value = 1.0
        part("spine", "Buckle", (0.24, 0.05, 0.2), (0, FY - 0.04, 2.1), gold, 0.02)
    if "pocket" in D:
        pk = add_bump(new_mat(f"{n}_Pocket", tuple(c * 0.93 for c in top_col), 0.95, 0.1), 260, 0.6, 8, tint=0.12)
        part("spine", "Pocket", (0.8, 0.06, 0.42), (0.2, FY - 0.01, 2.42), pk, 0.03)
    if "kangaroo" in D:
        part("spine", "Kangaroo", (1.2, 0.06, 0.5), (0, FY - 0.01, 2.4), "trim", 0.05)
    if "hood" in D:
        part("spine", "Hood", (1.5, 0.45, 0.4), (0, 0.42, 3.95), "trim", 0.18)
        for sx in (-1, 1):
            part("spine", f"String_{sx}", (0.05, 0.05, 0.5), (sx * 0.18, FY - 0.04, 3.65), "accent", 0.02)
    if "stripes" in D:
        for k, z in enumerate((3.35, 2.75)):
            part("spine", f"Stripe{k}", (2.02, 1.02, 0.2), (0, 0, z), "accent", 0.03)
    if "moon" in D:
        _crescent(rig, coll, P, emblem, center=(-0.48, FY - 0.03, 3.45))
    if "heart" in D:
        pts = []
        for k in range(40):
            t = 2 * math.pi * k / 40
            pts.append((0.016 * 16 * math.sin(t) ** 3, 0.016 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
        shape("spine", "Heart", pts, (0, FY - 0.01, 3.2), "accent", 0.035)
    if "robe" in D:
        fur = add_bump(new_mat(f"{n}_Fur", (0.97, 0.96, 0.93), 0.95, 0.2), 140, 0.8, 8, tint=0.12)
        spot = new_mat("FurSpot", (0.04, 0.04, 0.05), 0.6, 0.2)
        part("spine", "FurFront", (0.5, 0.08, 2.0), (0, FY - 0.03, 3.0), fur, 0.04)
        part("spine", "FurCollar", (2.2, 1.25, 0.28), (0, 0.06, 3.95), fur, 0.12)
        for k, (x, z) in enumerate(((-0.1, 3.5), (0.12, 3.1), (-0.08, 2.7), (0.1, 2.3), (-0.6, 3.97), (0.6, 3.97))):
            sp = rbox(f"{n}_Spot{k}", coll, (0.06, 0.03, 0.11), (x, FY - 0.08 if z < 3.9 else -0.66, z), spot, 0.015, 2)
            P.append((sp, "spine"))
        part("spine", "Cape", (2.3, 0.1, 3.3), (0, 0.6, 2.4), "top", 0.04)
        part("spine", "CapeFur", (2.32, 0.12, 0.22), (0, 0.6, 0.78), fur, 0.05)

    for s, sx in (("L", 1), ("R", -1)):
        ab = f"upper_arm.{s}"
        if sleeves == "long":
            part(ab, f"Arm_{s}", (0.98, 0.98, 2.0), (sx * 1.5, 0, 3.0), "top", 0.08)
            if "cuffs" in D:
                part(ab, f"Cuff_{s}", (1.0, 1.0, 0.16), (sx * 1.5, 0, 2.22), "trim", 0.04)
        else:
            part(ab, f"Arm_{s}", (0.96, 0.96, 2.0), (sx * 1.5, 0, 3.0), "skin", 0.08)
            if sleeves == "short":
                part(ab, f"Sleeve_{s}", (1.02, 1.02, 0.75), (sx * 1.5, 0, 3.62), "top", 0.07)
        lb = f"upper_leg.{s}"
        if bottom == "pants":
            part(lb, f"Leg_{s}", (0.98, 0.98, 2.0), (sx * 0.5, 0, 1.0), "pants", 0.07)
            if "cuffs" in D:
                part(lb, f"LegCuff_{s}", (1.0, 1.0, 0.16), (sx * 0.5, 0, 0.12), "trim", 0.04)
        else:
            part(lb, f"Leg_{s}", (0.96, 0.96, 2.0), (sx * 0.5, 0, 1.0), "skin", 0.07)
            if bottom == "shorts":
                part(lb, f"Shorts_{s}", (1.0, 1.0, 0.85), (sx * 0.5, 0, 1.58), "pants", 0.06)
        if shoes:
            sm = new_mat(f"{n}_Shoes", shoes, 0.45, 0.4)
            part(lb, f"Shoe_{s}", (1.02, 1.08, 0.35), (sx * 0.5, -0.03, 0.17), sm, 0.07)
    if bottom == "skirt":
        me = bpy.data.meshes.new(f"{n}_Skirt")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:     # flared box: waist 2.02 x 1.02, hem 2.4 x 1.35
            hem = v.co.z < 0
            v.co.x *= 2.4 if hem else 2.02
            v.co.y *= 1.35 if hem else 1.03
            v.co.z = 1.05 if hem else 2.02
        bm.to_mesh(me); bm.free()
        for p in me.polygons:
            p.use_smooth = True
        sk = _link(bpy.data.objects.new(f"{n}_Skirt", me), coll)
        me.materials.append(M["pants"])
        bv = sk.modifiers.new("Bevel", "BEVEL"); bv.width = 0.06; bv.segments = 3
        P.append((sk, "hips"))
    elif bottom != "pants":
        part("hips", "Waist", (2.0, 1.0, 0.2), (0, 0, 1.92), "pants", 0.04)
    for ob, bone in P:
        bind(ob, rig, bone)
    return M


def _crescent(rig, coll, P, rgb, center, r=0.27):
    """Crescent-moon patch: outer arc plus a radially inset inner arc (thick middle, pointed tips)."""
    n = rig.name
    alpha, W, turn, N = math.radians(50), 0.5 * r, math.radians(35), 48
    me = bpy.data.meshes.new(f"{n}_Moon")
    bm = bmesh.new()

    def rot(x, z):
        return (x * math.cos(turn) - z * math.sin(turn), x * math.sin(turn) + z * math.cos(turn))

    O, I = [], []
    for t in range(N + 1):
        u = t / N
        phi = alpha + u * (2 * math.pi - 2 * alpha)      # long way round, through the left side
        k = 1 - W * math.sin(math.pi * u) ** 0.8 / r
        ox, oz = r * math.cos(phi), r * math.sin(phi)
        O.append(bm.verts.new((rot(ox, oz)[0], 0, rot(ox, oz)[1])))
        if 0 < t < N:
            I.append(bm.verts.new((rot(ox * k, oz * k)[0], 0, rot(ox * k, oz * k)[1])))
    I = [O[0]] + I + [O[-1]]
    for t in range(N):
        vs = [O[t], O[t + 1], I[t + 1], I[t]]
        uniq = list(dict.fromkeys(vs))
        bm.faces.new(uniq)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    ob = _link(bpy.data.objects.new(f"{n}_Moon", me), coll)
    ob.location = center
    mat = add_bump(new_mat(f"{n}_Moon", rgb, 0.85, 0.2), 200, 0.35, 6, tint=0.1)
    me.materials.append(mat)
    so = ob.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.04
    P.append((ob, "spine"))
    return ob


# ------------------------------------------------------------------ cast presets + public API
LIGHT = (1.0, 0.82, 0.66)
TAN = (0.97, 0.67, 0.40)
BROWN_SKIN = (0.62, 0.40, 0.25)
PRESETS = {
    # hero: brown messy hair, sky-blue moon pajamas
    "Theo": dict(skin=TAN, hair=(0.50, 0.22, 0.09), hair_style="messy", hair_seed=3,
                 top=(0.48, 0.72, 0.98), pants=(0.44, 0.66, 0.95), details=("moon", "pocket", "cuffs")),
    # the town's king: black swept hair, gold crown, red robe with ermine fur
    "King": dict(skin=LIGHT, hair=(0.08, 0.06, 0.06), hair_style="swept", hat="crown",
                 top=(0.86, 0.1, 0.12), pants=(0.12, 0.12, 0.16), details=("robe",), shoes=(0.08, 0.06, 0.06),
                 face="confident"),
    # sleepy police officer: navy uniform, cap, badge, belt, black mustache
    "Officer": dict(skin=TAN, hair=(0.12, 0.08, 0.06), hair_style="under_cap", hat="police", extras=("mustache",),
                    top=(0.13, 0.24, 0.52), pants=(0.1, 0.16, 0.36), details=("badge", "belt", "buttons", "collar"),
                    accent=(0.1, 0.18, 0.42), shoes=(0.05, 0.05, 0.06), face="sleep"),
    "Mom": dict(skin=LIGHT, hair=(0.38, 0.18, 0.08), hair_style="long", top=(0.74, 0.5, 0.95),
                pants=(0.26, 0.4, 0.68), sleeves="short", details=("heart",), accent=(1.0, 0.45, 0.6),
                shoes=(0.98, 0.98, 0.98)),
    "Dad": dict(skin=TAN, hair=(0.3, 0.16, 0.08), hair_style="short", extras=("mustache",),
                top=(0.2, 0.5, 0.9), pants=(0.78, 0.66, 0.45), sleeves="short", details=("collar", "buttons"),
                accent=(0.95, 0.95, 0.95), shoes=(0.35, 0.2, 0.1)),
    # little sister: ginger pigtails, yellow striped top, pink skirt
    "Lily": dict(skin=LIGHT, hair=(0.86, 0.4, 0.14), hair_style="pigtails", top=(1.0, 0.82, 0.25),
                 pants=(0.98, 0.5, 0.68), sleeves="short", bottom="skirt", details=("stripes",),
                 accent=(1.0, 1.0, 1.0), shoes=(0.98, 0.4, 0.55), face="grin"),
    # best friend: black messy hair, glasses, green hoodie
    "Max": dict(skin=BROWN_SKIN, hair=(0.07, 0.06, 0.06), hair_style="messy", hair_seed=11, fringe_dir=-1.0,
                extras=("glasses",), top=(0.3, 0.78, 0.38), pants=(0.42, 0.45, 0.52),
                details=("hood", "kangaroo"), accent=(0.97, 0.97, 0.97), shoes=(0.95, 0.95, 0.95)),
    # the classic noob
    "Noob": dict(skin=(0.96, 0.8, 0.1), hair_style="bald", top=(0.05, 0.41, 0.75), pants=(0.64, 0.77, 0.24),
                 sleeves="none", details=(), fabric=False),
}


def build_character(name="Theo", location=(0, 0, 0), skin=TAN, hair=(0.47, 0.22, 0.10), hair_style="messy",
                    hair_seed=3, fringe_dir=1.0, top=(0.58, 0.76, 0.95), pants=(0.54, 0.71, 0.92),
                    details=(), accent=(0.95, 0.95, 0.95), sleeves="long", bottom="pants", shoes=None,
                    emblem=(0.99, 0.80, 0.22), hat=None, hat_color=None, extras=(), fabric=True, face="smile"):
    scene = bpy.context.scene
    old = bpy.data.collections.get(name)
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    for m in list(bpy.data.materials):
        if m.name.startswith(name + "_") and m.users == 0:
            bpy.data.materials.remove(m)
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    rig = build_armature(name, coll)
    rig["is_roblox_rig"] = True
    add_prop(rig, "face", FACE_INDEX[face], 0, len(FACE_NAMES) - 1, "expression atlas cell: " + ", ".join(FACE_NAMES))
    build_body(rig, coll, skin, top, pants, details, accent, sleeves, bottom, shoes, emblem, fabric)
    build_head(rig, coll, head_material(rig, skin))
    hm = add_bump(new_mat(f"{name}_HairMat", hair, 0.38, 0.5, coat=0.3), 3, 0.02, 1, kind="noise", tint=0.15)
    build_hair(rig, coll, hm, hair_style, hair_seed, fringe_dir)
    build_hat(rig, coll, hat, hat_color)
    build_extras(rig, coll, extras, hair)
    rig.location = location
    bpy.context.view_layer.update()
    return rig


def build_cast(names=None, spacing=3.6):
    names = names or list(PRESETS)
    rigs = []
    for i, nm in enumerate(names):
        x = (i - (len(names) - 1) / 2) * spacing
        rigs.append(build_character(nm, location=(x, 0, 0), **PRESETS[nm]))
    return rigs


def set_face(rig, name, frame=None):
    rig["face"] = FACE_INDEX[name]
    if frame is not None:
        rig.keyframe_insert('["face"]', frame=frame)
        _constant(rig, '["face"]')


def _fcurves(rig):
    ad = rig.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if len(getattr(act, "fcurves", []) or []):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _constant(rig, path):
    for fc in _fcurves(rig):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def blink(rig, frame, base="smile", length=3):
    set_face(rig, "blink", frame)
    set_face(rig, base, frame + length)


def talk(rig, start, end, base="smile", rate=3, seed=0):
    """Lip flap between the base face and the 'talk' face."""
    rnd = random.Random(seed)
    f, open_ = start, True
    while f < end:
        set_face(rig, "talk" if open_ else base, f)
        open_ = not open_
        f += rate + rnd.choice([0, 1, 2])
    set_face(rig, base, end)
