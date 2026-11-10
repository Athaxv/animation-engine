"""
Modular Roblox Environment & Nature Assets:
  - Roads         (env_road_segment)
  - Sidewalks     (env_sidewalk_tile)
  - Grass         (env_grass_patch)
  - Trees         (env_tree_oak)
  - Bushes        (env_bush_hedge)
  - Mountains     (env_mountain_peak)
  - Rocks         (env_rock_cluster)
  - Rivers        (env_river_stream)
  - Terrain       (env_terrain_hill)
  - Streetlights  (env_streetlight_classic)
  - Fences        (env_fence_picket)
  - Street Furniture (env_park_bench, env_fountain_plaza)
"""
import math


def build_env_road_segment(ns, coll, name="RoadSegment", length=24.0, width=10.0):
    blk, asphalt_mat, plastic = ns["blk"], ns["asphalt_mat"], ns["plastic"]
    before = set(coll.objects)
    blk(coll, f"{name}_Asphalt", (length, width, 0.3), (0, 0, 0.15), asphalt_mat(), 0.02)
    lm = plastic(f"{name}_LineYellow", (1.0, 0.85, 0.2), 0.5, 0)
    x = -length / 2 + 2.0
    k = 0
    while x <= length / 2 - 2.0:
        blk(coll, f"{name}_Dash_{k}", (3.0, 0.3, 0.06), (x, 0, 0.32), lm, 0.0)
        x += 6.0
        k += 1
    return None, [o for o in coll.objects if o not in before]


def build_env_sidewalk_tile(ns, coll, name="SidewalkTile", length=16.0, width=6.0):
    blk, plastic = ns["blk"], ns["plastic"]
    before = set(coll.objects)
    side = plastic(f"{name}_Concrete", (0.86, 0.86, 0.88), 0.8, 0.05)
    joint = plastic(f"{name}_Joint", (0.72, 0.72, 0.75), 0.8, 0)
    blk(coll, f"{name}_Slab", (length, width, 0.35), (0, 0, 0.175), side, 0.04)
    x = -length / 2 + 4.0
    k = 0
    while x < length / 2:
        blk(coll, f"{name}_Seam_{k}", (0.1, width, 0.04), (x, 0, 0.36), joint, 0.0)
        x += 4.0
        k += 1
    return None, [o for o in coll.objects if o not in before]


def build_env_grass_patch(ns, coll, name="GrassPatch", width=20.0, depth=20.0, with_flowers=True):
    blk, grass_mat, flowers = ns["blk"], ns["grass_mat"], ns["flowers"]
    before = set(coll.objects)
    blk(coll, f"{name}_Turf", (width, depth, 0.25), (0, 0, 0.125), grass_mat(), 0.03)
    if with_flowers:
        flowers(coll, f"{name}_Blossoms", 0, 0, seed=4, count=5)
    return None, [o for o in coll.objects if o not in before]


def build_env_tree_oak(ns, coll, name="TreeOak", scale=1.0, seed=1):
    before = set(coll.objects)
    ns["tree"](coll, name, 0.0, 0.0, s=scale, seed=seed)
    return None, [o for o in coll.objects if o not in before]


def build_env_bush_hedge(ns, coll, name="BushHedge", scale=1.0, seed=2):
    before = set(coll.objects)
    ns["bush"](coll, name, 0.0, 0.0, s=scale, seed=seed)
    return None, [o for o in coll.objects if o not in before]


def build_env_mountain_peak(ns, coll, name="MountainPeak", radius=14.0, height=24.0):
    cyl, plastic, matte = ns["cyl"], ns["plastic"], ns["matte"]
    before = set(coll.objects)
    rock = matte(f"{name}_Rock", (0.48, 0.50, 0.56))
    snow = plastic(f"{name}_Snow", (0.96, 0.98, 1.0), 0.35)
    cyl(coll, f"{name}_Base", radius, height * 0.72, (0, 0, height * 0.36), rock, segs=7, r2=radius * 0.32)
    cyl(coll, f"{name}_SnowCap", radius * 0.36, height * 0.34, (0, 0, height * 0.83), snow, segs=7, r2=0.2)
    return None, [o for o in coll.objects if o not in before]


def build_env_rock_cluster(ns, coll, name="RockCluster", seed=5):
    ball, matte = ns["ball"], ns["matte"]
    before = set(coll.objects)
    rm = matte(f"{name}_Stone", (0.55, 0.56, 0.60))
    ball(coll, f"{name}_Main", 1.6, (0.0, 0.0, 1.0), rm, scale=(1.3, 1.0, 0.75), lumpy=0.35, seed=seed)
    ball(coll, f"{name}_SideA", 1.0, (1.5, -0.5, 0.65), rm, scale=(1.1, 0.9, 0.7), lumpy=0.3, seed=seed + 1)
    ball(coll, f"{name}_SideB", 0.8, (-1.3, 0.6, 0.5), rm, scale=(1.0, 1.1, 0.65), lumpy=0.3, seed=seed + 2)
    return None, [o for o in coll.objects if o not in before]


def build_env_river_stream(ns, coll, name="RiverStream", length=32.0, width=6.5):
    blk, plastic, matte = ns["blk"], ns["plastic"], ns["matte"]
    before = set(coll.objects)
    water = plastic(f"{name}_Water", (0.14, 0.62, 0.95), rough=0.12, bump=0.04)
    foam = plastic(f"{name}_Foam", (0.78, 0.94, 1.0), rough=0.3, bump=0.0)
    bank = matte(f"{name}_Bank", (0.68, 0.66, 0.60))
    blk(coll, f"{name}_Channel", (length, width, 0.28), (0, 0, 0.14), water, 0.02)
    for k, x in enumerate((-length * 0.3, 0.0, length * 0.3)):
        blk(coll, f"{name}_Ripple_{k}", (4.5, 0.35, 0.04), (x, (k - 1) * 1.1, 0.29), foam, 0.0)
    for sy in (-1, 1):
        blk(coll, f"{name}_Bank_{sy}", (length, 0.95, 0.55), (0, sy * (width / 2 + 0.4), 0.275), bank, 0.06)
    return None, [o for o in coll.objects if o not in before]


def build_env_terrain_hill(ns, coll, name="TerrainHill", radius=12.0, height=5.5):
    cyl, grass_mat = ns["cyl"], ns["grass_mat"]
    before = set(coll.objects)
    gm = grass_mat()
    cyl(coll, f"{name}_Tier1", radius, height * 0.45, (0, 0, height * 0.225), gm, segs=16, r2=radius * 0.78)
    cyl(coll, f"{name}_Tier2", radius * 0.74, height * 0.55, (0, 0, height * 0.725), gm, segs=16, r2=radius * 0.42)
    return None, [o for o in coll.objects if o not in before]


def build_env_streetlight_classic(ns, coll, name="StreetlightClassic", facing=0):
    before = set(coll.objects)
    ns["street_lamp"](coll, name, 0.0, 0.0, facing=facing)
    return None, [o for o in coll.objects if o not in before]


def build_env_fence_picket(ns, coll, name="FencePicket", span=8.0):
    before = set(coll.objects)
    ns["picket_fence"](coll, name, -span / 2, span / 2, 0.0)
    return None, [o for o in coll.objects if o not in before]


def build_env_park_bench(ns, coll, name="ParkBench"):
    blk, wood, plastic = ns["blk"], ns["wood"], ns["plastic"]
    before = set(coll.objects)
    wm = wood(f"{name}_Wood", (0.82, 0.54, 0.30), 0.8)
    iron = plastic(f"{name}_Iron", (0.16, 0.18, 0.22), 0.4)
    blk(coll, f"{name}_Seat", (4.6, 1.8, 0.3), (0, 0, 1.85), wm, 0.06)
    blk(coll, f"{name}_Back", (4.6, 0.28, 1.8), (0, 0.78, 2.9), wm, 0.06)
    for sx in (-1.9, 1.9):
        blk(coll, f"{name}_LegF_{sx}", (0.3, 0.3, 1.8), (sx, -0.65, 0.9), iron, 0.04)
        blk(coll, f"{name}_LegB_{sx}", (0.3, 0.3, 3.4), (sx, 0.75, 1.7), iron, 0.04)
        blk(coll, f"{name}_Arm_{sx}", (0.3, 1.7, 0.25), (sx, 0.05, 2.45), iron, 0.04)
    return None, [o for o in coll.objects if o not in before]


def build_env_fountain_plaza(ns, coll, name="FountainPlaza"):
    cyl, ball, matte, glass = ns["cyl"], ns["ball"], ns["matte"], ns["glass"]
    before = set(coll.objects)
    stone = matte(f"{name}_Stone", (0.88, 0.87, 0.84))
    water = glass(f"{name}_Water", day=(0.30, 0.78, 1.0), night=(0.15, 0.45, 0.85), glow_day=0.4, glow_night=0.6, interior=True)
    cyl(coll, f"{name}_BasinOuter", 4.5, 1.4, (0, 0, 0.7), stone, segs=32)
    cyl(coll, f"{name}_WaterPool", 3.9, 1.2, (0, 0, 0.75), water, segs=32)
    cyl(coll, f"{name}_Pedestal", 1.1, 3.6, (0, 0, 1.8), stone, segs=24, r2=0.75)
    cyl(coll, f"{name}_UpperBowl", 2.2, 0.6, (0, 0, 3.6), stone, segs=24, r2=1.2)
    ball(coll, f"{name}_Spout", 0.75, (0, 0, 4.4), water, scale=(0.8, 0.8, 1.3))
    return None, [o for o in coll.objects if o not in before]
