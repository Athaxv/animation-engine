"""
Hand props, built procedurally (Roblox-plastic look). Load AFTER roblox_rig.py + roblox_sets.py.

    root = build_prop("sign:NO SNEEZING", coll, "Theo_sign")   # -> empty with the parts parented
    attach_to_hand(root, rig)                                     # right hand; shows best with pose "hold"

Props are modelled upright facing -Y with the grip at the origin. attach_to_hand binds them while the rig is in
pose "hold" (arms low and inward, in front of the belly), so in that pose the prop stands exactly upright
in front of the body facing the camera, below the face. Other poses carry it along with the arm.
"""
import bpy, math
from pathlib import Path
from mathutils import Vector

# every prop kind (vocab.py reads this list). "kind:TEXT" puts TEXT on sign / paper / flag.
PROP_KINDS = [
    # food
    "pizza", "burger", "ice_cream", "cup", "banana", "cake", "donut", "hotdog", "cookie", "apple", "egg",
    "soda", "coffee", "carrot",
    # everyday
    "phone", "letter", "book", "money", "gift", "balloon", "umbrella", "broom", "frying_pan", "hammer",
    "flashlight", "camera", "laptop", "remote", "toothbrush", "backpack", "briefcase", "key", "guitar",
    "megaphone", "microphone", "toilet_paper", "plunger", "baseball_bat", "teddy", "rubber_duck",
    "alarm_clock", "fishing_rod", "magnifier",
    # text
    "sign", "paper", "flag",
    # awards / magic / treasure
    "trophy", "medal", "wand", "potion", "gem", "gold_bar", "crystal_ball", "sword", "shield",
]
TEXT_PROPS = {"sign", "paper", "flag"}

FONT_CANDIDATES = [
    str((Path(__file__).resolve().parent.parent if "__file__" in globals() else ROOT if "ROOT" in globals() else Path.cwd()) / "public" / "fonts" / "caption.ttf"),
    r"C:\Windows\Fonts\seguibl.ttf",       # Segoe UI Black
    r"C:\Windows\Fonts\ariblk.ttf",        # Arial Black
]


def ui_font():
    import os
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            f = bpy.data.fonts.get(os.path.basename(p))
            return f or bpy.data.fonts.load(p, check_existing=True)
    return None


def _gold(name="PropGold"):
    m = plastic(name, (1.0, 0.76, 0.18), rough=0.25)
    b = _bsdf(m); b.inputs["Metallic"].default_value = 0.85
    return m


def _glow(name, rgb, strength=2.0):
    m = plastic(name, rgb, rough=0.3)
    b = _bsdf(m)
    b.inputs["Emission Color"].default_value = (*srgb(rgb), 1)
    b.inputs["Emission Strength"].default_value = strength
    return m


def _torus(coll, name, R, r, center, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=40, minor_segments=14,
                                     location=center, rotation=[math.radians(a) for a in rot])
    t = bpy.context.active_object
    t.name = name
    for c in list(t.users_collection):
        c.objects.unlink(t)
    coll.objects.link(t)
    for p in t.data.polygons:
        p.use_smooth = True
    t.data.materials.append(mat)
    return t


def _flat(coll, name, pts, mat, thick=0.12, center=(0, 0, 0)):
    """Flat extruded polygon in the XZ plane (points (x, z)), front face toward -Y."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    top = [bm.verts.new((x, 0, z)) for x, z in pts]
    bot = [bm.verts.new((x, thick, z)) for x, z in pts]
    bm.faces.new(top[::-1]); bm.faces.new(bot)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[i], top[j], bot[j], bot[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.location = center
    me.materials.append(mat)
    return ob


def _star(coll, name, r, center, mat, thick=0.12):
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    return _flat(coll, name, pts, mat, thick, center)


def _text(coll, name, body, center, size=0.42, width=2.3, col=(0.05, 0.05, 0.06)):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.extrude = 0.015
    f = ui_font()
    if f:
        cu.font = f
    # shrink long text to fit the board width (rough: 0.6 em per char)
    longest = max(len(l) for l in body.split("\n")) or 1
    cu.size = min(size, width / (0.62 * longest))
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob)
    ob.location = center
    ob.rotation_euler = (math.pi / 2, 0, 0)          # stand up, read from -Y
    cu.materials.append(matte(f"{name}Ink", col))
    return ob


def _parts(kind, coll, n, text=None):
    P = []
    add = P.append
    if kind == "phone":
        add(blk(coll, f"{n}_body", (0.55, 0.1, 1.0), (0, 0, 0.5), plastic("PropPhone", (0.08, 0.08, 0.1)), 0.06))
        add(blk(coll, f"{n}_screen", (0.46, 0.02, 0.86), (0, -0.055, 0.5), _glow("PropScreen", (0.35, 0.7, 1.0), 1.5), 0.02))
    elif kind == "letter":
        add(blk(coll, f"{n}_paper", (1.0, 0.04, 0.7), (0, 0, 0.35), matte("PropPaper", (0.98, 0.96, 0.9)), 0.02))
        add(ball(coll, f"{n}_seal", 0.12, (0, -0.04, 0.35), plastic("PropSeal", (0.9, 0.15, 0.2)), (1, 0.3, 1)))
    elif kind == "sign":
        # placard, centred on its grip; attach_to_hand moves it to the middle of the chest (CENTRED)
        add(blk(coll, f"{n}_board", (2.5, 0.12, 1.25), (0, 0, 0), plastic("PropBoard", (0.99, 0.99, 0.97)), 0.08))
        add(blk(coll, f"{n}_frame", (2.62, 0.08, 1.37), (0, 0.05, 0), plastic("PropBoardRim", (0.9, 0.2, 0.2)), 0.06))
        add(_text(coll, f"{n}_text", (text or "HELLO").upper(), (0, -0.08, 0), size=0.5, width=2.2))
    elif kind == "trophy":
        g = _gold()
        add(blk(coll, f"{n}_base", (0.7, 0.7, 0.25), (0, 0, 0.12), plastic("PropTrophyBase", (0.2, 0.15, 0.12)), 0.04))
        add(cyl(coll, f"{n}_stem", 0.1, 0.5, (0, 0, 0.5), g))
        add(cyl(coll, f"{n}_cup", 0.2, 0.7, (0, 0, 1.1), g, r2=0.45))
    elif kind == "medal":
        add(blk(coll, f"{n}_ribbon", (0.35, 0.03, 0.8), (0, 0, 0.75), fabric("PropRibbon", (0.2, 0.4, 0.95)), 0.02))
        add(cyl(coll, f"{n}_disc", 0.32, 0.07, (0, -0.03, 0.25), _gold(), rot=(90, 0, 0)))
    elif kind == "pizza":
        # a slice, tip down in the hand, crust on top, facing the camera
        add(_flat(coll, f"{n}_slice", [(-0.6, 1.25), (0.6, 1.25), (0.0, 0.0)], plastic("PropCheese", (1.0, 0.78, 0.3)), 0.1))
        add(blk(coll, f"{n}_crust", (1.35, 0.2, 0.22), (0, 0.04, 1.3), plastic("PropCrust", (0.85, 0.55, 0.25)), 0.08))
        for i, (x, z) in enumerate(((0.0, 0.95), (-0.22, 1.05), (0.2, 1.0), (0.0, 0.55))):
            add(cyl(coll, f"{n}_pep{i}", 0.11, 0.04, (x, -0.04, z), plastic("PropPepperoni", (0.85, 0.2, 0.15)),
                    rot=(90, 0, 0)))
    elif kind == "burger":
        bun = plastic("PropBun", (0.95, 0.62, 0.3))
        add(ball(coll, f"{n}_top", 0.55, (0, 0, 0.75), bun, (1, 1, 0.55)))
        add(cyl(coll, f"{n}_lettuce", 0.6, 0.08, (0, 0, 0.55), plastic("PropLettuce", (0.4, 0.8, 0.3))))
        add(cyl(coll, f"{n}_patty", 0.56, 0.2, (0, 0, 0.42), plastic("PropPatty", (0.4, 0.22, 0.12))))
        add(cyl(coll, f"{n}_bottom", 0.55, 0.2, (0, 0, 0.22), bun))
    elif kind == "book":
        add(blk(coll, f"{n}_cover", (0.9, 0.28, 1.2), (0, 0, 0.6), plastic("PropBookCover", (0.85, 0.2, 0.25)), 0.04))
        add(blk(coll, f"{n}_pages", (0.84, 0.3, 1.1), (0.05, 0, 0.6), matte("PropPages", (0.98, 0.96, 0.9)), 0.02))
    elif kind == "money":
        m = plastic("PropCash", (0.45, 0.78, 0.4))
        for i in range(4):
            add(blk(coll, f"{n}_bill{i}", (1.1, 0.5, 0.08), (0.03 * i, 0, 0.1 + 0.09 * i), m, 0.02))
        add(blk(coll, f"{n}_band", (0.2, 0.52, 0.4), (0, 0, 0.25), plastic("PropBand", (0.98, 0.85, 0.3)), 0.02))
    elif kind == "ice_cream":
        add(cyl(coll, f"{n}_cone", 0.32, 0.9, (0, 0, 0.45), plastic("PropCone", (0.9, 0.65, 0.35)), r2=0.03,
                rot=(180, 0, 0)))
        add(ball(coll, f"{n}_scoop", 0.38, (0, 0, 1.0), plastic("PropScoop", (1.0, 0.6, 0.75))))
    elif kind == "cup":
        add(cyl(coll, f"{n}_cup", 0.35, 0.8, (0, 0, 0.4), plastic("PropMug", (0.98, 0.98, 0.98)), r2=0.3))
        add(cyl(coll, f"{n}_drink", 0.32, 0.02, (0, 0, 0.8), plastic("PropDrink", (0.45, 0.25, 0.12))))
    elif kind == "balloon":
        add(cyl(coll, f"{n}_string", 0.02, 3.0, (0, 0, 1.5), matte("PropString", (0.95, 0.95, 0.95))))
        add(ball(coll, f"{n}_balloon", 0.75, (0, 0, 3.6), plastic("PropBalloon", (0.95, 0.2, 0.25), rough=0.2), (1, 1, 1.2)))
    elif kind == "gift":
        add(blk(coll, f"{n}_box", (1.0, 1.0, 0.9), (0, 0, 0.45), plastic("PropGift", (0.3, 0.55, 0.95)), 0.05))
        r = plastic("PropGiftRibbon", (0.98, 0.3, 0.4))
        add(blk(coll, f"{n}_rib1", (1.04, 0.2, 0.94), (0, 0, 0.45), r, 0.02))
        add(blk(coll, f"{n}_rib2", (0.2, 1.04, 0.94), (0, 0, 0.45), r, 0.02))
    elif kind == "sword":
        add(blk(coll, f"{n}_grip", (0.18, 0.18, 0.6), (0, 0, 0.1), plastic("PropGrip", (0.3, 0.18, 0.1)), 0.04))
        add(blk(coll, f"{n}_guard", (0.8, 0.2, 0.15), (0, 0, 0.45), _gold(), 0.04))
        add(blk(coll, f"{n}_blade", (0.28, 0.06, 2.6), (0, 0, 1.8), plastic("PropBlade", (0.8, 0.84, 0.9), rough=0.15), 0.03))
    elif kind == "magnifier":
        add(blk(coll, f"{n}_handle", (0.16, 0.16, 0.8), (0, 0, 0.2), plastic("PropMagHandle", (0.3, 0.18, 0.1)), 0.04))
        add(cyl(coll, f"{n}_rim", 0.5, 0.1, (0, 0, 1.05), plastic("PropMagRim", (0.15, 0.15, 0.18)), rot=(90, 0, 0)))
        add(cyl(coll, f"{n}_glass", 0.43, 0.11, (0, 0, 1.05), plastic("PropMagGlass", (0.75, 0.9, 1.0), rough=0.05),
                rot=(90, 0, 0)))
    elif kind == "microphone":
        add(cyl(coll, f"{n}_handle", 0.1, 0.9, (0, 0, 0.35), plastic("PropMicBody", (0.08, 0.08, 0.1)), r2=0.14))
        add(ball(coll, f"{n}_head", 0.22, (0, 0, 0.9), plastic("PropMicHead", (0.6, 0.62, 0.66), rough=0.3)))
    # ---------------------------------------------------------------- food
    elif kind == "banana":
        y = plastic("PropBanana", (1.0, 0.85, 0.2))
        for i, (x, z, rx) in enumerate(((0.0, 0.2, 0), (0.12, 0.65, -18), (0.32, 1.0, -40))):
            add(ball(coll, f"{n}_seg{i}", 0.2, (x, 0, z), y, (0.8, 0.8, 1.6)))
            P[-1].rotation_euler = (0, math.radians(rx), 0)
        add(cyl(coll, f"{n}_tip", 0.05, 0.15, (0.45, 0, 1.22), plastic("PropBananaTip", (0.35, 0.25, 0.1)), rot=(0, -40, 0)))
    elif kind == "cake":
        add(cyl(coll, f"{n}_base", 0.75, 0.55, (0, 0, 0.28), plastic("PropCakeBase", (1.0, 0.75, 0.82))))
        add(cyl(coll, f"{n}_icing", 0.78, 0.1, (0, 0, 0.6), plastic("PropIcing", (1.0, 0.98, 0.95))))
        add(cyl(coll, f"{n}_top", 0.5, 0.4, (0, 0, 0.85), plastic("PropCakeTop", (0.55, 0.32, 0.2))))
        add(cyl(coll, f"{n}_candle", 0.05, 0.4, (0, 0, 1.25), plastic("PropCandle", (0.3, 0.6, 1.0))))
        add(ball(coll, f"{n}_flame", 0.08, (0, 0, 1.52), _glow("PropFlame", (1.0, 0.7, 0.2), 6.0), (1, 1, 1.6)))
    elif kind == "donut":
        add(_torus(coll, f"{n}_dough", 0.42, 0.22, (0, 0, 0.62), plastic("PropDough", (0.92, 0.62, 0.32)), rot=(90, 0, 0)))
        add(_torus(coll, f"{n}_glaze", 0.42, 0.2, (0, -0.06, 0.62), plastic("PropGlaze", (1.0, 0.5, 0.75), rough=0.25), rot=(90, 0, 0)))
    elif kind == "hotdog":
        add(cyl(coll, f"{n}_bun", 0.25, 1.3, (0, 0, 0.3), plastic("PropBun", (0.95, 0.62, 0.3)), rot=(0, 90, 0)))
        add(cyl(coll, f"{n}_sausage", 0.16, 1.55, (0, -0.05, 0.48), plastic("PropSausage", (0.75, 0.25, 0.15)), rot=(0, 90, 0)))
        add(cyl(coll, f"{n}_mustard", 0.04, 1.2, (0, -0.12, 0.62), plastic("PropMustard", (1.0, 0.85, 0.1)), rot=(0, 90, 0)))
    elif kind == "cookie":
        add(cyl(coll, f"{n}_cookie", 0.5, 0.1, (0, 0, 0.5), plastic("PropCookie", (0.85, 0.6, 0.32)), rot=(90, 0, 0)))
        for i, (x, z) in enumerate(((-0.2, 0.6), (0.15, 0.7), (0.05, 0.35), (0.25, 0.45), (-0.15, 0.32))):
            add(ball(coll, f"{n}_chip{i}", 0.06, (x, -0.06, z), plastic("PropChoc", (0.3, 0.17, 0.1))))
    elif kind == "apple":
        add(ball(coll, f"{n}_apple", 0.4, (0, 0, 0.4), plastic("PropApple", (0.9, 0.12, 0.15), rough=0.3), (1, 1, 0.92)))
        add(cyl(coll, f"{n}_stem", 0.03, 0.2, (0, 0, 0.82), plastic("PropStem", (0.35, 0.22, 0.1))))
        add(ball(coll, f"{n}_leaf", 0.1, (0.1, 0, 0.86), plastic("PropLeaf", (0.3, 0.75, 0.25)), (1.4, 0.3, 0.6)))
    elif kind == "egg":
        add(ball(coll, f"{n}_egg", 0.3, (0, 0, 0.38), plastic("PropEgg", (0.98, 0.95, 0.88), rough=0.3), (1, 1, 1.3)))
    elif kind == "soda":
        add(cyl(coll, f"{n}_can", 0.22, 0.75, (0, 0, 0.38), plastic("PropCan", (0.9, 0.12, 0.15), rough=0.25)))
        add(cyl(coll, f"{n}_lid", 0.2, 0.04, (0, 0, 0.77), plastic("PropLid", (0.8, 0.82, 0.86), rough=0.2)))
        add(blk(coll, f"{n}_band", (0.3, 0.02, 0.22), (0, -0.215, 0.4), plastic("PropCanBand", (1, 1, 1)), 0.01))
    elif kind == "coffee":
        add(cyl(coll, f"{n}_cup", 0.22, 0.75, (0, 0, 0.38), plastic("PropPaperCup", (0.98, 0.97, 0.94)), r2=0.28))
        add(cyl(coll, f"{n}_sleeve", 0.27, 0.25, (0, 0, 0.4), plastic("PropSleeve", (0.6, 0.4, 0.25)), r2=0.285))
        add(cyl(coll, f"{n}_lid", 0.3, 0.08, (0, 0, 0.78), plastic("PropCupLid", (0.15, 0.15, 0.17))))
    elif kind == "carrot":
        add(cyl(coll, f"{n}_root", 0.03, 1.0, (0, 0, 0.5), plastic("PropCarrot", (1.0, 0.5, 0.1)), r2=0.18))
        for i, a in enumerate((-20, 0, 20)):
            add(blk(coll, f"{n}_leaf{i}", (0.06, 0.06, 0.45), (0, 0, 1.2), plastic("PropLeaf", (0.3, 0.75, 0.25)), 0.02, (0, a, 0)))
    # ---------------------------------------------------------------- everyday objects
    elif kind == "umbrella":
        add(cyl(coll, f"{n}_stick", 0.04, 2.6, (0, 0, 1.3), plastic("PropUmbStick", (0.15, 0.15, 0.17))))
        add(cyl(coll, f"{n}_canopy", 1.5, 0.8, (0, 0, 2.7), plastic("PropCanopy", (0.95, 0.2, 0.3)), r2=0.05, segs=8))
        add(_torus(coll, f"{n}_hook", 0.14, 0.04, (0.14, 0, 0.0), plastic("PropUmbStick", (0.15, 0.15, 0.17)), rot=(90, 0, 0)))
    elif kind == "broom":
        add(cyl(coll, f"{n}_stick", 0.06, 3.2, (0, 0, 1.0), wood("PropBroomStick", (0.75, 0.52, 0.3))))
        add(cyl(coll, f"{n}_brush", 0.15, 0.9, (0, 0, -0.95), plastic("PropBristle", (0.95, 0.8, 0.4)), r2=0.45))
    elif kind == "frying_pan":
        add(blk(coll, f"{n}_handle", (0.16, 0.12, 1.0), (0, 0, 0.3), plastic("PropPanHandle", (0.1, 0.1, 0.1)), 0.04))
        add(cyl(coll, f"{n}_pan", 0.7, 0.12, (0, 0, 1.45), plastic("PropPan", (0.2, 0.2, 0.22), rough=0.3), rot=(90, 0, 0)))
        add(cyl(coll, f"{n}_egg", 0.3, 0.05, (0, -0.08, 1.45), plastic("PropEggWhite", (1, 1, 1)), rot=(90, 0, 0)))
        add(ball(coll, f"{n}_yolk", 0.12, (0, -0.1, 1.45), plastic("PropYolk", (1.0, 0.7, 0.1)), (1, 0.5, 1)))
    elif kind == "hammer":
        add(blk(coll, f"{n}_handle", (0.16, 0.16, 1.2), (0, 0, 0.3), wood("PropHammerWood", (0.75, 0.52, 0.3)), 0.04))
        add(blk(coll, f"{n}_head", (0.8, 0.3, 0.3), (0, 0, 0.95), plastic("PropSteel", (0.6, 0.62, 0.66), rough=0.25), 0.04))
    elif kind == "flashlight":
        add(cyl(coll, f"{n}_body", 0.13, 0.9, (0, 0, 0.35), plastic("PropTorch", (0.95, 0.75, 0.1))))
        add(cyl(coll, f"{n}_head", 0.13, 0.3, (0, 0, 0.92), plastic("PropTorchHead", (0.15, 0.15, 0.17)), r2=0.22))
        add(cyl(coll, f"{n}_lens", 0.2, 0.03, (0, 0, 1.08), _glow("PropLens", (1.0, 0.95, 0.7), 8.0)))
    elif kind == "camera":
        add(blk(coll, f"{n}_body", (0.9, 0.45, 0.6), (0, 0, 0.6), plastic("PropCamBody", (0.12, 0.12, 0.14)), 0.08))
        add(cyl(coll, f"{n}_lens", 0.22, 0.3, (0, -0.32, 0.6), plastic("PropCamLens", (0.25, 0.25, 0.28)), rot=(90, 0, 0)))
        add(cyl(coll, f"{n}_glass", 0.15, 0.02, (0, -0.48, 0.6), plastic("PropCamGlass", (0.3, 0.45, 0.8), rough=0.05), rot=(90, 0, 0)))
        add(blk(coll, f"{n}_flash", (0.2, 0.1, 0.12), (0.28, 0, 0.95), plastic("PropCamFlash", (0.9, 0.9, 0.92)), 0.02))
    elif kind == "laptop":
        add(blk(coll, f"{n}_base", (1.4, 0.95, 0.07), (0, -0.4, 0.0), plastic("PropLaptop", (0.75, 0.77, 0.8), rough=0.3), 0.03))
        add(blk(coll, f"{n}_lid", (1.4, 0.07, 0.95), (0, 0.06, 0.48), plastic("PropLaptop", (0.75, 0.77, 0.8), rough=0.3), 0.03, (-12, 0, 0)))
        add(blk(coll, f"{n}_screen", (1.25, 0.02, 0.8), (0, 0.0, 0.48), _glow("PropLaptopScreen", (0.45, 0.75, 1.0), 1.4), 0.01, (-12, 0, 0)))
    elif kind == "remote":
        add(blk(coll, f"{n}_body", (0.3, 0.12, 1.0), (0, 0, 0.5), plastic("PropRemote", (0.12, 0.12, 0.14)), 0.05))
        add(cyl(coll, f"{n}_btn", 0.07, 0.04, (0, -0.07, 0.85), plastic("PropRedBtn", (0.95, 0.15, 0.15)), rot=(90, 0, 0)))
    elif kind == "toothbrush":
        add(blk(coll, f"{n}_handle", (0.12, 0.08, 1.1), (0, 0, 0.55), plastic("PropBrush", (0.3, 0.6, 1.0)), 0.04))
        add(blk(coll, f"{n}_bristles", (0.12, 0.15, 0.3), (0, -0.1, 1.0), plastic("PropBristles", (0.98, 0.98, 0.98)), 0.02))
    elif kind == "backpack":
        add(blk(coll, f"{n}_bag", (1.1, 0.6, 1.3), (0, 0, 0.65), fabric("PropBag", (0.95, 0.35, 0.2)), 0.2))
        add(blk(coll, f"{n}_pocket", (0.8, 0.2, 0.5), (0, -0.35, 0.45), fabric("PropBagPocket", (0.85, 0.3, 0.18)), 0.1))
    elif kind == "briefcase":
        add(blk(coll, f"{n}_case", (1.3, 0.35, 0.95), (0, 0, -0.55), plastic("PropCase", (0.35, 0.2, 0.12)), 0.06))
        add(blk(coll, f"{n}_handle", (0.4, 0.08, 0.08), (0, 0, 0.0), plastic("PropCaseHandle", (0.1, 0.1, 0.1)), 0.03))
        for s in (-1, 1):
            add(blk(coll, f"{n}_lock{s}", (0.12, 0.05, 0.1), (s * 0.4, -0.18, -0.2), _gold(), 0.01))
    elif kind == "key":
        g = _gold()
        add(_torus(coll, f"{n}_ring", 0.18, 0.05, (0, 0, 0.2), g, rot=(90, 0, 0)))
        add(blk(coll, f"{n}_shaft", (0.08, 0.06, 0.6), (0, 0, 0.65), g, 0.02))
        add(blk(coll, f"{n}_tooth", (0.15, 0.06, 0.08), (0.08, 0, 0.85), g, 0.01))
    elif kind == "guitar":
        add(ball(coll, f"{n}_body", 0.55, (0, 0, 0.4), wood("PropGuitar", (0.85, 0.45, 0.2)), (1, 0.35, 1.15)))
        add(cyl(coll, f"{n}_hole", 0.16, 0.05, (0, -0.19, 0.5), plastic("PropHole", (0.1, 0.06, 0.04)), rot=(90, 0, 0)))
        add(blk(coll, f"{n}_neck", (0.16, 0.1, 1.4), (0, -0.05, 1.4), wood("PropNeck", (0.4, 0.25, 0.12)), 0.02))
        add(blk(coll, f"{n}_peg", (0.22, 0.12, 0.3), (0, -0.05, 2.15), plastic("PropPeg", (0.15, 0.1, 0.06)), 0.04))
    elif kind == "megaphone":
        add(blk(coll, f"{n}_handle", (0.15, 0.15, 0.5), (0, 0, 0.25), plastic("PropMegaHandle", (0.12, 0.12, 0.14)), 0.04))
        add(cyl(coll, f"{n}_horn", 0.15, 1.0, (0, -0.3, 0.65), plastic("PropMega", (0.98, 0.98, 0.98)), rot=(90, 0, 0), r2=0.45))
        add(cyl(coll, f"{n}_rim", 0.47, 0.06, (0, -0.82, 0.65), plastic("PropMegaRim", (0.95, 0.2, 0.2)), rot=(90, 0, 0)))
    elif kind == "flag":
        add(cyl(coll, f"{n}_pole", 0.04, 2.6, (0, 0, 1.0), plastic("PropPole", (0.9, 0.9, 0.92))))
        add(blk(coll, f"{n}_cloth", (1.3, 0.04, 0.85), (0.67, 0, 1.85), fabric("PropFlag", (0.95, 0.2, 0.25)), 0.02))
        if text:
            add(_text(coll, f"{n}_text", text.upper(), (0.67, -0.04, 1.85), size=0.32, width=1.15, col=(1, 1, 1)))
    elif kind == "toilet_paper":
        add(cyl(coll, f"{n}_roll", 0.35, 0.55, (0, 0, 0.3), plastic("PropTP", (0.99, 0.99, 0.98), rough=0.7)))
        add(cyl(coll, f"{n}_core", 0.13, 0.57, (0, 0, 0.3), plastic("PropTPCore", (0.6, 0.45, 0.3))))
        add(blk(coll, f"{n}_tail", (0.5, 0.02, 0.6), (0.1, -0.35, -0.0), plastic("PropTP", (0.99, 0.99, 0.98), rough=0.7), 0.01))
    elif kind == "plunger":
        add(cyl(coll, f"{n}_stick", 0.06, 1.6, (0, 0, 0.6), wood("PropPlungerStick", (0.8, 0.6, 0.35))))
        add(cyl(coll, f"{n}_cup", 0.4, 0.4, (0, 0, 1.5), plastic("PropPlungerCup", (0.85, 0.12, 0.12)), r2=0.12))
    elif kind == "baseball_bat":
        add(cyl(coll, f"{n}_bat", 0.07, 2.2, (0, 0, 0.9), wood("PropBat", (0.85, 0.65, 0.4)), r2=0.16))
    elif kind == "teddy":
        br = fabric("PropTeddy", (0.65, 0.42, 0.25))
        add(ball(coll, f"{n}_body", 0.4, (0, 0, 0.45), br, (1, 0.8, 1.1)))
        add(ball(coll, f"{n}_head", 0.3, (0, 0, 1.05), br))
        for s in (-1, 1):
            add(ball(coll, f"{n}_ear{s}", 0.11, (s * 0.22, 0, 1.3), br))
        add(ball(coll, f"{n}_snout", 0.12, (0, -0.25, 1.0), fabric("PropSnout", (0.9, 0.75, 0.55))))
    elif kind == "rubber_duck":
        y = plastic("PropDuck", (1.0, 0.85, 0.1), rough=0.25)
        add(ball(coll, f"{n}_body", 0.4, (0, 0, 0.35), y, (1, 1.2, 0.8)))
        add(ball(coll, f"{n}_head", 0.25, (0, -0.15, 0.8), y))
        add(ball(coll, f"{n}_beak", 0.12, (0, -0.4, 0.78), plastic("PropBeak", (1.0, 0.5, 0.1)), (1, 1, 0.5)))
    elif kind == "alarm_clock":
        add(ball(coll, f"{n}_body", 0.45, (0, 0, 0.5), plastic("PropClock", (0.95, 0.2, 0.2)), (1, 0.6, 1)))
        add(cyl(coll, f"{n}_face", 0.35, 0.04, (0, -0.27, 0.5), plastic("PropClockFace", (0.98, 0.98, 0.95)), rot=(90, 0, 0)))
        for s in (-1, 1):
            add(ball(coll, f"{n}_bell{s}", 0.17, (s * 0.3, 0, 0.95), _gold(), (1, 1, 0.7)))
    elif kind == "fishing_rod":
        add(cyl(coll, f"{n}_rod", 0.05, 3.6, (0, 0, 1.6), plastic("PropRod", (0.2, 0.2, 0.22)), r2=0.02))
        add(cyl(coll, f"{n}_reel", 0.15, 0.12, (0.12, 0, 0.3), plastic("PropReel", (0.8, 0.8, 0.82)), rot=(0, 90, 0)))
    elif kind == "paper":
        add(blk(coll, f"{n}_sheet", (1.0, 0.03, 1.3), (0, 0, 0.65), matte("PropPaper", (0.98, 0.97, 0.93)), 0.01))
        add(_text(coll, f"{n}_text", (text or "A+").upper(), (0, -0.03, 0.7), size=0.6, width=0.9,
                  col=(0.85, 0.1, 0.1)))
    # ---------------------------------------------------------------- magic / treasure
    elif kind == "wand":
        add(cyl(coll, f"{n}_stick", 0.05, 1.3, (0, 0, 0.5), plastic("PropWand", (0.12, 0.08, 0.06))))
        add(_star(coll, f"{n}_star", 0.3, (0, 0.06, 1.3), _glow("PropStar", (1.0, 0.85, 0.2), 3.0)))
    elif kind == "potion":
        add(ball(coll, f"{n}_flask", 0.4, (0, 0, 0.42), plastic("PropFlask", (0.75, 0.9, 1.0), rough=0.05)))
        add(ball(coll, f"{n}_liquid", 0.33, (0, 0, 0.38), _glow("PropPotion", (0.6, 0.25, 1.0), 2.5), (1, 1, 0.85)))
        add(cyl(coll, f"{n}_neck", 0.11, 0.35, (0, 0, 0.9), plastic("PropFlask", (0.75, 0.9, 1.0), rough=0.05)))
        add(cyl(coll, f"{n}_cork", 0.1, 0.15, (0, 0, 1.12), plastic("PropCork", (0.65, 0.45, 0.25))))
    elif kind == "gem":
        add(ball(coll, f"{n}_gem", 0.45, (0, 0, 0.5), _glow("PropGem", (0.25, 0.8, 1.0), 0.8), (1, 0.6, 1.2)))
    elif kind == "gold_bar":
        add(cyl(coll, f"{n}_bar", 0.45, 0.35, (0, 0, 0.2), _gold(), rot=(0, 0, 45), segs=4, r2=0.32))
        P[-1].scale = (1.6, 0.8, 1)
    elif kind == "crystal_ball":
        add(cyl(coll, f"{n}_base", 0.35, 0.25, (0, 0, 0.12), _gold()))
        add(ball(coll, f"{n}_orb", 0.5, (0, 0, 0.75), _glow("PropOrb", (0.65, 0.4, 1.0), 1.2)))
    elif kind == "shield":
        add(cyl(coll, f"{n}_shield", 0.9, 0.12, (0, 0, 0.9), plastic("PropShield", (0.25, 0.45, 0.95)), rot=(90, 0, 0)))
        add(_torus(coll, f"{n}_rim", 0.9, 0.06, (0, 0, 0.9), _gold(), rot=(90, 0, 0)))
        add(_star(coll, f"{n}_emblem", 0.4, (0, -0.12, 0.9), _gold()))
    else:
        raise KeyError(f"unknown prop {kind!r}")
    return P


def build_prop(spec, coll, name):
    """spec: 'phone' or 'sign:SOME TEXT'. Returns the root empty (parts parented to it)."""
    kind, _, text = spec.partition(":")
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.5
    coll.objects.link(root)
    for ob in _parts(kind, coll, name, text or None):
        ob.parent = root
    root["prop"] = spec
    return root


GRIP_LOCAL = Vector((-1.5, -0.05, 1.45))       # bottom of the right arm, rig rest space


CENTRED = {"sign": 0.55}    # kinds held in the middle of the body: kind -> lift above the hand (studs)


def attach_to_hand(root, rig, scale=1.0):
    """Bind to the right arm, upright and facing -Y while the rig is in pose "hold".
    Call before the rig is animated (rig at rest, any transform)."""
    keep_loc, keep_rot, keep_scale = rig.location.copy(), rig.rotation_euler.copy(), rig.scale.copy()
    rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0); rig.scale = (1, 1, 1)
    hold = globals().get("POSES", {}).get("hold", {})
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_euler = [math.radians(a) for a in hold.get(pb.name, (0, 0, 0))]
    bpy.context.view_layer.update()
    pb = rig.pose.bones["upper_arm.R"]
    hand = pb.matrix @ pb.bone.matrix_local.inverted() @ GRIP_LOCAL
    kind = str(root.get("prop", "")).split(":")[0]
    if kind in CENTRED:
        hand = Vector((0.0, hand.y - 0.1, hand.z + CENTRED[kind]))
    root.location = hand
    root.rotation_euler = (0, 0, 0)
    root.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    bind(root, rig, "upper_arm.R")                  # roblox_rig.bind keeps the world transform
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
    rig.location, rig.rotation_euler, rig.scale = keep_loc, keep_rot, keep_scale
    bpy.context.view_layer.update()


def place_in_world(root, target, rot_deg=0.0, scale=1.0):
    """Stand a built prop on the ground: its bounding-box bottom-centre lands on `target` (world)."""
    bpy.context.view_layer.update()
    pts = []
    for ob in root.children_recursive:
        pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    off = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)) - root.matrix_world.translation
    rz = math.radians(rot_deg)
    off = Vector((off.x * math.cos(rz) - off.y * math.sin(rz), off.x * math.sin(rz) + off.y * math.cos(rz), off.z))
    root.rotation_euler = (0, 0, rz)
    root.scale = (scale, scale, scale)
    root.location = Vector(target) - off * scale
    return hi.z - lo.z


def prop_objects(root):
    return [root] + list(root.children_recursive)
