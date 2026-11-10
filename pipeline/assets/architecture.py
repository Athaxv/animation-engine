"""
Modular Roblox Architecture Assets:
  - Houses        (arch_house_suburban)
  - Apartments    (arch_apartment_block)
  - Shops         (arch_shop_bakery)
  - Schools       (arch_school_facade)
  - Towers        (arch_clock_tower)
  - Castles       (arch_castle_keep)
  - Walls         (arch_stone_wall)
  - Bridges       (arch_arched_bridge)
  - Gates         (arch_town_gate)

Each builder constructs its geometry inside `coll` relative to local origin (0, 0, 0)
with bottom contact at z = 0 and front facing -Y, returning the list of created objects.
"""
import math


def build_arch_house_suburban(ns, coll, name="HouseSuburban", wall=(1.0, 0.62, 0.32), roof="gable",
                              roof_col=(0.9, 0.32, 0.28), door_col=(0.3, 0.55, 0.95)):
    before = set(coll.objects)
    # house() places front at y_front and extends to y_front + d; center it around y=0
    grp = ns["house"](coll, name, 0.0, -7.0, w=18, d=14, h=10, wall=wall, roof=roof,
                      roof_col=roof_col, door_col=door_col, seed=2)
    created = [o for o in coll.objects if o not in before]
    return grp, created


def build_arch_apartment_block(ns, coll, name="ApartmentBlock", wall=(0.52, 0.74, 0.96)):
    blk, plastic, matte, glass, window, door = (
        ns["blk"], ns["plastic"], ns["matte"], ns["glass"], ns["window"], ns["door"]
    )
    before = set(coll.objects)
    w, d, h = 20.0, 14.0, 22.0
    wm = matte(f"{name}_Wall", wall)
    tm = plastic(f"{name}_Trim", (0.96, 0.96, 0.98), 0.45)
    dark = plastic(f"{name}_Dark", (0.18, 0.20, 0.25), 0.4)
    gl = glass(f"{name}_Glass", (0.5, 0.78, 1.0), interior=False)

    blk(coll, f"{name}_Body", (w, d, h), (0, 0, h / 2), wm, 0.12)
    blk(coll, f"{name}_Base", (w + 0.6, d + 0.6, 1.0), (0, 0, 0.5), tm, 0.06)
    blk(coll, f"{name}_RoofLedge", (w + 1.2, d + 1.2, 1.2), (0, 0, h + 0.6), tm, 0.1)
    door(coll, f"{name}_Entry", (0, -d / 2 - 0.1, 0.8), dark, plastic("Gold", (1.0, 0.8, 0.3)), "X", w=4.4, h=6.2)
    blk(coll, f"{name}_Canopy", (6.5, 2.6, 0.5), (0, -d / 2 - 1.2, 7.4), dark, 0.08)

    for floor_i, zc in enumerate((5.0, 11.5, 17.5)):
        for sx in (-6.0, 0.0, 6.0):
            if floor_i == 0 and abs(sx) < 1.0:
                continue
            window(coll, f"{name}_Win_{floor_i}_{sx}", (sx, -d / 2 - 0.08, zc), 3.0, 3.2, tm, gl, "X", sill=True)
            if floor_i > 0 and abs(sx) > 1.0:
                blk(coll, f"{name}_Balc_{floor_i}_{sx}", (3.8, 1.6, 0.3), (sx, -d / 2 - 0.8, zc - 1.8), tm, 0.04)
                blk(coll, f"{name}_Rail_{floor_i}_{sx}", (3.8, 0.15, 1.2), (sx, -d / 2 - 1.5, zc - 1.1), dark, 0.03)
    return None, [o for o in coll.objects if o not in before]


def build_arch_shop_bakery(ns, coll, name="ShopBakery", wall=(1.0, 0.88, 0.68), accent=(0.95, 0.32, 0.38)):
    blk, cyl, plastic, matte, glass, door = (
        ns["blk"], ns["cyl"], ns["plastic"], ns["matte"], ns["glass"], ns["door"]
    )
    before = set(coll.objects)
    w, d, h = 16.0, 12.0, 10.5
    wm = matte(f"{name}_Wall", wall)
    tm = plastic(f"{name}_Trim", (1.0, 1.0, 1.0), 0.4)
    ac = plastic(f"{name}_Accent", accent, 0.4)
    gl = glass(f"{name}_Display", (0.65, 0.88, 1.0), interior=False)

    blk(coll, f"{name}_Main", (w, d, h), (0, 0, h / 2), wm, 0.1)
    blk(coll, f"{name}_RoofParapet", (w + 0.8, d + 0.8, 1.4), (0, 0, h + 0.7), ac, 0.1)
    blk(coll, f"{name}_SignBoard", (9.5, 0.6, 2.2), (0, -d / 2 - 0.3, h + 1.2), tm, 0.08)
    door(coll, f"{name}_Door", (-4.2, -d / 2 - 0.1, 0.4), ac, plastic("Gold", (1.0, 0.8, 0.3)), "X", w=3.6, h=6.4)
    # Large display window
    blk(coll, f"{name}_ShowGlass", (6.8, 0.15, 4.4), (2.4, -d / 2 - 0.08, 4.0), gl, 0.02)
    blk(coll, f"{name}_ShowSill", (7.4, 0.8, 0.35), (2.4, -d / 2 - 0.3, 1.7), tm, 0.05)
    # Striped awning
    for i in range(8):
        col = ac if i % 2 == 0 else tm
        blk(coll, f"{name}_Awning_{i}", (1.8, 2.8, 0.4), (-6.3 + i * 1.8, -d / 2 - 1.3, 7.2), col, 0.06, rot=(18, 0, 0))
    return None, [o for o in coll.objects if o not in before]


def build_arch_school_facade(ns, coll, name="SchoolFacade"):
    blk, cyl, plastic, brick, glass, window, door, wall_clock = (
        ns["blk"], ns["cyl"], ns["plastic"], ns["brick"], ns["glass"], ns["window"], ns["door"], ns["wall_clock"]
    )
    before = set(coll.objects)
    w, d, h = 26.0, 14.0, 13.0
    bm = brick(f"{name}_Brick", (0.82, 0.34, 0.26))
    tm = plastic(f"{name}_Trim", (0.96, 0.95, 0.92), 0.45)
    gl = glass(f"{name}_Glass", (0.5, 0.78, 1.0), interior=False)

    blk(coll, f"{name}_Body", (w, d, h), (0, 0, h / 2), bm, 0.1)
    blk(coll, f"{name}_CenterWing", (9.0, d + 1.6, h + 3.0), (0, -0.8, (h + 3.0) / 2), bm, 0.1)
    blk(coll, f"{name}_Cornice", (w + 1.0, d + 1.0, 0.9), (0, 0, h + 0.45), tm, 0.08)
    blk(coll, f"{name}_Pediment", (9.8, 2.2, 1.2), (0, -0.8, h + 3.4), tm, 0.08)
    for sx in (-2.4, 2.4):
        cyl(coll, f"{name}_Pillar_{sx}", 0.45, 7.5, (sx, -d / 2 - 1.4, 4.2), tm, segs=20)
    door(coll, f"{name}_MainDoor", (0, -d / 2 - 0.9, 0.6), plastic("SchoolDoor", (0.25, 0.45, 0.78)), plastic("Gold", (1.0, 0.8, 0.3)), "X", w=4.4, h=6.8)
    wall_clock(coll, f"{name}_Clock", (0, -d / 2 - 1.7, h + 1.2), r=1.4, axis="X", rim=(0.95, 0.8, 0.25), hour=8)
    for sx in (-9.0, -5.8, 5.8, 9.0):
        for zc in (4.5, 9.5):
            window(coll, f"{name}_W_{sx}_{zc}", (sx, -d / 2 - 0.08, zc), 2.4, 3.0, tm, gl, "X", sill=True)
    return None, [o for o in coll.objects if o not in before]


def build_arch_clock_tower(ns, coll, name="ClockTower"):
    blk, cyl, plastic, matte, wall_clock = (
        ns["blk"], ns["cyl"], ns["plastic"], ns["matte"], ns["wall_clock"]
    )
    before = set(coll.objects)
    stone = matte(f"{name}_Stone", (0.86, 0.84, 0.78))
    trim = plastic(f"{name}_Trim", (0.97, 0.96, 0.94), 0.4)
    roof_m = plastic(f"{name}_Spire", (0.22, 0.34, 0.58), 0.35)
    gold = plastic(f"{name}_Gold", (1.0, 0.82, 0.25), 0.25)

    blk(coll, f"{name}_Plinth", (7.6, 7.6, 3.0), (0, 0, 1.5), trim, 0.12)
    blk(coll, f"{name}_Shaft", (6.2, 6.2, 16.0), (0, 0, 11.0), stone, 0.1)
    blk(coll, f"{name}_Belfry", (6.8, 6.8, 4.6), (0, 0, 21.3), trim, 0.12)
    wall_clock(coll, f"{name}_FaceFront", (0, -3.45, 21.3), r=1.8, axis="X", rim=(1.0, 0.8, 0.25), hour=3)
    cyl(coll, f"{name}_Spire", 4.6, 7.5, (0, 0, 27.3), roof_m, segs=4, r2=0.1)
    cyl(coll, f"{name}_Finial", 0.35, 1.8, (0, 0, 31.5), gold, segs=16)
    return None, [o for o in coll.objects if o not in before]


def build_arch_castle_keep(ns, coll, name="CastleKeep"):
    blk, cyl, plastic, matte, door = ns["blk"], ns["cyl"], ns["plastic"], ns["matte"], ns["door"]
    before = set(coll.objects)
    stone = matte(f"{name}_Stone", (0.68, 0.70, 0.75))
    dark = matte(f"{name}_DarkStone", (0.52, 0.54, 0.60))
    roof_m = plastic(f"{name}_Banner", (0.88, 0.16, 0.18), 0.4)

    w, d, h = 16.0, 14.0, 14.0
    blk(coll, f"{name}_Keep", (w, d, h), (0, 0, h / 2), stone, 0.1)
    door(coll, f"{name}_Gate", (0, -d / 2 - 0.1, 0.0), plastic("Oak", (0.45, 0.28, 0.15)), plastic("Gold", (1.0, 0.8, 0.3)), "X", w=4.8, h=7.2)
    # Crenellations along top front/back
    for i, x in enumerate(range(-7, 8, 2)):
        blk(coll, f"{name}_MerlonF_{i}", (1.2, 1.0, 1.4), (x, -d / 2 + 0.4, h + 0.7), dark, 0.06)
        blk(coll, f"{name}_MerlonB_{i}", (1.2, 1.0, 1.4), (x, d / 2 - 0.4, h + 0.7), dark, 0.06)
    # 4 corner turrets
    for sx in (-1, 1):
        for sy in (-1, 1):
            tx, ty = sx * (w / 2 + 0.5), sy * (d / 2 + 0.5)
            cyl(coll, f"{name}_Turret_{sx}_{sy}", 2.4, h + 3.0, (tx, ty, (h + 3.0) / 2), dark, segs=24)
            cyl(coll, f"{name}_Cone_{sx}_{sy}", 2.8, 4.2, (tx, ty, h + 5.1), roof_m, segs=24, r2=0.05)
    return None, [o for o in coll.objects if o not in before]


def build_arch_stone_wall(ns, coll, name="StoneWall", length=12.0, height=4.2):
    blk, matte, plastic = ns["blk"], ns["matte"], ns["plastic"]
    before = set(coll.objects)
    stone = matte(f"{name}_Wall", (0.76, 0.75, 0.72))
    cap = plastic(f"{name}_Cap", (0.88, 0.87, 0.84), 0.5)

    blk(coll, f"{name}_Span", (length, 1.2, height - 0.5), (0, 0, (height - 0.5) / 2), stone, 0.08)
    blk(coll, f"{name}_Coping", (length + 0.4, 1.5, 0.5), (0, 0, height - 0.25), cap, 0.06)
    for sx in (-1, 1):
        px = sx * (length / 2)
        blk(coll, f"{name}_Pillar_{sx}", (1.8, 1.8, height + 0.8), (px, 0, (height + 0.8) / 2), stone, 0.08)
        blk(coll, f"{name}_PillarCap_{sx}", (2.1, 2.1, 0.45), (px, 0, height + 1.0), cap, 0.06)
    return None, [o for o in coll.objects if o not in before]


def build_arch_arched_bridge(ns, coll, name="ArchedBridge", span=14.0, width=5.2):
    blk, wood, matte = ns["blk"], ns["wood"], ns["matte"]
    before = set(coll.objects)
    wm = wood(f"{name}_Plank", (0.78, 0.52, 0.30), 1.0)
    st = matte(f"{name}_Stone", (0.74, 0.74, 0.76))

    steps = 7
    dx = span / steps
    for i in range(steps):
        u = (i + 0.5) / steps - 0.5
        x = u * span
        arch_z = 1.6 * (1.0 - 4.0 * u * u)
        blk(coll, f"{name}_Deck_{i}", (dx + 0.15, width, 0.45), (x, 0, arch_z + 0.22), wm, 0.05)
        for sy in (-1, 1):
            ry = sy * (width / 2 - 0.25)
            blk(coll, f"{name}_Post_{i}_{sy}", (0.35, 0.35, 1.6), (x, ry, arch_z + 1.1), st, 0.04)
            blk(coll, f"{name}_Rail_{i}_{sy}", (dx + 0.2, 0.25, 0.25), (x, ry, arch_z + 1.85), wm, 0.04)
    return None, [o for o in coll.objects if o not in before]


def build_arch_town_gate(ns, coll, name="TownGate"):
    blk, cyl, ball, plastic, matte = ns["blk"], ns["cyl"], ns["ball"], ns["plastic"], ns["matte"]
    before = set(coll.objects)
    stone = matte(f"{name}_Stone", (0.82, 0.80, 0.76))
    iron = plastic(f"{name}_Iron", (0.16, 0.17, 0.20), 0.35)
    gold = plastic(f"{name}_Lantern", (1.0, 0.85, 0.35), 0.25)

    for sx in (-1, 1):
        px = sx * 5.2
        blk(coll, f"{name}_Pier_{sx}", (2.6, 2.6, 10.5), (px, 0, 5.25), stone, 0.1)
        blk(coll, f"{name}_Cap_{sx}", (3.1, 3.1, 0.8), (px, 0, 10.9), stone, 0.08)
        ball(coll, f"{name}_Lantern_{sx}", 0.55, (px - sx * 1.4, -1.2, 7.8), gold)
    blk(coll, f"{name}_Header", (13.4, 2.2, 1.8), (0, 0, 10.2), stone, 0.1)
    blk(coll, f"{name}_Crest", (5.0, 2.4, 1.4), (0, 0, 11.6), gold, 0.1)
    for gx in (-4.2, -3.2, 3.2, 4.2):
        cyl(coll, f"{name}_Bar_{gx}", 0.12, 9.2, (gx, 0, 4.6), iron, segs=12)
    return None, [o for o in coll.objects if o not in before]
