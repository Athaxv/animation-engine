"""
Geometry verification for the Phase 2 character system (runs inside Blender).

These are the measurements the Phase 2 test suite asserts on. They are also used
by ``render_character_lineup.py`` so the previews are produced from the same
numbers the tests check.

Checks
------
``rig_report``          R6 skeleton compatibility (bone set, part inventory, head dims)
``head_occlusion``      face readability: geometry in front of the head inside the
                        eye / mouth band
``face_wear``           face-zone accessories really sit in front of the face
``body_crossing``       body accessories that pass through the torso to the far side
``mesh_signature``      deterministic bbox fingerprint (appearance consistency)

Coordinate reminder: the head is a cylinder of radius ``HEAD_R`` centred at
``HEAD_CZ``; the face decal is on the -Y side. A point occludes the face only if
it is in front of that cylinder, i.e. ``y < -sqrt(R^2 - x^2)``.
"""
import math

HEAD_CZ = 4.62
HEAD_R = 0.64
HEAD_H = 1.24

#: painted extents of the eye decal, converted to head space.
#: atlas cell -> head space is ``z = HEAD_CZ + (v - 0.5) * FACE_SPAN`` with
#: FACE_SPAN = 1.55; ``_oval_eyes`` draws at v = 0.60 +- 0.075 and u = 0.385 +- 0.042,
#: so the painted eye really spans z 4.659..4.891 and |x| 0.113..0.243.
EYE_BAND = dict(x=0.30, z0=4.63, z1=4.91)
MOUTH_BAND = dict(x=0.25, z0=4.32, z1=4.58)

TORSO = dict(x=1.0, y=0.5, z0=2.0, z1=4.0)

R6_BONES = {
    "root", "hips", "spine", "neck", "head",
    "upper_arm.L", "upper_arm.R", "upper_leg.L", "upper_leg.R",
}


# ---------------------------------------------------------------- geometry io
def evaluated_points(objects):
    """World-space vertices of every mesh/curve object in ``objects``."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in objects:
        if ob.type not in ("MESH", "CURVE"):
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            pts.append(mw @ v.co)
        ev.to_mesh_clear()
    return pts


def collection_points(rig, name_keys=None):
    import bpy
    coll = bpy.data.collections.get(rig.name)
    if coll is None:
        return []
    objs = list(coll.all_objects)
    if name_keys:
        objs = [o for o in objs if any(k in o.name for k in name_keys)]
    # the rig is placed in the world; measure in rig-local space so placement
    # offsets in a scene never change a clearance result
    inv = rig.matrix_world.inverted()
    return [inv @ p for p in evaluated_points(objs)]


def head_points(rig):
    return collection_points(rig, ("_Head",))


def hair_points(rig):
    keys = ("Hair", "Tie", "Spike", "Curl", "Crest", "Bead", "Flower", "Beanie",
            "TopHat", "Wiz", "Headband", "Hp", "Crown", "CapCrown", "CapDome", "CapBrim")
    return collection_points(rig, keys)


# ---------------------------------------------------------------- measurements
def _band_hits(pts, band, surface_eps=0.02):
    hits = []
    for p in pts:
        if abs(p.x) > band["x"] or not (band["z0"] < p.z < band["z1"]):
            continue
        surface = -math.sqrt(max(HEAD_R ** 2 - p.x ** 2, 0.0))
        if p.y < surface - surface_eps:
            hits.append((p.x, p.y, p.z))
    return hits


def head_occlusion(pts):
    """Count geometry in front of the head inside the eye and mouth bands."""
    eye = _band_hits(pts, EYE_BAND)
    mouth = _band_hits(pts, MOUTH_BAND)
    return {
        "eye_hits": len(eye),
        "mouth_hits": len(mouth),
        "eye_samples": eye[:6],
        "mouth_samples": mouth[:6],
        "ok": not eye and not mouth,
    }


def face_wear(pts):
    """Vertices that are genuinely in front of the face (visible), not buried."""
    front = 0
    for p in pts:
        if not (4.10 < p.z < 5.20):
            continue
        surface = -math.sqrt(max(HEAD_R ** 2 - p.x ** 2, 0.0))
        if p.y < surface:
            front += 1
    return {"front_vertices": front, "total": len(pts), "ok": front > 0}


def body_interior(pts):
    """
    Vertices buried inside the torso volume.

    Attachments legitimately touch the body surface (bag straps, a hood collar,
    a cape at the shoulders). What is never acceptable is geometry that sits
    *inside* the torso box, which shows as the accessory clipping through the
    chest or back when the character turns.
    """
    x, y = TORSO["x"] - 0.15, TORSO["y"] - 0.10
    hits = [p for p in pts
            if abs(p.x) < x and abs(p.y) < y and TORSO["z0"] + 0.15 < p.z < TORSO["z1"] - 0.15]
    return {"interior_hits": len(hits), "ok": not hits,
            "interior_samples": [(round(p.x, 3), round(p.y, 3), round(p.z, 3)) for p in hits[:6]]}


def mesh_signature(rig, ndigits=4):
    """Order-independent fingerprint of every object's world bbox."""
    import bpy
    coll = bpy.data.collections.get(rig.name)
    rows = []
    objs = sorted(coll.all_objects, key=lambda o: o.name)
    for ob in objs:
        bb = [tuple(round(c, ndigits) for c in corner) for corner in ob.bound_box]
        rows.append((ob.name, ob.type, tuple(sorted(bb))))
    return tuple(rows)


def rig_report(rig):
    """R6 compatibility snapshot."""
    import bpy
    coll = bpy.data.collections.get(rig.name)
    if coll is None:
        return {"error": f"no collection {rig.name!r}"}
    meshes = [o for o in coll.all_objects if o.type == "MESH"]
    bones = {b.name for b in rig.data.bones}
    head = coll.all_objects.get(f"{rig.name}_Head")
    torso = coll.all_objects.get(f"{rig.name}_Torso")
    props = list(rig.keys())
    decal = False
    for slot in (head.material_slots if head else []):
        if slot.material and "FaceIdx" in slot.material.node_tree.nodes:
            decal = True
    return {
        "bones": sorted(bones),
        "missing_bones": sorted(R6_BONES - bones),
        "mesh_objects": len(meshes),
        "head": head is not None,
        "head_dims": tuple(round(d, 3) for d in head.dimensions) if head else None,
        "torso_dims": tuple(round(d, 3) for d in torso.dimensions) if torso else None,
        "face_prop": rig.get("face", None),
        "decal_material": decal,
        "props": sorted(props),
        "is_roblox_rig": bool(rig.get("is_roblox_rig", False)),
    }


# ---------------------------------------------------------------- aggregates
def measure(rig):
    """Full Phase 2 measurement bundle for one built character."""
    hair = hair_points(rig)
    occ = head_occlusion(hair)
    rep = rig_report(rig)
    rep.update({
        "hair_vertices": len(hair),
        "hair_eye_hits": occ["eye_hits"],
        "hair_mouth_hits": occ["mouth_hits"],
        "hair_ok": occ["ok"],
    })
    return rep


def accessory_measure(rig, acc_ids):
    """Per-accessory zone-aware verification."""
    from . import accessories  # noqa: F401  (local import keeps the module bpy-free)
    out = {}
    for acc in acc_ids:
        zone = accessories.ACCESSORY_REGISTRY[acc][0]
        pts = collection_points(rig, _accessory_keys(acc))
        entry = {"zone": zone, "vertices": len(pts), "ok": True}
        if zone == "face":
            face = face_wear(pts)
            entry.update(face)
            if not face["ok"]:
                entry["ok"] = False
        elif zone == "head_top":
            occ = head_occlusion(pts)
            entry.update(eye_hits=occ["eye_hits"], mouth_hits=occ["mouth_hits"])
            if not occ["ok"]:
                entry["ok"] = False
        else:
            inside = body_interior(pts)
            entry.update(inside)
            if not inside["ok"]:
                entry["ok"] = False
        if not pts:
            entry["ok"] = False
            entry["error"] = "no geometry"
        out[acc] = entry
    return out


_ACC_PREFIX = {
    "beanie": ("Beanie",),
    "top_hat": ("TopHat",),
    "wizard_hat": ("Wiz",),
    "flower_crown": ("Flower",),
    "headband": ("Headband",),
    "headphones": ("Hp",),
    "sunglasses": ("Sun",),
    "mask": ("Mask",),
    "monocle": ("Mono",),
    "eyepatch": ("Patch",),
    "scarf": ("Scarf",),
    "backpack": ("Pack",),
    "satchel": ("Satchel",),
    "cape": ("Cape",),
    "wings": ("Wing",),
    "amulet": ("Amulet",),
}


def _accessory_keys(acc):
    return _ACC_PREFIX.get(acc, (acc,))
