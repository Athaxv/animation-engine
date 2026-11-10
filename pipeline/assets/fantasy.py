"""
Modular Roblox Fantasy & Magical Assets:
  - Portals             (fan_portal_arcane)
  - Magical structures  (fan_magical_obelisk)
  - Crystals            (fan_crystal_cluster)
  - Floating platforms  (fan_floating_platform)
  - Ancient structures  (fan_ancient_ruins)
"""


def _emissive(ns, name, rgb, strength=3.5):
    m = ns["new_mat"](f"S_{name}", rgb, 0.2, 0.8)
    b = ns["_bsdf"](m)
    b.inputs["Emission Color"].default_value = (*ns["srgb"](rgb), 1.0)
    b.inputs["Emission Strength"].default_value = strength
    m["dress_day"] = (*rgb, strength * 0.6)
    m["dress_sunset"] = (*rgb, strength * 0.9)
    m["dress_night"] = (*rgb, strength * 1.4)
    return m


def build_fan_portal_arcane(ns, coll, name="PortalArcane"):
    blk, cyl, matte = ns["blk"], ns["cyl"], ns["matte"]
    before = set(coll.objects)
    stone = matte(f"{name}_Obsidian", (0.18, 0.16, 0.24))
    vortex = _emissive(ns, f"{name}_Vortex", (0.28, 0.72, 1.0), 4.0)
    rune = _emissive(ns, f"{name}_Rune", (0.72, 0.35, 1.0), 5.0)

    blk(coll, f"{name}_Base", (8.2, 3.2, 1.2), (0, 0, 0.6), stone, 0.12)
    for sx in (-1, 1):
        blk(coll, f"{name}_Pillar_{sx}", (1.6, 1.8, 8.2), (sx * 2.8, 0, 5.1), stone, 0.1)
        blk(coll, f"{name}_RuneStrip_{sx}", (0.35, 1.9, 6.4), (sx * 2.8, 0, 5.1), rune, 0.04)
    blk(coll, f"{name}_ArchTop", (7.6, 2.0, 1.6), (0, 0, 9.6), stone, 0.12)
    cyl(coll, f"{name}_Field", 2.4, 0.25, (0, 0, 5.2), vortex, rot=(90, 0, 0), segs=32).scale = (1.0, 1.45, 1.0)
    return None, [o for o in coll.objects if o not in before]


def build_fan_magical_obelisk(ns, coll, name="MagicalObelisk"):
    blk, cyl, matte = ns["blk"], ns["cyl"], ns["matte"]
    before = set(coll.objects)
    stone = matte(f"{name}_Stone", (0.22, 0.24, 0.32))
    glow = _emissive(ns, f"{name}_Glow", (0.25, 0.95, 0.82), 4.5)

    blk(coll, f"{name}_Pedestal", (4.4, 4.4, 1.6), (0, 0, 0.8), stone, 0.1)
    cyl(coll, f"{name}_Shaft", 1.1, 8.5, (0, 0, 6.2), stone, segs=4, r2=0.55)
    cyl(coll, f"{name}_Tip", 0.55, 1.6, (0, 0, 11.25), glow, segs=4, r2=0.02)
    for k, zc in enumerate((3.8, 6.5, 9.0)):
        cyl(coll, f"{name}_Ring_{k}", 1.65 - k * 0.2, 0.22, (0, 0, zc), glow, segs=24)
    return None, [o for o in coll.objects if o not in before]


def build_fan_crystal_cluster(ns, coll, name="CrystalCluster"):
    cyl, matte = ns["cyl"], ns["matte"]
    before = set(coll.objects)
    base_m = matte(f"{name}_Rock", (0.35, 0.34, 0.40))
    crys = _emissive(ns, f"{name}_Crystal", (0.85, 0.28, 0.98), 3.8)
    cyl(coll, f"{name}_Base", 2.2, 0.7, (0, 0, 0.35), base_m, segs=7, r2=1.8)
    specs = [
        (0.0, 0.0, 2.4, 0.65, 4.2, (0, 0, 0)),
        (-1.0, -0.3, 1.6, 0.45, 2.8, (8, -18, 10)),
        (1.0, 0.2, 1.5, 0.42, 2.6, (-10, 16, -12)),
        (0.2, -0.9, 1.2, 0.35, 2.0, (16, 6, 0)),
    ]
    for i, (x, y, z, r, h, rot) in enumerate(specs):
        cyl(coll, f"{name}_Shard_{i}", r, h, (x, y, z), crys, rot=rot, segs=6, r2=0.03)
    return None, [o for o in coll.objects if o not in before]


def build_fan_floating_platform(ns, coll, name="FloatingPlatform"):
    cyl, grass_mat, matte = ns["cyl"], ns["grass_mat"], ns["matte"]
    before = set(coll.objects)
    rock = matte(f"{name}_UnderRock", (0.46, 0.42, 0.38))
    gm = grass_mat()
    core = _emissive(ns, f"{name}_Core", (0.32, 0.85, 1.0), 3.5)

    # Floats above z=2.0 with inverted rock cone underneath
    cyl(coll, f"{name}_TopTurf", 4.8, 0.8, (0, 0, 5.6), gm, segs=12, r2=5.0)
    cyl(coll, f"{name}_RockCone", 0.6, 3.6, (0, 0, 3.4), rock, segs=9, r2=4.6)
    cyl(coll, f"{name}_FloatCrystal", 0.5, 1.4, (0, 0, 1.2), core, segs=6, r2=0.05)
    return None, [o for o in coll.objects if o not in before]


def build_fan_ancient_ruins(ns, coll, name="AncientRuins"):
    blk, cyl, matte = ns["blk"], ns["cyl"], ns["matte"]
    before = set(coll.objects)
    stone = matte(f"{name}_AncientStone", (0.78, 0.75, 0.68))
    rune = _emissive(ns, f"{name}_AltarGlow", (1.0, 0.72, 0.22), 3.0)

    blk(coll, f"{name}_FloorSlab", (10.0, 6.5, 0.6), (0, 0, 0.3), stone, 0.08)
    blk(coll, f"{name}_Altar", (2.4, 1.6, 1.8), (0, 0, 1.5), stone, 0.08)
    blk(coll, f"{name}_AltarGem", (0.9, 0.9, 0.4), (0, 0, 2.55), rune, 0.05)
    for sx, h_col in ((-3.8, 6.8), (-1.6, 4.2), (1.6, 6.8), (3.8, 3.5)):
        cyl(coll, f"{name}_Col_{sx}", 0.55, h_col, (sx, 1.8, 0.6 + h_col / 2), stone, segs=16)
    blk(coll, f"{name}_BrokenBeam", (5.2, 1.2, 0.9), (-0.5, 1.8, 7.8), stone, 0.08, rot=(0, 4, 0))
    return None, [o for o in coll.objects if o not in before]
