"""
Set builder: blocky stylized environments with named marks + lighting dressings.

Load AFTER blocky_rig.py (uses get_mat / box / disk):
    ns = {}
    exec(open(".../pipeline/blocky_rig.py").read(), ns)
    exec(open(".../pipeline/sets.py").read(), ns)
    coll = ns["build_set"]("street")          # -> collection "Set_street"
    ns["apply_dressing"]("street", "morning")

Conventions
  * Characters face -Y; the camera usually sits at -Y looking +Y. Backdrops are at +Y.
  * Marks are empties named  mark_<set>_<name>; rotation_euler.z is the default facing
    (0 = facing camera/-Y, 90 = facing +X, 180 = facing +Y/away).
  * Every light has custom props  dress_<dressing> = energy (missing -> 0 / hidden).
  * Window glass materials have  dress_<dressing> = emission strength.
"""
import bpy, bmesh, math, random
from mathutils import Vector

SET_NAMES = ["street", "town_square", "house_interior", "hero_room"]
DRESSINGS = {
    "street": ["day", "school_day", "morning"],
    "town_square": ["day"],
    "house_interior": ["kitchen", "grandpa"],
    "hero_room": ["night"],
}
# world background color (sRGB) + strength per dressing
WORLDS = {
    "day":        ((0.55, 0.78, 1.0), 1.0),
    "school_day": ((0.55, 0.78, 1.0), 1.0),
    "morning":    ((1.0, 0.78, 0.6), 0.9),
    "kitchen":    ((0.95, 0.9, 0.85), 0.6),
    "grandpa":    ((0.9, 0.8, 0.65), 0.45),
    "night":      ((0.05, 0.07, 0.16), 0.25),
}


# ---------------------------------------------------------------- helpers
def M(name, rgb, rough=0.6, emit=0.0, metal=0.0):
    return get_mat("SET_" + name, rgb, rough, emit, metal)


def B(coll, name, size, center, mat, bevel=0.04, rot=(0, 0, 0)):
    ob = box(name, coll, size, center, mat, bevel, 2)
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def prism(coll, name, w, d, h, center, mat, rot_z=0):
    """Gable roof: ridge along X."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in [(-w / 2, -d / 2, 0), (-w / 2, d / 2, 0), (-w / 2, 0, h),
                                   (w / 2, -d / 2, 0), (w / 2, d / 2, 0), (w / 2, 0, h)]]
    for f in [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]:
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = center
    ob.rotation_euler = (0, 0, math.radians(rot_z))
    bv = ob.modifiers.new("Bevel", "BEVEL"); bv.width = 0.08; bv.segments = 2
    return ob


def sphere(coll, name, r, center, mat, subdiv=2):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.location = center
    return ob


def cyl(coll, name, r, depth, center, mat, rot=(0, 0, 0), segs=24):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.location = center
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def checker_mat(name, c1, c2, scale=0.25, rough=0.8):
    m = bpy.data.materials.get("SET_" + name)
    if m: return m
    m = bpy.data.materials.new("SET_" + name); m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale, scale, scale)
    ck = nt.nodes.new("ShaderNodeTexChecker"); ck.inputs["Scale"].default_value = 1.0
    ck.inputs["Color1"].default_value = (*srgb(c1), 1); ck.inputs["Color2"].default_value = (*srgb(c2), 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], ck.inputs["Vector"])
    nt.links.new(ck.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (*srgb(c1), 1)
    return m


def glass_mat(name, rgb, dress):
    """Window glass that glows per dressing (dress = {dressing: strength})."""
    m = get_mat("SET_" + name, rgb, 0.1, emit=0.0)
    for k, v in dress.items():
        m[f"dress_{k}"] = v
    return m


def mark(coll, set_name, name, loc, facing_deg=0.0):
    e = bpy.data.objects.new(f"mark_{set_name}_{name}", None)
    e.empty_display_type = 'SINGLE_ARROW'
    e.empty_display_size = 1.5
    e.location = loc
    e.rotation_euler = (0, 0, math.radians(facing_deg))
    e["mark"] = name
    coll.objects.link(e)
    return e


def light(coll, name, kind, loc, rot=(0, 0, 0), color=(1, 1, 1), dress=None, size=1.0, spot_deg=45):
    ld = bpy.data.lights.new(name, kind)
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    if kind == 'SPOT':
        ld.spot_size = math.radians(spot_deg); ld.spot_blend = 0.4
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    ob = bpy.data.objects.new(name, ld); coll.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    for k, v in (dress or {}).items():
        ob[f"dress_{k}"] = v
    return ob


def tree(coll, name, x, y, s=1.0, seed=0):
    rnd = random.Random(seed)
    TR = M("Trunk", (0.45, 0.3, 0.2), 0.8)
    LF = M("Leaves", (0.32, 0.68, 0.28), 0.7)
    LF2 = M("Leaves2", (0.26, 0.6, 0.24), 0.7)
    B(coll, f"{name}_trunk", (0.9 * s, 0.9 * s, 4.5 * s), (x, y, 2.25 * s), TR, 0.08)
    B(coll, f"{name}_leaf1", (4.6 * s, 4.6 * s, 3.2 * s), (x, y, 5.6 * s), LF, 0.35, rot=(0, 0, rnd.uniform(0, 30)))
    B(coll, f"{name}_leaf2", (3.4 * s, 3.4 * s, 2.4 * s), (x, y, 7.9 * s), LF2, 0.3, rot=(0, 0, rnd.uniform(0, 30)))


def lamp_post(coll, name, x, y, dress):
    P = M("LampPole", (0.15, 0.16, 0.18), 0.4, metal=0.5)
    BULB = M("Bulb", (1.0, 0.85, 0.55), 0.3, emit=4.0)
    B(coll, f"{name}_base", (0.7, 0.7, 0.5), (x, y, 0.25), P, 0.05)
    B(coll, f"{name}_pole", (0.25, 0.25, 7.0), (x, y, 3.5), P, 0.04)
    B(coll, f"{name}_head", (1.0, 1.0, 0.25), (x, y, 7.1), P, 0.05)
    B(coll, f"{name}_bulb", (0.7, 0.7, 0.6), (x, y, 6.7), BULB, 0.1)
    light(coll, f"{name}_light", 'POINT', (x, y, 6.3), color=(1.0, 0.82, 0.55), dress=dress, size=0.5)


def house(coll, name, x, y_front, w=13, d=10, h=11.0, wall=(0.95, 0.88, 0.75), roof=(0.75, 0.25, 0.2),
          trim=(1, 1, 1), door=(0.45, 0.28, 0.18), chimney=True, glass=None):
    W = M(f"{name}_wall", wall, 0.85)
    R = M(f"{name}_roof", roof, 0.75)
    T = M("Trim_White", trim, 0.6)
    D = M(f"{name}_door", door, 0.6)
    G = glass or M("Glass", (0.6, 0.8, 0.95), 0.1)
    KN = M("Knob_Gold", (0.95, 0.75, 0.25), 0.3, metal=0.8)
    yc = y_front + d / 2
    B(coll, f"{name}_found", (w + 0.6, d + 0.6, 0.6), (x, yc, 0.3), M("Foundation", (0.55, 0.55, 0.58), 0.9), 0.05)
    B(coll, f"{name}_body", (w, d, h), (x, yc, 0.6 + h / 2), W, 0.05)
    B(coll, f"{name}_band", (w + 0.2, d + 0.2, 0.35), (x, yc, 0.6 + h), T, 0.04)
    prism(coll, f"{name}_roof", w + 1.6, d + 1.8, 4.0, (x, yc, 0.6 + h + 0.15), R)
    # door
    B(coll, f"{name}_doorframe", (3.6, 0.3, 7.0), (x, y_front - 0.05, 0.6 + 3.5), T, 0.04)
    B(coll, f"{name}_door", (3.0, 0.3, 6.5), (x, y_front - 0.12, 0.6 + 3.25), D, 0.04)
    B(coll, f"{name}_knob", (0.25, 0.2, 0.25), (x + 1.0, y_front - 0.3, 0.6 + 3.2), KN, 0.05)
    B(coll, f"{name}_step", (4.0, 1.4, 0.4), (x, y_front - 0.6, 0.2), M("Foundation", (0.55, 0.55, 0.58), 0.9), 0.04)
    # windows
    for wx in (-w / 2 + 2.3, w / 2 - 2.3):
        B(coll, f"{name}_win{wx:+.0f}_frame", (2.9, 0.3, 2.9), (x + wx, y_front - 0.05, 0.6 + h * 0.5), T, 0.04)
        B(coll, f"{name}_win{wx:+.0f}_glass", (2.4, 0.3, 2.4), (x + wx, y_front - 0.1, 0.6 + h * 0.5), G, 0.0)
        B(coll, f"{name}_win{wx:+.0f}_bar_v", (0.15, 0.32, 2.4), (x + wx, y_front - 0.15, 0.6 + h * 0.5), T, 0.0)
        B(coll, f"{name}_win{wx:+.0f}_bar_h", (2.4, 0.32, 0.15), (x + wx, y_front - 0.15, 0.6 + h * 0.5), T, 0.0)
        B(coll, f"{name}_win{wx:+.0f}_sill", (3.2, 0.6, 0.2), (x + wx, y_front - 0.25, 0.6 + h * 0.5 - 1.55), T, 0.04)
    if chimney:
        B(coll, f"{name}_chimney", (1.3, 1.3, 3.8), (x + w * 0.28, yc + d * 0.15, 0.6 + h + 2.6), M("Brick", (0.65, 0.3, 0.22), 0.9), 0.05)
    light(coll, f"{name}_porch", 'POINT', (x, y_front - 1.0, 0.6 + 7.6), color=(1.0, 0.8, 0.5),
          dress={"morning": 30, "night": 120}, size=0.3)


# ---------------------------------------------------------------- sets
def build_street(coll):
    s = "street"
    ROAD = M("Road", (0.24, 0.24, 0.27), 0.85)
    LINE = M("RoadLine", (1.0, 0.85, 0.25), 0.6)
    SIDE = checker_mat("Sidewalk", (0.78, 0.78, 0.8), (0.72, 0.72, 0.75), 0.25)
    CURB = M("Curb", (0.62, 0.62, 0.65), 0.8)
    GRASS = M("Grass", (0.42, 0.75, 0.32), 0.8)
    FENCE = M("Trim_White", (1, 1, 1), 0.6)
    glass = glass_mat("StreetGlass", (0.62, 0.8, 0.95), {"day": 0.0, "school_day": 0.0, "morning": 0.6, "night": 2.5})

    B(coll, "road", (120, 14, 0.2), (0, -7, -0.1), ROAD, 0)
    for i in range(-12, 13):
        B(coll, f"roadline_{i}", (3.0, 0.3, 0.05), (i * 5, -7, 0.02), LINE, 0)
    B(coll, "curb", (120, 0.6, 0.35), (0, -0.3, 0.17), CURB, 0.04)
    B(coll, "sidewalk", (120, 5.4, 0.3), (0, 2.7, 0.15), SIDE, 0)
    B(coll, "grass", (120, 40, 0.25), (0, 25.4, 0.12), GRASS, 0)
    B(coll, "grass_far", (120, 30, 0.2), (0, -29, -0.1), GRASS, 0)

    houses = [  # name, x, wall, roof, door
        ("houseA", -34, (0.98, 0.9, 0.72), (0.3, 0.45, 0.75), (0.25, 0.4, 0.6)),
        ("houseB", -17, (0.75, 0.88, 0.95), (0.75, 0.25, 0.2), (0.85, 0.2, 0.2)),
        ("houseC", 0, (0.98, 0.8, 0.8), (0.35, 0.3, 0.3), (0.3, 0.55, 0.35)),
        ("houseGrandpa", 17, (0.88, 0.8, 0.62), (0.42, 0.3, 0.22), (0.45, 0.28, 0.18)),
        ("houseE", 34, (0.85, 0.95, 0.8), (0.55, 0.25, 0.45), (0.95, 0.75, 0.25)),
    ]
    for i, (n, x, wall, roof, door) in enumerate(houses):
        house(coll, n, x, 9.0, wall=wall, roof=roof, door=door, chimney=(i % 2 == 0), glass=glass)
        # walkway + picket fence with gap at walkway
        B(coll, f"{n}_walk", (2.6, 3.6, 0.3), (x, 7.2, 0.17), SIDE, 0)
        for side in (-1, 1):
            fx0, fx1 = x + side * 1.8, x + side * 7.5
            n_p = 6
            for k in range(n_p):
                px = fx0 + (fx1 - fx0) * k / (n_p - 1)
                B(coll, f"{n}_picket_{side}_{k}", (0.3, 0.2, 1.6), (px, 5.6, 0.95), FENCE, 0.05)
            B(coll, f"{n}_rail_{side}", (abs(fx1 - fx0), 0.15, 0.2), ((fx0 + fx1) / 2, 5.65, 1.25), FENCE, 0.03)
    # trees + lamps
    for i, x in enumerate((-42, -25.5, -8.5, 8.5, 25.5, 42)):
        tree(coll, f"tree_{i}", x, 11.5 + (i % 2) * 2.5, 1.0 + (i % 3) * 0.1, i)
    for i, x in enumerate((-26, -14, 9, 26)):
        lamp_post(coll, f"lamp_{i}", x, 0.6, {"morning": 0, "night": 400})
    # far background trees
    for i in range(14):
        tree(coll, f"bgtree_{i}", -52 + i * 8, 28 + (i % 3) * 2, 1.3, 100 + i)
    # mailbox (for Hero) + hydrant
    MB = M("Mailbox", (0.25, 0.45, 0.8), 0.4, metal=0.3)
    B(coll, "mailbox_post", (0.3, 0.3, 3.0), (-8.0, 4.2, 1.5), M("Trunk", (0.45, 0.3, 0.2), 0.8), 0.04)
    B(coll, "mailbox_box", (1.2, 2.0, 1.1), (-8.0, 4.2, 3.4), MB, 0.3)
    B(coll, "mailbox_flag", (0.1, 0.5, 0.9), (-7.35, 4.5, 3.7), M("FlagRed", (0.9, 0.15, 0.15), 0.5), 0.03)
    HY = M("Hydrant", (0.9, 0.18, 0.15), 0.4)
    cyl(coll, "hydrant", 0.45, 1.6, (6.5, 4.4, 1.1), HY)
    sphere(coll, "hydrant_top", 0.45, (6.5, 4.4, 1.9), HY)
    # lights
    sm = light(coll, "sun", 'SUN', (0, 0, 30), rot=(52, 0, -30), color=(1.0, 0.96, 0.9),
               dress={"day": 4.0, "school_day": 4.0, "morning": 2.6, "night": 0.0}, size=2)
    sm["dress_rot_morning"] = (72, 0, 60)
    light(coll, "sky_fill", 'SUN', (0, 0, 30), rot=(60, 0, 150), color=(0.88, 0.92, 1.0),
          dress={"day": 0.8, "school_day": 0.8, "morning": 0.5, "night": 0.08}, size=5)
    # marks (stand on sidewalk z=0.3)
    z = 0.3
    mark(coll, s, "sidewalk_a", (-3.2, 2.6, z), -20)
    mark(coll, s, "sidewalk_b", (1.2, 2.6, z), 20)
    mark(coll, s, "sidewalk_c", (5.6, 2.6, z), 0)
    mark(coll, s, "mailbox", (-6.4, 2.8, z), 0)
    mark(coll, s, "path_start", (-6.0, 2.6, z), -90)
    mark(coll, s, "grandpa_door", (17.0, 6.6, z), 180)


def build_town_square(coll):
    s = "town_square"
    PLAZA = checker_mat("Plaza2", (0.68, 0.62, 0.55), (0.6, 0.55, 0.48), 0.2)
    WOOD = M("StageWood", (0.6, 0.38, 0.22), 0.6)
    GOLD = M("Gold", (1.0, 0.78, 0.25), 0.3, metal=0.9)
    GOLDGLOW = M("GoldGlow", (1.0, 0.8, 0.35), 0.3, emit=2.0)
    WALL = M("Backdrop", (0.2, 0.22, 0.5), 0.6)
    RED = M("BannerRed", (0.85, 0.18, 0.2), 0.6)
    WHITE = M("Trim_White", (1, 1, 1), 0.6)
    BULB = M("StringBulb", (1.0, 0.85, 0.5), 0.3, emit=6.0)

    B(coll, "plaza", (120, 120, 0.2), (0, 10, -0.1), PLAZA, 0)
    # stage
    B(coll, "stage", (20, 9, 1.5), (0, 13.5, 0.75), WOOD, 0.08)
    B(coll, "stage_trim", (20.2, 0.3, 0.3), (0, 9.0, 1.35), GOLD, 0.05)
    B(coll, "stage_step1", (7, 1.4, 0.5), (0, 8.3, 0.25), WOOD, 0.05)
    B(coll, "stage_step2", (7, 1.4, 1.0), (0, 9.0 - 0.0, 0.5), WOOD, 0.05)
    # backdrop + emblem
    B(coll, "backdrop", (24, 1.0, 14), (0, 18.5, 7), WALL, 0.1)
    B(coll, "backdrop_frame_top", (24.4, 1.2, 0.6), (0, 18.4, 14), GOLD, 0.08)
    for sx in (-1, 1):
        B(coll, f"backdrop_frame_{sx}", (0.6, 1.2, 14), (sx * 12.1, 18.4, 7), GOLD, 0.08)
        B(coll, f"banner_{sx}", (3.0, 0.2, 8.0), (sx * 7.5, 17.9, 8.5), RED, 0.05)
        B(coll, f"banner_stripe_{sx}", (3.0, 0.22, 0.5), (sx * 7.5, 17.85, 5.0), GOLD, 0.03)
    emb = sphere(coll, "emblem_core", 1.6, (0, 17.6, 9.0), GOLDGLOW, 3)
    emb.scale = (1, 0.3, 1)
    # podium + mic
    B(coll, "podium", (2.8, 1.5, 2.5), (0, 10.6, 1.5 + 1.25), WOOD, 0.08)
    B(coll, "podium_top", (3.2, 1.9, 0.25), (0, 10.6, 1.5 + 2.6), WOOD, 0.06)
    d = cyl(coll, "podium_badge", 0.6, 0.15, (0, 9.8, 1.5 + 1.5), GOLD, rot=(90, 0, 0))
    cyl(coll, "mic_stand", 0.06, 1.3, (0.6, 10.3, 1.5 + 3.2), M("LampPole", (0.15, 0.16, 0.18), 0.4, metal=0.5), rot=(-20, 0, 0))
    sphere(coll, "mic_head", 0.2, (0.6, 10.05, 1.5 + 3.85), M("LampPole", (0.15, 0.16, 0.18), 0.4, metal=0.5))
    # flag poles + string lights across stage front
    for sx in (-1, 1):
        B(coll, f"pole_{sx}", (0.35, 0.35, 16), (sx * 13.5, 9.5, 8), WHITE, 0.05)
        sphere(coll, f"pole_ball_{sx}", 0.5, (sx * 13.5, 9.5, 16.2), GOLD)
    n = 22
    for i in range(n + 1):
        t = i / n
        x = -13.5 + 27 * t
        zz = 14.5 - 3.0 * math.sin(math.pi * t)
        sphere(coll, f"bulb_{i}", 0.22, (x, 9.5, zz), BULB, 1)
    # town hall behind
    TH = M("TownHall", (0.92, 0.9, 0.84), 0.8)
    B(coll, "townhall", (40, 10, 20), (0, 30, 10), TH, 0.1)
    prism(coll, "townhall_roof", 42, 12, 6, (0, 30, 20), M("TownRoof", (0.3, 0.4, 0.6), 0.7))
    for i in range(8):
        cyl(coll, f"column_{i}", 0.8, 18, (-17.5 + i * 5, 24.6, 9), WHITE)
    # side shops with awnings
    shops = [(-26, (0.95, 0.55, 0.45), (0.95, 0.85, 0.3)), (26, (0.5, 0.75, 0.95), (0.9, 0.3, 0.3))]
    glass = glass_mat("ShopGlass", (0.7, 0.85, 0.95), {"day": 0.2})
    for x, wc, ac in shops:
        for j, y in enumerate((0, 12)):
            n_ = f"shop_{x}_{j}"
            B(coll, n_, (10, 10, 11), (x, y, 5.5), M(f"{n_}_wall", wc, 0.8), 0.08)
            sx = -1 if x > 0 else 1
            B(coll, f"{n_}_window", (0.3, 6, 3.5), (x + sx * 5.05, y, 3.0), glass, 0.0)
            B(coll, f"{n_}_awning", (2.2, 7.5, 0.4), (x + sx * 5.9, y, 5.6), M(f"{n_}_awn", ac, 0.6), 0.1, rot=(0, sx * -15, 0))
    for i, (x, y) in enumerate(((-16, 2), (16, 2), (-16, -10), (16, -10))):
        lamp_post(coll, f"lamp_{i}", x, y, {"day": 0})
    for i, (x, y) in enumerate(((-20, -16), (20, -16), (-34, 22), (34, 22))):
        tree(coll, f"tree_{i}", x, y, 1.1, i)
    # lights
    light(coll, "sun", 'SUN', (0, 0, 30), rot=(50, 0, -25), color=(1.0, 0.95, 0.88), dress={"day": 3.2}, size=2)
    light(coll, "sky_fill", 'SUN', (0, 0, 30), rot=(60, 0, 150), color=(0.88, 0.92, 1.0), dress={"day": 0.8}, size=5)
    for sx in (-1, 1):
        light(coll, f"stage_spot_{sx}", 'SPOT', (sx * 8, -2, 14), rot=(55, 0, sx * 30), color=(1.0, 0.9, 0.7),
              dress={"day": 1200}, size=0.6, spot_deg=30)
    # marks
    mark(coll, s, "podium", (0, 12.0, 1.5), 0)
    mark(coll, s, "stage_left", (-6, 13, 1.5), 0)
    mark(coll, s, "stage_right", (6, 13, 1.5), 0)
    mark(coll, s, "center", (0, 0.5, 0), 180)
    mark(coll, s, "crowd_front_l", (-3.5, 4.0, 0), 180)
    mark(coll, s, "crowd_front_r", (3.5, 4.0, 0), 180)
    mark(coll, s, "crowd_back_l", (-5.0, -3.0, 0), 180)
    mark(coll, s, "crowd_back_r", (5.0, -3.0, 0), 180)


def build_house_interior(coll):
    s = "house_interior"
    FLOOR = checker_mat("WoodFloor2", (0.72, 0.5, 0.32), (0.64, 0.43, 0.27), 0.55, 0.6)
    WALL = M("Wallpaper", (0.95, 0.88, 0.72), 0.9)
    BASE = M("Trim_White", (1, 1, 1), 0.6)
    CAB = M("Cabinet", (0.95, 0.95, 0.93), 0.5)
    TOPM = M("Countertop", (0.25, 0.25, 0.28), 0.3)
    WOOD = M("FurnWood", (0.55, 0.35, 0.2), 0.6)
    COUCH = M("Couch", (0.35, 0.55, 0.45), 0.85)
    RUG = M("Rug", (0.75, 0.3, 0.3), 0.95)
    STEEL = M("Steel", (0.8, 0.82, 0.85), 0.3, metal=0.8)
    glass = glass_mat("InteriorWindow3", (0.45, 0.7, 1.0), {"kitchen": 0.35, "grandpa": 0.25})

    B(coll, "floor", (24, 18, 0.3), (0, 0, -0.15), FLOOR, 0)
    B(coll, "wall_back", (24, 0.5, 11), (0, 9, 5.5), WALL, 0)
    B(coll, "wall_left", (0.5, 18, 11), (-12, 0, 5.5), WALL, 0)
    B(coll, "wall_right", (0.5, 18, 11), (12, 0, 5.5), WALL, 0)
    B(coll, "ceiling", (24.5, 18, 0.4), (0, 0, 11.2), M("Ceiling", (0.97, 0.95, 0.9), 0.9), 0)
    B(coll, "crown_back", (24, 0.5, 0.4), (0, 8.7, 10.8), BASE, 0.03)
    B(coll, "base_back", (24, 0.6, 0.6), (0, 8.7, 0.3), BASE, 0.03)
    B(coll, "base_left", (0.6, 18, 0.6), (-11.7, 0, 0.3), BASE, 0.03)
    B(coll, "base_right", (0.6, 18, 0.6), (11.7, 0, 0.3), BASE, 0.03)
    # window on back wall + curtains
    B(coll, "window_frame", (5.4, 0.6, 4.4), (3.5, 8.7, 6.0), BASE, 0.05)
    B(coll, "window_glass", (4.8, 0.6, 3.8), (3.5, 8.6, 6.0), glass, 0)
    B(coll, "window_bar", (0.15, 0.62, 3.8), (3.5, 8.48, 6.0), BASE, 0)
    for sx in (-1, 1):
        B(coll, f"curtain_{sx}", (1.2, 0.3, 5.0), (3.5 + sx * 3.1, 8.4, 5.9), M("Curtain", (0.85, 0.35, 0.3), 0.9), 0.1)
    # kitchen (left)
    B(coll, "counter", (8, 2.2, 3.0), (-7.5, 7.6, 1.5), CAB, 0.05)
    B(coll, "counter_top", (8.2, 2.5, 0.25), (-7.5, 7.5, 3.1), TOPM, 0.03)
    B(coll, "upper_cab", (8, 1.4, 2.6), (-7.5, 8.1, 7.3), CAB, 0.05)
    for i in range(4):
        B(coll, f"cab_handle_{i}", (0.6, 0.12, 0.12), (-10.5 + i * 2, 6.45, 2.5), STEEL, 0.03)
    B(coll, "fridge", (2.8, 2.4, 7.2), (-10.2, 3.6, 3.6), STEEL, 0.15)
    B(coll, "fridge_line", (2.82, 2.42, 0.06), (-10.2, 3.6, 4.8), M("FridgeLine", (0.3, 0.3, 0.32), 0.4), 0)
    B(coll, "stove_top", (2.4, 2.3, 0.1), (-5.0, 7.5, 3.25), M("StoveBlack", (0.08, 0.08, 0.08), 0.3), 0)
    # dining table + chairs (characters stand behind the table at y~3.3)
    B(coll, "table_top", (6.0, 3.2, 0.3), (-3.2, 1.3, 2.9), WOOD, 0.05)
    for lx in (-1, 1):
        for ly in (-1, 1):
            B(coll, f"table_leg_{lx}_{ly}", (0.3, 0.3, 2.75), (-3.2 + lx * 2.6, 1.3 + ly * 1.25, 1.37), WOOD, 0.03)
    B(coll, "tablecloth_runner", (6.05, 1.0, 0.05), (-3.2, 1.3, 3.08), M("Runner", (0.95, 0.95, 0.9), 0.8), 0)
    # meatloaf plate (kitchen dressing only)
    plate = cyl(coll, "prop_plate", 0.9, 0.12, (-4.4, 0.9, 3.15), M("Plate", (1, 1, 1), 0.3))
    loaf = B(coll, "prop_meatloaf", (1.2, 0.7, 0.45), (-4.4, 0.9, 3.42), M("Meatloaf", (0.45, 0.22, 0.12), 0.7), 0.15)
    sauce = B(coll, "prop_meatloaf_sauce", (1.15, 0.65, 0.08), (-4.4, 0.9, 3.66), M("Ketchup", (0.8, 0.12, 0.08), 0.3), 0.04)
    for o in (plate, loaf, sauce):
        o["only_dressing"] = "kitchen"
    # living (right): couch, coffee table, rug, lamp, clock, frames
    B(coll, "rug", (9, 6, 0.06), (5.5, 2.5, 0.03), RUG, 0)
    B(coll, "couch_base", (7, 2.8, 1.5), (6.0, 6.6, 0.95), COUCH, 0.2)
    B(coll, "couch_back", (7, 0.9, 2.4), (6.0, 7.7, 2.2), COUCH, 0.25)
    for sx in (-1, 1):
        B(coll, f"couch_arm_{sx}", (0.9, 2.8, 2.2), (6.0 + sx * 3.5, 6.6, 1.3), COUCH, 0.25)
    for i in (-1, 1):
        B(coll, f"cushion_{i}", (3.0, 2.3, 0.5), (6.0 + i * 1.55, 6.4, 1.9), M("Cushion", (0.45, 0.65, 0.55), 0.85), 0.2)
    B(coll, "coffee_table", (3.5, 1.8, 0.25), (6.0, 2.2, 1.4), WOOD, 0.05)
    for lx in (-1, 1):
        B(coll, f"coffee_leg_{lx}", (0.25, 1.5, 1.3), (6.0 + lx * 1.5, 2.2, 0.65), WOOD, 0.03)
    B(coll, "floorlamp_pole", (0.2, 0.2, 6.0), (10.5, 7.5, 3.0), STEEL, 0.03)
    B(coll, "floorlamp_shade", (1.6, 1.6, 1.3), (10.5, 7.5, 6.3), M("LampShade", (1.0, 0.92, 0.75), 0.6, emit=2.5), 0.2)
    clock = cyl(coll, "wall_clock", 0.9, 0.2, (-1.0, 8.65, 8.0), M("ClockFace", (1, 1, 1), 0.5), rot=(90, 0, 0))
    cyl(coll, "wall_clock_rim", 1.0, 0.15, (-1.0, 8.72, 8.0), WOOD, rot=(90, 0, 0))
    B(coll, "clock_hand_h", (0.08, 0.06, 0.5), (-1.0, 8.5, 8.2), M("Face_Black", (0.03, 0.025, 0.03), 0.35), 0)
    B(coll, "clock_hand_m", (0.6, 0.06, 0.07), (-0.75, 8.5, 8.0), M("Face_Black", (0.03, 0.025, 0.03), 0.35), 0)
    for i, (x, c) in enumerate(((7.5, (0.4, 0.6, 0.85)), (10.0, (0.95, 0.75, 0.35)))):
        B(coll, f"frame_{i}", (1.8, 0.2, 2.2), (x, 8.7, 6.5), WOOD, 0.04)
        B(coll, f"frame_pic_{i}", (1.4, 0.22, 1.8), (x, 8.65, 6.5), M(f"Pic{i}", c, 0.7), 0)
    # door on left wall
    B(coll, "door_frame", (0.6, 3.4, 5.4), (-11.75, -1.5, 2.7), BASE, 0.04)
    B(coll, "door", (0.4, 2.8, 5.0), (-11.6, -1.5, 2.5), M("DoorWood", (0.5, 0.32, 0.2), 0.6), 0.04)
    # lights
    light(coll, "ceiling", 'AREA', (0, 1, 10.6), rot=(0, 0, 0), color=(1.0, 0.92, 0.82),
          dress={"kitchen": 900, "grandpa": 600}, size=12)
    light(coll, "window_sun", 'SUN', (0, 0, 20), rot=(60, 0, 160), color=(1.0, 0.92, 0.8),
          dress={"kitchen": 2.5, "grandpa": 1.5}, size=3)
    light(coll, "lamp_glow", 'POINT', (10.5, 7.0, 6.0), color=(1.0, 0.75, 0.45), dress={"kitchen": 50, "grandpa": 250}, size=0.6)
    light(coll, "front_fill", 'AREA', (0, -14, 7), rot=(70, 0, 0), color=(1.0, 0.95, 0.9),
          dress={"kitchen": 600, "grandpa": 400}, size=14)
    # marks
    mark(coll, s, "table_a", (-4.6, 3.4, 0), 0)
    mark(coll, s, "table_b", (-1.6, 3.4, 0), 0)
    mark(coll, s, "couch", (6.0, 3.8, 0), 0)
    mark(coll, s, "door", (-9.5, -1.5, 0), 90)


def build_hero_room(coll):
    s = "hero_room"
    FLOOR = checker_mat("RoomFloor2", (0.62, 0.45, 0.32), (0.56, 0.4, 0.28), 0.55, 0.6)
    WALL = M("RoomWall", (0.45, 0.62, 0.78), 0.9)
    BASE = M("Trim_White", (1, 1, 1), 0.6)
    WOOD = M("FurnWood", (0.55, 0.35, 0.2), 0.6)
    MIRROR = M("Mirror", (0.95, 0.97, 1.0), 0.02, metal=1.0)
    night_glass = glass_mat("NightWindow3", (0.03, 0.05, 0.13), {"night": 2.2})

    B(coll, "floor", (20, 16, 0.3), (0, 0, -0.15), FLOOR, 0)
    B(coll, "wall_back", (20, 0.5, 11), (0, 8, 5.5), WALL, 0)
    B(coll, "wall_right", (0.5, 16, 11), (10, 0, 5.5), WALL, 0)
    B(coll, "ceiling", (20.5, 16, 0.4), (0, 0, 11.2), M("Ceiling", (0.97, 0.95, 0.9), 0.9), 0)
    # left wall in two pieces with a door opening at y=1.5 (width 3.2, height 5.6)
    B(coll, "wall_left_back", (0.5, 4.9, 11), (-10, 5.55, 5.5), WALL, 0)
    B(coll, "wall_left_front", (0.5, 7.9, 11), (-10, -4.05, 5.5), WALL, 0)
    B(coll, "wall_left_top", (0.5, 3.2, 5.4), (-10, 1.5, 8.3), WALL, 0)
    B(coll, "base_back", (20, 0.6, 0.6), (0, 7.7, 0.3), BASE, 0.03)
    B(coll, "door_frame_top", (0.8, 3.6, 0.4), (-10, 1.5, 5.75), BASE, 0.04)
    for sy in (-1, 1):
        B(coll, f"door_frame_{sy}", (0.8, 0.4, 5.6), (-10, 1.5 + sy * 1.8, 2.8), BASE, 0.04)
    # door panel with hinge at y=0.0 (rotate around Z to open; empty 'door_hinge')
    hinge = bpy.data.objects.new("door_hinge", None); coll.objects.link(hinge)
    hinge.location = (-10.0, 0.0, 0.0); hinge.empty_display_size = 0.6
    dp = B(coll, "door_panel", (0.3, 3.0, 5.5), (-10.0, 1.5, 2.75), M("DoorWood", (0.5, 0.32, 0.2), 0.6), 0.04)
    dk = B(coll, "door_knob", (0.3, 0.25, 0.25), (-9.75, 2.6, 2.7), M("Knob_Gold", (0.95, 0.75, 0.25), 0.3, metal=0.8), 0.05)
    for o in (dp, dk):
        o.parent = hinge
        o.location = Vector(o.location) - hinge.location
    # hallway behind the door (dim)
    B(coll, "hall_floor", (8, 8, 0.3), (-14.2, 1.5, -0.15), FLOOR, 0)
    B(coll, "hall_wall", (0.5, 8, 11), (-18, 1.5, 5.5), M("HallWall", (0.3, 0.32, 0.38), 0.9), 0)
    light(coll, "hall_light", 'POINT', (-14, 1.5, 7.5), color=(0.9, 0.85, 1.0), dress={"night": 120}, size=0.5)
    # mirror on back wall
    B(coll, "mirror_frame", (3.8, 0.4, 6.6), (-3.5, 7.6, 4.0), WOOD, 0.08)
    B(coll, "mirror_glass", (3.2, 0.42, 6.0), (-3.5, 7.55, 4.0), MIRROR, 0)
    try:
        pd = bpy.data.lightprobes.new("mirror_probe", 'PLANE')
        po = bpy.data.objects.new("mirror_probe", pd); coll.objects.link(po)
        po.location = (-3.5, 7.3, 4.0); po.rotation_euler = (math.radians(90), 0, 0)
        po.scale = (1.7, 3.1, 1)
    except Exception as e:
        print("planar probe unavailable:", e)
    # window (night) with moon
    B(coll, "window_frame", (4.6, 0.6, 4.2), (4.5, 7.7, 6.3), BASE, 0.05)
    B(coll, "window_glass", (4.0, 0.6, 3.6), (4.5, 7.62, 6.3), night_glass, 0)
    moon = sphere(coll, "moon", 0.6, (5.6, 7.27, 7.3), M("Moon", (1.0, 0.98, 0.85), 0.5, emit=3.0), 2)
    moon.scale = (1, 0.2, 1)
    B(coll, "window_bar", (0.15, 0.62, 3.6), (4.5, 7.5, 6.3), BASE, 0)
    # bed
    BL = M("Blanket", (0.95, 0.45, 0.3), 0.9)
    B(coll, "bed_frame", (5.2, 8.0, 1.4), (6.8, 3.6, 0.7), WOOD, 0.08)
    B(coll, "bed_head", (5.2, 0.6, 4.0), (6.8, 7.5, 2.0), WOOD, 0.1)
    B(coll, "mattress", (5.0, 7.6, 0.8), (6.8, 3.6, 1.8), M("Sheet", (0.97, 0.97, 0.97), 0.8), 0.2)
    B(coll, "blanket", (5.2, 5.0, 0.35), (6.8, 2.2, 2.25), BL, 0.15)
    B(coll, "pillow", (3.0, 1.4, 0.7), (6.8, 6.4, 2.45), M("Pillow", (1, 1, 1), 0.8), 0.3)
    # desk + lamp + chair
    B(coll, "desk_top", (4.5, 2.2, 0.25), (2.0, 6.6, 3.0), WOOD, 0.04)
    for lx in (-1, 1):
        B(coll, f"desk_leg_{lx}", (0.25, 2.0, 2.9), (2.0 + lx * 2.0, 6.6, 1.45), WOOD, 0.03)
    B(coll, "desk_lamp", (0.6, 0.6, 1.4), (3.6, 6.9, 3.8), M("DeskLamp", (1.0, 0.9, 0.6), 0.4, emit=4.0), 0.15)
    B(coll, "laptop", (1.6, 1.1, 0.12), (1.6, 6.4, 3.2), M("Laptop", (0.2, 0.2, 0.22), 0.4), 0.03)
    # posters + shelf
    for i, (x, c) in enumerate(((-7.5, (0.95, 0.35, 0.3)), (0.0, (0.35, 0.7, 0.4)))):
        B(coll, f"poster_{i}", (2.4, 0.1, 3.2), (x, 7.72, 7.0), M(f"Poster{i}", c, 0.7), 0.0)
        B(coll, f"poster_{i}_shape", (1.2, 0.12, 1.2), (x, 7.68, 7.2), M("PosterShape", (1, 1, 0.9), 0.7), 0.0)
    B(coll, "shelf", (4.0, 1.0, 0.25), (-7.0, 7.4, 4.8), WOOD, 0.03)
    for i, c in enumerate(((0.3, 0.5, 0.9), (0.9, 0.8, 0.2), (0.85, 0.3, 0.35))):
        B(coll, f"book_{i}", (0.35, 0.8, 1.1), (-8.3 + i * 0.4, 7.4, 5.45), M(f"Book{i}", c, 0.7), 0.02)
    B(coll, "rug", (6.5, 4.5, 0.06), (-1.0, 1.8, 0.03), M("RoomRug", (0.95, 0.85, 0.4), 0.95), 0)
    # lights (night)
    light(coll, "desk_light", 'POINT', (2.6, 5.4, 3.7), color=(1.0, 0.75, 0.45), dress={"night": 160}, size=0.5)
    light(coll, "moonlight", 'AREA', (4.5, 6.8, 8.0), rot=(-50, 0, 0), color=(0.55, 0.65, 1.0), dress={"night": 300}, size=3.5)
    light(coll, "front_fill", 'AREA', (0, -12, 7), rot=(70, 0, 0), color=(0.75, 0.8, 1.0), dress={"night": 650}, size=12)
    light(coll, "ceiling", 'AREA', (0, 1, 10.6), color=(1.0, 0.9, 0.75), dress={"night": 180}, size=8)
    # marks
    mark(coll, s, "mirror", (-3.5, 4.3, 0), 180)
    mark(coll, s, "bed", (4.0, 2.5, 0), 0)
    mark(coll, s, "door", (-12.0, 1.5, 0), 90)
    mark(coll, s, "window", (4.5, 5.0, 0), 180)
    mark(coll, s, "center", (-1.0, 1.0, 0), 0)


BUILDERS = {"street": build_street, "town_square": build_town_square,
            "house_interior": build_house_interior, "hero_room": build_hero_room}


# ---------------------------------------------------------------- public API
def build_set(name, scene=None):
    scene = scene or bpy.context.scene
    cname = f"Set_{name}"
    old = bpy.data.collections.get(cname)
    if old:
        for o in list(old.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    coll = bpy.data.collections.new(cname)
    scene.collection.children.link(coll)
    coll["set_name"] = name
    coll["dressings"] = ",".join(DRESSINGS[name])
    BUILDERS[name](coll)
    for o in coll.objects:
        if o.type == 'EMPTY' and o.name.startswith("mark_"):
            o.hide_render = True
    apply_dressing(name, DRESSINGS[name][0], scene)
    return coll


def apply_dressing(set_name, dressing, scene=None):
    scene = scene or bpy.context.scene
    coll = bpy.data.collections[f"Set_{set_name}"]
    for o in [x for x in coll.all_objects if x is not None]:
        if o.type == 'LIGHT':
            e = o.get(f"dress_{dressing}", 0.0)
            o.data.energy = e
            o.hide_render = o.hide_viewport = (e == 0)
            r = o.get(f"dress_rot_{dressing}")
            base = o.get("dress_rot_base")
            if base is None:
                o["dress_rot_base"] = [math.degrees(a) for a in o.rotation_euler]
                base = o["dress_rot_base"]
            o.rotation_euler = [math.radians(a) for a in (r if r is not None else base)]
        only = o.get("only_dressing")
        if only is not None:
            o.hide_render = o.hide_viewport = (only != dressing)
    # window glass glow
    for o in [x for x in coll.all_objects if x is not None]:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m and f"dress_{dressing}" in m:
                b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
                b.inputs["Emission Color"].default_value = b.inputs["Base Color"].default_value
                b.inputs["Emission Strength"].default_value = m[f"dress_{dressing}"]
    # world
    col, strength = WORLDS[dressing]
    w = bpy.data.worlds.get(f"World_{dressing}") or bpy.data.worlds.new(f"World_{dressing}")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*srgb(col), 1)
    bg.inputs[1].default_value = strength
    scene.world = w
    scene["dressing"] = dressing
    return w


def get_marks(set_name):
    coll = bpy.data.collections[f"Set_{set_name}"]
    return {o["mark"]: o for o in coll.objects if o is not None and o.get("mark")}


def place_at_mark(rig, set_name, mark_name, facing_deg=None):
    m = get_marks(set_name)[mark_name]
    rig.location = m.matrix_world.translation
    rig.rotation_euler = (0, 0, m.rotation_euler.z if facing_deg is None else math.radians(facing_deg))
