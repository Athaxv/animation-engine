"""
Reusable Roblox R6 clothing / outfit overlays (Phase 2).

An "outfit" is *geometry layered on the existing R6 body*, never a replacement
for it: the blocky torso/arm/leg boxes from ``pipeline/roblox_rig.py`` stay
exactly where they are, so silhouette, bone binding and locomotion are unchanged.

Outfits add readable second-order detail that a flat solid colour cannot:
zippers, lapels, ribbed hems, pockets, pleats, crests, prints and trim.

All overlays are pushed slightly outside the body surface so they never
z-fight, and none of them touch the head.
"""
import math

OUTFITS = [
    "none",
    "hoodie",
    "jacket",
    "tshirt",
    "school_uniform",
    "suit",
    "dress",
    "themed",
]

OUTFIT_NOTES = {
    "none": "plain top/pants from the base body",
    "hoodie": "hood volume, zip strip, drawstrings, kangaroo pocket, ribbed hem",
    "jacket": "open V front, lapels, zip teeth, chest pocket, hem band",
    "tshirt": "short sleeves, crew rib, chest print",
    "school_uniform": "blazer panels, buttons, crest, tie (pleats with bottom=skirt)",
    "suit": "lapels, tie, pocket square, cuff buttons",
    "dress": "fitted bodice, waist sash, flared skirt, hem trim",
    "themed": "fantasy pauldrons, chest sigil, belt and bracers",
}

PRINTS = ["none", "star", "heart", "circle", "stripe", "bolt"]

# overlay thickness, keeps garments outside the body box
_T = 0.035


def _print_points(kind, r=0.28):
    """2D silhouette (x, z) for a chest print."""
    if kind == "star":
        pts = []
        for k in range(10):
            rad = r if k % 2 == 0 else r * 0.45
            a = math.pi * k / 5 - math.pi / 2
            pts.append((rad * math.cos(a), rad * math.sin(a)))
        return pts
    if kind == "heart":
        pts = []
        for k in range(36):
            t = 2 * math.pi * k / 36
            pts.append((0.016 * 16 * math.sin(t) ** 3,
                        0.016 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
        return [(x * (r / 0.30), z * (r / 0.30)) for x, z in pts]
    if kind == "circle":
        return [(r * math.cos(2 * math.pi * k / 28), r * math.sin(2 * math.pi * k / 28)) for k in range(28)]
    if kind == "stripe":
        return [(-r, r * 0.18), (r, r * 0.18), (r, -r * 0.18), (-r, -r * 0.18)]
    if kind == "bolt":
        return [(0.02, r), (-0.16, 0.02), (-0.03, 0.02), (-0.11, -r), (0.17, 0.06), (0.03, 0.06)]
    return []


def build_outfit(K, rig, coll, M, outfit="none", print_kind="none", bottom="pants",
                 accent=(0.95, 0.95, 0.95), print_color=None, crest=None):
    """
    Add garment geometry on top of an already-built R6 body.

    ``M`` is the material dict returned by ``roblox_rig.build_body``
    (``skin``, ``top``, ``pants``, ``trim``, ``accent``). Returns the objects created.
    """
    strand = K.get("_strand")
    link = K["_link"]
    bind = K["bind"]
    new_mat = K["new_mat"]
    add_bump = K["add_bump"]
    rbox = K["rbox"]
    sphere = K["_sphere_mesh"]
    cylinder = K["_cyl_mesh"]
    flat_shape = K["_flat_shape"]

    n = rig.name
    OUT = []
    FY = -0.5            # torso front plane (torso is 2.0 x 1.0 x 2.0 at z = 3.0)
    TOP_Z = 4.0          # torso top
    BOT_Z = 2.0          # torso bottom / hips line

    fab = lambda m: add_bump(m, 90, 0.18, 6, tint=0.06)

    top_rgb = tuple(M["top"].diffuse_color)[:3]
    trim_rgb = tuple(M["trim"].diffuse_color)[:3]
    acc_rgb = tuple(M["accent"].diffuse_color)[:3]
    pants_rgb = tuple(M["pants"].diffuse_color)[:3]

    def mat_for(key, rgb, rough=0.8, spec=0.25):
        m = bpy_mat(f"{n}_Out{key}", rgb, rough, spec, fab)
        return m

    def bpy_mat(name, rgb, rough, spec, bump_fn=None):
        m = new_mat(name, rgb, rough, spec)
        return bump_fn(m) if bump_fn else m

    def part(name, size, center, mat, bone="spine", bevel=0.04, rot=None):
        ob = rbox(f"{n}_{name}", coll, size, center, mat, bevel)
        if rot:
            ob.rotation_euler = rot
        OUT.append((ob, bone))
        return ob

    def shape(name, pts, center, mat, bone="spine", th=0.03, rot=(0, 0, 0), scale=(1, 1, 1)):
        me, _ = flat_shape(f"{n}_{name}", pts)
        ob = link(K["bpy"].data.objects.new(f"{n}_{name}", me), coll)
        ob.location = center
        ob.rotation_euler = rot
        ob.scale = scale
        me.materials.append(mat)
        so = ob.modifiers.new("Solid", "SOLIDIFY")
        so.thickness = th
        OUT.append((ob, bone))
        return ob

    def cylinder_part(name, r1, r2, depth, center, mat, bone="spine", rot=None, scale=None, segs=32):
        ob = link(K["bpy"].data.objects.new(f"{n}_{name}", cylinder(f"{n}_{name}", r1, r2, depth, segs)), coll)
        ob.location = center
        if rot:
            ob.rotation_euler = rot
        if scale:
            ob.scale = scale
        ob.data.materials.append(mat)
        OUT.append((ob, bone))
        return ob

    # ------------------------------------------------------------------ outfits
    if outfit == "hoodie":
        hood = mat_for("Hood", trim_rgb, 0.9, 0.15)
        part("HoodBack", (1.55, 0.42, 0.46), (0, 0.36, TOP_Z - 0.06), hood, bevel=0.20)
        part("HoodRim", (1.62, 0.30, 0.14), (0, 0.20, TOP_Z + 0.12), hood, bevel=0.06)
        # zip strip down the centre front
        part("Zip", (0.10, 0.05, 1.92), (0, FY - _T, 3.0), M["trim"], bevel=0.01)
        for k in range(7):
            part(f"ZipTooth{k}", (0.14, 0.04, 0.07), (0, FY - _T - 0.03, 2.28 + 0.24 * k), M["accent"], bevel=0.01)
        for sx in (-1, 1):
            part(f"Draw_{sx}", (0.05, 0.05, 0.46), (sx * 0.20, FY - _T - 0.03, 3.62), M["accent"], bevel=0.01)
            sphere_dot = link(K["bpy"].data.objects.new(f"{n}_DrawTip_{sx}", sphere(f"{n}_DrawTip_{sx}", 0.055, 12)), coll)
            sphere_dot.location = (sx * 0.20, FY - _T - 0.03, 3.39)
            sphere_dot.data.materials.append(M["accent"])
            OUT.append((sphere_dot, "spine"))
        part("Pocket", (1.28, 0.06, 0.52), (0, FY - _T, 2.46), M["trim"], bevel=0.05)
        part("Hem", (2.04, 1.04, 0.18), (0, 0, BOT_Z + 0.10), M["trim"], bevel=0.04)

    elif outfit == "jacket":
        lapel = mat_for("Lapel", tuple(c * 1.12 for c in top_rgb), 0.7, 0.3)
        for sx in (-1, 1):
            shape(f"Lapel_{sx}", [(sx * 0.06, 0.0), (sx * 0.62, 0.0), (sx * 0.50, -1.15), (sx * 0.10, -0.85)],
                  (sx * 0.30, FY - _T - 0.01, TOP_Z - 0.30), lapel, th=0.05)
            part(f"HemBand_{sx}", (0.94, 1.05, 0.16), (sx * 0.5, 0, BOT_Z + 0.08), M["trim"], bevel=0.04)
        part("Placket", (0.16, 0.05, 1.80), (0, FY - _T - 0.02, 3.02), M["trim"], bevel=0.01)
        for k in range(6):
            part(f"ZipTeeth{k}", (0.10, 0.03, 0.06), (0, FY - _T - 0.05, 2.34 + 0.28 * k), M["accent"], bevel=0.01)
        part("ChestPocket", (0.42, 0.05, 0.30), (0.55, FY - _T - 0.02, 3.42), M["trim"], bevel=0.02)
        # stand-up collar (kept low so it does not read as shoulder fins)
        for sx in (-1, 1):
            shape(f"Collar_{sx}", [(0, 0), (sx * 0.30, 0.02), (sx * 0.26, 0.15)], (sx * 0.06, FY - _T, TOP_Z - 0.04),
                  lapel, th=0.04)

    elif outfit == "tshirt":
        for sx in (-1, 1):
            part(f"Rib_{sx}", (0.34, 0.06, 0.10), (sx * 0.24, FY - _T, TOP_Z - 0.08), M["trim"], bevel=0.02)
        part("HemBand", (2.02, 1.02, 0.10), (0, 0, BOT_Z + 0.06), M["trim"], bevel=0.02)
        if print_kind != "none":
            pc = new_mat(f"{n}_Print", print_color or accent, 0.7, 0.25)
            shape("Print", _print_points(print_kind), (0.0, FY - _T - 0.015, 3.12), pc, th=0.02)

    elif outfit == "school_uniform":
        blazer = mat_for("Blazer", tuple(c * 0.82 for c in top_rgb), 0.75, 0.25)
        for sx in (-1, 1):
            part(f"BlazerPanel_{sx}", (0.94, 1.05, 1.86), (sx * 0.53, 0, 3.02), blazer, bevel=0.05)
        for k in range(3):
            b = link(K["bpy"].data.objects.new(f"{n}_UniBtn{k}", cylinder(f"{n}_UniBtn{k}", 0.055, 0.055, 0.03, 16)), coll)
            b.location = (0.06, FY - 0.06, 3.44 - 0.34 * k)
            b.rotation_euler = (math.pi / 2, 0, 0)
            b.data.materials.append(M["accent"])
            OUT.append((b, "spine"))
        # crest on the breast pocket
        crest_pts = [(0.14 * (1 if k % 2 == 0 else 0.42) * math.sin(math.pi * k / 5),
                      0.14 * (1 if k % 2 == 0 else 0.42) * math.cos(math.pi * k / 5)) for k in range(10)]
        shape("Crest", crest_pts, (-0.52, FY - 0.06, 3.46), M["accent"], th=0.03)
        for sx in (-1, 1):
            shape(f"UniCollar_{sx}", [(0, 0), (sx * 0.40, 0.05), (sx * 0.34, 0.32)],
                  (sx * 0.05, FY - 0.06, TOP_Z - 0.03), M["accent"], th=0.04)
        part("TieKnot", (0.16, 0.06, 0.14), (0, FY - 0.08, 3.82), M["accent"], bevel=0.02)
        shape("TieBlade", [(-0.08, 0), (0.08, 0), (0.12, -0.80), (0, -0.94), (-0.12, -0.80)],
              (0, FY - 0.08, 3.76), M["accent"], th=0.035)
        if bottom == "skirt":
            skirt = mat_for("Pleats", tuple(M["pants"].diffuse_color)[:3], 0.85, 0.2)
            for k in range(9):
                a = -0.58 + k * 0.145
                part(f"Pleat{k}", (0.26, 1.06, 1.02), (math.sin(a) * 1.24, math.cos(a) * 0.02, 1.54), skirt,
                     bone="hips", bevel=0.02, rot=(0, 0, a))

    elif outfit == "suit":
        jacket = mat_for("Suit", top_rgb, 0.62, 0.35)
        shirt = new_mat(f"{n}_Shirt", (0.97, 0.97, 0.99), 0.7, 0.25)
        for sx in (-1, 1):
            shape(f"SuitLapel_{sx}", [(sx * 0.05, 0.0), (sx * 0.58, 0.02), (sx * 0.44, -1.02), (sx * 0.09, -0.74)],
                  (sx * 0.28, FY - 0.05, TOP_Z - 0.26), jacket, th=0.05)
            part(f"SuitSleeve_{sx}", (1.02, 1.02, 1.92), (sx * 1.5, 0, 3.02), jacket, bone=f"upper_arm.{'L' if sx > 0 else 'R'}",
                 bevel=0.06)
            for k in range(2):
                cb = link(K["bpy"].data.objects.new(f"{n}_CuffBtn_{sx}_{k}",
                                                     cylinder(f"{n}_CuffBtn_{sx}_{k}", 0.04, 0.04, 0.025, 12)), coll)
                cb.location = (sx * 1.5, FY + 0.02, 2.34 - 0.12 * k)
                cb.rotation_euler = (math.pi / 2, 0, 0)
                cb.data.materials.append(M["accent"])
                OUT.append((cb, f"upper_arm.{'L' if sx > 0 else 'R'}"))
        part("SuitShirt", (0.62, 0.05, 1.30), (0, FY - 0.055, 3.32), shirt, bevel=0.02)
        part("SuitKnot", (0.15, 0.06, 0.13), (0, FY - 0.08, 3.86), M["accent"], bevel=0.02)
        shape("SuitTie", [(-0.075, 0), (0.075, 0), (0.11, -0.76), (0, -0.90), (-0.11, -0.76)],
              (0, FY - 0.08, 3.80), M["accent"], th=0.035)
        shape("PocketSquare", [(-0.11, 0), (0.11, 0), (0.07, 0.16), (0, 0.09), (-0.07, 0.16)],
              (0.54, FY - 0.06, 3.44), M["accent"], th=0.03)
        part("SuitBelt", (2.03, 1.03, 0.14), (0, 0, 2.14), new_mat(f"{n}_SuitBelt", (0.06, 0.06, 0.07), 0.4, 0.4), bevel=0.03)

    elif outfit == "dress":
        bodice = mat_for("Bodice", top_rgb, 0.82, 0.22)
        part("Bodice", (2.02, 1.02, 1.10), (0, 0, 3.42), bodice, bevel=0.05)
        part("Sash", (2.06, 1.06, 0.26), (0, 0, 2.80), M["accent"], bevel=0.04)
        cylinder_part("SkirtA", 1.62, 1.24, 1.30, (0, 0, 2.02), M["pants"], bone="hips", scale=(1.0, 0.55, 1.0), segs=36)
        hem = new_mat(f"{n}_DressHem", tuple(c * 0.86 for c in pants_rgb), 0.8, 0.25)
        cylinder_part("HemTrim", 1.60, 1.54, 0.14, (0, 0, 1.44), hem, bone="hips", scale=(1.0, 0.55, 1.0), segs=36)
        for sx in (-1, 1):
            shape(f"Shoulder_{sx}", [(0, 0), (sx * 0.34, 0.04), (sx * 0.26, -0.24)], (sx * 0.62, FY - 0.05, TOP_Z - 0.12),
                  bodice, th=0.05)
        if print_kind != "none":
            pc = new_mat(f"{n}_DressPrint", print_color or accent, 0.75, 0.22)
            shape("DressPrint", _print_points(print_kind, 0.22), (0.0, FY - 0.055, 3.44), pc, th=0.02)

    elif outfit == "themed":
        armor = new_mat(f"{n}_Armor", tuple(c * 0.55 for c in top_rgb), 0.35, 0.55, coat=0.35)
        glow = new_mat(f"{n}_Sigil", accent, 0.25, 0.7)
        b = K["_bsdf"](glow)
        if "Emission Color" in b.inputs:
            b.inputs["Emission Color"].default_value = (*K["srgb"](accent), 1.0)
            b.inputs["Emission Strength"].default_value = 2.2
        for sx in (-1, 1):
            sphere_p = link(K["bpy"].data.objects.new(f"{n}_Pauldron_{sx}", sphere(f"{n}_Pauldron_{sx}", 0.44, 20)), coll)
            sphere_p.location = (sx * 1.22, 0, TOP_Z - 0.10)
            sphere_p.scale = (1.0, 0.92, 0.62)
            sphere_p.data.materials.append(armor)
            OUT.append((sphere_p, "spine"))
            part(f"Bracer_{sx}", (1.04, 1.04, 0.46), (sx * 1.5, 0, 2.58), armor,
                 bone=f"upper_arm.{'L' if sx > 0 else 'R'}", bevel=0.05)
        part("ChestPlate", (1.40, 0.10, 1.10), (0, FY - 0.06, 3.24), armor, bevel=0.08)
        shape("Sigil", _print_points("star", 0.24), (0.0, FY - 0.13, 3.26), glow, th=0.03)
        part("WarBelt", (2.04, 1.04, 0.18), (0, 0, 2.14), armor, bevel=0.03)
        part("Tasset", (0.80, 0.10, 0.44), (0.0, FY - 0.06, 1.92), armor, bone="hips", bevel=0.05)

    for ob, bone in OUT:
        bind(ob, rig, bone)
    return [ob for ob, _ in OUT]
