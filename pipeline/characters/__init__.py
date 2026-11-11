"""
Phase 2 character system: persistent identities + reusable appearance assets.

Layout
------
``identities.py``   the identity registry (stable ids, appearance, voice, personality)
``hair.py``         ten new hair silhouettes layered on the six legacy styles
``clothing.py``     seven garment overlays with real second-order detail
``accessories.py``  sixteen head / face / body accessories with declared zones
``checks.py``       geometry verification (rig compat, clipping, intersections)

Import surface
--------------
This package is deliberately importable **without Blender**: ``identities``,
``hair``, ``clothing`` and ``accessories`` only need ``math``/``re``/``json`` at
module scope. Anything that touches ``bpy`` is imported lazily inside a function,
so ``python pipeline/test_characters.py`` can validate the registry and the
rig-kwargs mapping on a plain interpreter.
"""

from . import accessories, clothing, hair, identities  # noqa: F401

CHARACTER_IDENTITIES = identities.CHARACTER_IDENTITIES
SKIN_TONES = identities.SKIN_TONES
PERSONALITIES = identities.PERSONALITIES
HEAD_STYLES = identities.HEAD_STYLES
FACE_STYLES = identities.FACE_STYLES
IDENTITY_JSON = identities.IDENTITY_JSON

resolve = identities.resolve
get = identities.get
validate_all = identities.validate_all
validate_identity = identities.validate_identity
to_json_document = identities.to_json_document
write_json = identities.write_json

ACCESSORY_REGISTRY = accessories.ACCESSORY_REGISTRY
ACCESSORY_ZONES = accessories.ACCESSORY_ZONES
OUTFITS = clothing.OUTFITS
PRINTS = clothing.PRINTS
HAIR_ALL_STYLES = hair.ALL_STYLES
HAIR_LEGACY_STYLES = hair.LEGACY_STYLES
HAIR_VOLUME = hair.HAIR_VOLUME

#: keys an identity may hand to ``roblox_rig.build_character``
RIG_KWARGS = (
    "skin", "hair", "hair_style", "hair_seed", "fringe_dir",
    "top", "pants", "details", "accent", "sleeves", "bottom", "shoes",
    "emblem", "hat", "hat_color", "extras", "fabric", "face",
    "outfit", "print_kind", "print_color", "accessories", "body_scale", "head_style",
)


def identity_to_rig_kwargs(name):
    """
    Translate an identity into ``build_character`` keyword arguments.

    Legacy identities (``legacy_preset`` set) return ``None`` because they are
    built verbatim from ``roblox_rig.PRESETS``; that is what keeps the eight
    original characters byte-compatible.
    """
    ident = get(name)
    if ident.get("legacy_preset"):
        return None

    cloth = ident.get("clothing") or {}
    hair_spec = ident.get("hair") or {}
    props = ident.get("proportions") or {}

    kw = dict(
        skin=tuple(ident["skin"]),
        hair=tuple(hair_spec.get("color", (0.35, 0.20, 0.10))),
        hair_style=hair_spec.get("style", "short"),
        hair_seed=hair_spec.get("seed", 3),
        fringe_dir=hair_spec.get("fringe_dir", 1.0),
        top=tuple(cloth.get("top", (0.58, 0.76, 0.95))),
        pants=tuple(cloth.get("pants", (0.54, 0.71, 0.92))),
        details=tuple(cloth.get("details") or ()),
        accent=tuple(cloth.get("accent", (0.95, 0.95, 0.95))),
        sleeves=cloth.get("sleeves", "long"),
        bottom=cloth.get("bottom", "pants"),
        shoes=tuple(cloth["shoes"]) if cloth.get("shoes") else None,
        hat=cloth.get("hat"),
        hat_color=tuple(cloth["hat_color"]) if cloth.get("hat_color") else None,
        extras=tuple(cloth.get("extras") or ()),
        fabric=bool(cloth.get("fabric", True)),
        face=ident.get("face_style", "smile"),
        outfit=cloth.get("outfit", "none"),
        print_kind=cloth.get("print", "none"),
        print_color=tuple(cloth["print_color"]) if cloth.get("print_color") else None,
        accessories=tuple(ident.get("accessories") or ()),
        body_scale=float(props.get("body_scale", 1.0)),
        head_style=ident.get("head_style", "round"),
    )
    return {k: v for k, v in kw.items() if k in RIG_KWARGS}


def appearance_signature(name):
    """
    Deterministic fingerprint of everything that affects the rendered look.

    Two builds of the same identity must produce the same signature; that is the
    basis of the clothing/identity consistency tests.
    """
    ident = get(name)
    if ident.get("legacy_preset"):
        return ("legacy", ident["legacy_preset"])
    kw = identity_to_rig_kwargs(name)
    parts = []
    for key in sorted(kw):
        val = kw[key]
        if isinstance(val, (list, tuple)):
            val = tuple(round(float(v), 6) if isinstance(v, (int, float)) else v for v in val)
        parts.append((key, val))
    return tuple(parts)


def summary():
    """Counts for the report / lineup captions."""
    legacy = [k for k, v in CHARACTER_IDENTITIES.items() if v.get("legacy_preset")]
    new = [k for k, v in CHARACTER_IDENTITIES.items() if not v.get("legacy_preset")]
    return {
        "identities": len(CHARACTER_IDENTITIES),
        "legacy_identities": len(legacy),
        "new_identities": len(new),
        "legacy_hair_styles": len(hair.LEGACY_STYLES),
        "new_hair_styles": len(hair.HAIR_VOLUME),
        "hair_styles": len(hair.ALL_STYLES),
        "outfits": len(clothing.OUTFITS),
        "prints": len(clothing.PRINTS),
        "accessories": len(accessories.ACCESSORY_REGISTRY),
        "accessory_zones": len(accessories.ACCESSORY_ZONES),
        "head_styles": len(HEAD_STYLES),
        "skin_tones": len(SKIN_TONES),
        "personalities": len(PERSONALITIES),
        "faces": len(FACE_STYLES),
        "legacy_ids": legacy,
        "new_ids": new,
    }
