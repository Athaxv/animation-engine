"""
Reusable Roblox R6 hair assets (Phase 2).

Adds new silhouettes on top of the six legacy styles in ``pipeline/roblox_rig.py``
(``messy``, ``short``, ``under_cap``, ``swept``, ``long``, ``pigtails``, ``bald``).
Geometry is generated with the same helpers as the legacy rig (strand curves +
skull cap) so nothing is re-implemented here: ``roblox_rig`` passes a helper
namespace ``K`` into every builder.

Face-safety rules every style in this module obeys (measured by
``pipeline/characters/checks.py``):
  * fringe tips stop at or above the brow line (z >= HEAD_CZ + 0.38)
  * nothing enters the eye band (z 4.71-4.86, |x| <= 0.36, in front of the face)
  * side/back strands stay behind the face plane (y > -0.50)
"""

# how much skull cap each style keeps (1.0 = legacy "messy" volume)
HAIR_VOLUME = {
    "spiky": 0.92,
    "layered": 1.00,
    "side_swept": 0.88,
    "bob": 0.84,
    "ponytail": 0.82,
    "buzz": 0.52,
    "curly": 0.98,
    "mohawk": 0.66,
    "braids": 0.84,
    "wavy_long": 0.94,
}

HAIR_NOTES = {
    "spiky": "short tapered spikes standing up off the crown",
    "layered": "two stacked tiers of overlapping clumps",
    "side_swept": "long asymmetric sweep across the forehead",
    "bob": "chin-length straight curtain with a blunt fringe",
    "ponytail": "smooth pulled-back top with a tied tail behind",
    "buzz": "very short flat crop, close to the skull",
    "curly": "cluster of rounded curls over the skull",
    "mohawk": "shaved sides with a raised centre crest",
    "braids": "two beaded braids falling over the shoulders",
    "wavy_long": "long S-curved curtain down the back and shoulders",
}

# styles that already existed in pipeline/roblox_rig.py and stay there unchanged
LEGACY_STYLES = ["messy", "short", "under_cap", "swept", "long", "pigtails", "bald"]

# every hair style an identity may reference, in render order
ALL_STYLES = LEGACY_STYLES[:-1] + list(HAIR_VOLUME) + ["bald"]

# fringe tips must stay at or above this height so the brow/eyes stay readable
FRINGE_FLOOR = 0.38


def build_hair_extra(K, rig, coll, mat, style, seed=3, fringe_dir=1.0):
    """Build a Phase-2 hair style. Returns the root curve object (or None)."""
    import math
    import random

    strand = K["_strand"]
    cap_fn = K["_hair_cap"]
    sphere = K["_sphere_mesh"]
    cylinder = K["_cyl_mesh"]
    link = K["_link"]
    bind = K["bind"]
    new_mat = K["new_mat"]
    rbox = K["rbox"]
    HEAD_CZ = K["HEAD_CZ"]
    HEAD_R = K["HEAD_R"]

    n = rig.name
    cz, R = HEAD_CZ, HEAD_R
    rnd = random.Random(seed)
    j = lambda a: rnd.uniform(-a, a)
    s = fringe_dir

    volume = HAIR_VOLUME[style]
    cut_z = 0.1
    if style in ("buzz", "mohawk"):
        cut_z = 0.16
    top = cz + 0.2 + 0.62 * volume
    floor = cz + FRINGE_FLOOR

    # --- shared pieces -------------------------------------------------
    def make_curve(curve_name=None):
        cu = K["bpy"].data.curves.new(curve_name or f"{n}_HairExtra", 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.11
        cu.bevel_resolution = 5
        cu.use_fill_caps = True
        return cu

    def emit(cu):
        ob = link(K["bpy"].data.objects.new(cu.name, cu), coll)
        cu.materials.append(mat)
        bind(ob, rig, "head")
        return ob

    def clump_ring(cu, count, z_lo, z_hi, r_lo, r_hi, y_bias=0.25, thick=1.8):
        """Even ring of clumps hugging the skull; keeps the front clear of the face."""
        for i in range(count):
            a = 2 * math.pi * i / count
            ca, sa = math.cos(a), math.sin(a)
            front = max(0.0, -sa)
            z_end = z_hi - (z_hi - z_lo) * front
            z_end = max(z_end, floor)
            r_out = r_lo + (r_hi - r_lo) * rnd.random()
            strand(cu, [
                (ca * (R - 0.04), sa * (R - 0.04), top - 0.05),
                (ca * r_out, sa * r_out + y_bias * 0.1, (top + z_end) * 0.5),
                (ca * (r_out + 0.06), sa * (r_out + 0.06), z_end),
            ], thick + j(0.2), 0.12)

    if style in ("spiky", "layered", "side_swept", "bob", "ponytail", "curly", "braids", "wavy_long"):
        cap_fn(rig, coll, mat, 1.0, cut_z=cut_z)
    elif style == "buzz":
        cap_fn(rig, coll, mat, 1.0, cut_z=0.16)

    # --- style bodies --------------------------------------------------
    if style == "spiky":
        cu = make_curve()
        spikes = [
            (0.00, -0.10, 1.08, 0.0, 20),
            (-0.36, -0.16, 0.96, -20, 28), (0.36, -0.16, 0.96, 20, 28),
            (-0.54, 0.10, 0.78, -38, 38), (0.54, 0.10, 0.78, 38, 38),
            (-0.25, 0.36, 0.84, -12, -24), (0.25, 0.36, 0.84, 12, -24),
            (0.00, 0.22, 1.00, 0.0, -12),
            (-0.46, -0.36, 0.68, -44, 50), (0.46, -0.36, 0.68, 44, 50),
        ]
        for i, (sx, sy, h, tilt_y, tilt_x) in enumerate(spikes):
            sp = link(K["bpy"].data.objects.new(f"{n}_Spike{i}", cylinder(f"{n}_Spike{i}", 0.16, 0.004, h, 12)), coll)
            base_z = top - 0.18 + (0.0 if abs(sx) < 0.1 else 0.02)
            sp.location = (sx * R * 0.92, sy * R * 0.92, base_z + h * 0.35)
            sp.rotation_euler = (math.radians(tilt_x), math.radians(tilt_y), 0)
            sp.data.materials.append(mat)
            bind(sp, rig, "head")
        clump_ring(cu, 10, cz + 0.34, top - 0.12, R + 0.06, R + 0.14, thick=1.5)
        return emit(cu)

    if style == "layered":
        cu = make_curve()
        # upper tier: short clumps sitting on the crown
        for i in range(8):
            a = 2 * math.pi * i / 8 + 0.2
            ca, sa = math.cos(a), math.sin(a)
            strand(cu, [
                (ca * 0.22, sa * 0.22, top),
                (ca * 0.5, sa * 0.5, top - 0.10),
                (ca * 0.62, sa * 0.62, cz + 0.52),
            ], 2.1 + j(0.2), 0.18)
        # lower tier: longer clumps at the hairline, flipped outward
        clump_ring(cu, 12, cz + 0.30, cz + 0.46, R + 0.12, R + 0.22, y_bias=0.3, thick=2.0)
        # front fringe: layered bangs, two staggered rows above the brow
        for row, (zb, rr, xs) in enumerate(((floor + 0.10, 2.0, (-0.44, -0.22, 0.0, 0.22, 0.44)),
                                            (floor + 0.22, 1.6, (-0.33, -0.11, 0.11, 0.33)))):
            for x in xs:
                strand(cu, [
                    (x * 0.55, -0.10, top),
                    (x * 0.95 + s * 0.04, -0.56, zb + 0.20),
                    (x + s * 0.08, -0.70, zb),
                ], rr, 0.14)
        return emit(cu)

    if style == "side_swept":
        cu = make_curve()
        # deep side part on the -X side, heavy sweep toward +X
        for k, (x0, x1, z1) in enumerate(((-0.10, 0.30, floor + 0.16),
                                          (-0.02, 0.46, floor + 0.10),
                                          (0.08, 0.58, floor + 0.04),
                                          (-0.18, 0.16, floor + 0.22),
                                          (0.16, 0.66, floor - 0.06))):
            strand(cu, [
                (x0 * 0.5 - 0.16, -0.08, top + 0.02),
                (x0 * 0.6, -0.46, top - 0.06),
                (x1 * 0.85, -0.66, (top + z1) * 0.5),
                (x1, -0.66, max(z1, floor)),
            ], 2.2 - k * 0.12, 0.10)
        # long side lock falling past the cheek on the heavy side
        for k, y in enumerate((-0.28, 0.02, 0.30)):
            strand(cu, [
                (R - 0.06, y, cz + 0.46),
                (R + 0.10, y - 0.06, cz + 0.10),
                (R + 0.13, y - 0.10, cz - 0.45 - 0.1 * k),
                (R + 0.10, y - 0.06, cz - 0.85 - 0.12 * k),
            ], 1.9, 0.35)
        for x in (-0.34, -0.08, 0.18, 0.42):
            strand(cu, [(x, R - 0.12, top - 0.08), (x * 1.1, R + 0.12, cz + 0.16),
                        (x * 1.12, R + 0.06, cz - 0.10 + j(0.05))], 2.0, 0.4)
        return emit(cu)

    if style == "bob":
        cu = make_curve()
        # blunt fringe just above the brow
        for x in (-0.50, -0.30, -0.10, 0.10, 0.30, 0.50):
            strand(cu, [(x * 0.7, -0.08, top), (x * 0.98, -0.60, floor + 0.14),
                        (x, -0.70, floor + 0.02)], 1.9, 0.16)
        # chin-length curtain all the way round, tucked slightly forward at the front
        clump_ring(cu, 14, cz - 0.30, floor + 0.02, R + 0.10, R + 0.16, y_bias=0.2, thick=2.0)
        # the front pair is trimmed above the jaw so it frames the face
        for sx in (-1, 1):
            strand(cu, [
                (sx * (R - 0.05), -0.40, cz + 0.42),
                (sx * (R + 0.10), -0.46, cz + 0.02),
                (sx * (R + 0.08), -0.42, cz - 0.36),
            ], 1.9, 0.3)
        return emit(cu)

    if style == "ponytail":
        cu = make_curve()
        # smooth pulled-back top: strands run from the hairline to the tie
        for k, x in enumerate((-0.42, -0.21, 0.0, 0.21, 0.42)):
            strand(cu, [
                (x * 0.85, -0.24, top - 0.02),
                (x * 0.7, 0.10, top + 0.06),
                (x * 0.28, 0.46, cz + 0.62),
                (x * 0.10, 0.58, cz + 0.50),
            ], 2.0, 0.3)
        # slicked-back hairline: no bangs, so the style reads as "pulled back"
        # from the front even though the tail itself is behind the head
        for sx in (-1, 1):
            for k, dy in enumerate((0.0, 0.06)):
                strand(cu, [
                    (sx * 0.30, -0.50 - dy * 0.3, top - 0.26),
                    (sx * 0.52, -0.28, top - 0.06),
                    (sx * 0.62, 0.18, cz + 0.34),
                ], 1.5 - 0.3 * k, 0.30)
            strand(cu, [
                (sx * 0.10, -0.52, top - 0.20),
                (sx * 0.26, -0.34, top - 0.02),
                (sx * 0.34, 0.14, cz + 0.42),
            ], 1.4, 0.35)
        # tie
        tie_mat = mat
        tie = link(K["bpy"].data.objects.new(f"{n}_HairTie", cylinder(f"{n}_HairTie", 0.16, 0.16, 0.14, 20)), coll)
        tie.location = (0.0, 0.62, cz + 0.46)
        tie.rotation_euler = (math.radians(96), 0, 0)
        tie.data.materials.append(tie_mat)
        bind(tie, rig, "head")
        # tail: thick bundle down the back
        for k, x in enumerate((-0.10, 0.0, 0.10)):
            strand(cu, [
                (x, 0.62, cz + 0.46),
                (x * 1.4, 0.86, cz + 0.10),
                (x * 1.9, 0.92, cz - 0.42),
                (x * 2.4, 0.86, cz - 0.95 - 0.08 * k),
            ], 2.6, 0.5)
        # the tail also swings forward over the shoulder so the style reads head-on
        for k, dy in enumerate((0.0, 0.05)):
            strand(cu, [
                (0.06, 0.60 - dy, cz + 0.44),
                (0.34, 0.34 - dy, cz + 0.18),
                (0.50, -0.28 - dy, cz - 0.40),
                (0.44, -0.42 - dy, cz - 0.94 - 0.06 * k),
            ], 2.0 - 0.3 * k, 0.4)
        return emit(cu)

    if style == "buzz":
        cu = make_curve()
        # Uniform stubble shell. It hugs the scalp (so it never reads as a
        # headband) and only hangs low at the sides and back; the front hairline
        # is held at z = 4.94, safely above the painted eye band (top 4.91).
        for i in range(20):
            a = 2 * math.pi * i / 20
            ca, sa = math.cos(a), math.sin(a)
            z_end = 4.94 if abs(ca) < 0.55 else 4.94 - 0.46 * (1.0 - max(0.0, -sa))
            strand(cu, [
                (ca * (R - 0.03), sa * (R - 0.03), top - 0.04),
                (ca * (R + 0.02), sa * (R + 0.02) + 0.01, (top + z_end) * 0.5),
                (ca * (R + 0.055), sa * (R + 0.055), z_end),
            ], 1.5, 0.16)
        return emit(cu)

    if style == "curly":
        cu = make_curve()
        curls = []
        for ring, (count, rz, rr) in enumerate(((9, 0.62, 0.20), (7, 0.80, 0.17), (4, 0.94, 0.15))):
            for i in range(count):
                a = 2 * math.pi * i / count + ring * 0.4
                ca, sa = math.cos(a), math.sin(a)
                cz_l = cz + 0.20 + rz * 0.62 * volume
                if sa < -0.55 and cz_l < floor:
                    continue
                curls.append((ca * rr * 2.6, sa * rr * 2.6 + 0.04, cz_l, rr))
        for i, (x, y, z, rr) in enumerate(curls):
            b = link(K["bpy"].data.objects.new(f"{n}_Curl{i}", sphere(f"{n}_Curl{i}", rr, 16)), coll)
            b.location = (x, y, z)
            b.scale = (1.0, 1.0, 0.85)
            b.data.materials.append(mat)
            bind(b, rig, "head")
        return emit(cu)

    if style == "mohawk":
        cu = make_curve()
        # sides stay genuinely shaved -- no stubble band, so the crest is unambiguous
        # centre crest: a wide ridge of cones marching front to back
        for i, (yy, h, tilt) in enumerate(((-0.50, 0.80, -30), (-0.24, 1.00, -16), (0.04, 1.14, 0),
                                           (0.30, 1.00, 18), (0.54, 0.78, 34))):
            sp = link(K["bpy"].data.objects.new(f"{n}_Crest{i}", cylinder(f"{n}_Crest{i}", 0.25, 0.004, h, 14)), coll)
            sp.location = (0.0, yy * R, top - 0.20 + h * 0.4)
            sp.rotation_euler = (math.radians(tilt), 0, math.radians(90))
            sp.data.materials.append(mat)
            bind(sp, rig, "head")
        return emit(cu)

    if style == "braids":
        cu = make_curve()
        for x in (-0.44, -0.22, 0.0, 0.22, 0.44):
            strand(cu, [(x * 0.8, -0.08, top), (x, -0.58, floor + 0.12), (x * 0.9, -0.66, floor + 0.02)], 1.7, 0.18)
        clump_ring(cu, 12, cz + 0.28, floor, R + 0.08, R + 0.14, thick=1.8)
        bead = new_mat(f"{n}_BraidBead", (0.96, 0.80, 0.30), 0.3, 0.5)
        for sx in (-1, 1):
            for k in range(4):
                b = link(K["bpy"].data.objects.new(f"{n}_Bead_{sx}_{k}", sphere(f"{n}_Bead_{sx}_{k}", 0.115, 14)), coll)
                b.location = (sx * (R + 0.04 + 0.02 * k), 0.34 + 0.02 * k, cz - 0.10 - 0.20 * k)
                b.data.materials.append(bead if k % 2 else mat)
                bind(b, rig, "head")
            strand(cu, [
                (sx * (R - 0.04), 0.24, cz + 0.36),
                (sx * (R + 0.08), 0.34, cz + 0.02),
                (sx * (R + 0.12), 0.36, cz - 0.42),
                (sx * (R + 0.10), 0.34, cz - 0.88),
            ], 1.7, 0.22)
        return emit(cu)

    if style == "wavy_long":
        cu = make_curve()
        # forehead sweep kept above the brow
        for sx in (-1, 1):
            for k, x in enumerate((0.10, 0.30, 0.50)):
                strand(cu, [
                    (sx * 0.05, -0.16, top + 0.03),
                    (sx * x, -0.58, floor + 0.30),
                    (sx * (x + 0.10), -0.68, floor + 0.16),
                ], 1.5, 0.18)
        # long wavy curtain down the back with an S curve
        for i, x in enumerate((-0.56, -0.34, -0.12, 0.12, 0.34, 0.56)):
            strand(cu, [
                (x, R - 0.14, top - 0.06),
                (x * 1.05, R + 0.20, cz + 0.18),
                (x * 0.92, R + 0.30, cz - 0.30),
                (x * 1.10, R + 0.18, cz - 0.80),
                (x * 0.98 + j(0.04), 0.66, cz - 1.24 + j(0.05)),
            ], 2.3, 0.55)
        # shoulder locks
        for sx in (-1, 1):
            for k, y in enumerate((-0.20, 0.14)):
                strand(cu, [
                    (sx * (R - 0.05), y, cz + 0.42),
                    (sx * (R + 0.12), y - 0.06, cz - 0.10),
                    (sx * 0.76, y - 0.30, cz - 0.62),
                    (sx * 0.72, y - 0.34, cz - 1.10 + j(0.06)),
                ], 2.0, 0.45)
        return emit(cu)

    return None
