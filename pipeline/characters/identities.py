"""
Character identity profiles (Phase 2).

An *identity* is the persistent description of how a character looks and sounds.
It is deliberately separate from:

  * animation  -> ``pipeline/roblox_motions.py`` (poses, actions) and the
                  per-shot ``changes`` in ``shots.json``
  * placement  -> ``mark`` / ``dx`` / ``dy`` / ``facing`` on a cast entry

So one identity can be referenced by any number of shots, sets and episodes, and
it always resolves to exactly the same appearance.

Identity fields
---------------
``id``            stable slug, also the baked collection / blend name
``name``          display name
``legacy_preset`` optional: build verbatim from ``roblox_rig.PRESETS`` (keeps the
                  eight original presets byte-identical)
``proportions``   ``body_scale`` / ``head_scale`` / ``arm_scale`` / ``leg_scale``
``skin``          sRGB tone, normally a key of ``SKIN_TONES``
``head_style``    ``round`` (R6 default) or ``square``
``face_style``    default expression id from the 16-cell atlas
``hair``          ``{style, color, seed, fringe_dir}``
``clothing``      colours + ``outfit`` + ``print`` + legacy ``details``
``accessories``   list of ids from ``characters.accessories.ACCESSORY_REGISTRY``
``voice``         ``eleven_voice`` id + delivery settings
``personality``   default pose / face / idle action / walk multiplier

Nothing here mutates the R6 skeleton: ``proportions`` only scales the finished
rig object, exactly like the existing per-shot ``scale`` key.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
IDENTITY_JSON = ROOT / "public" / "roblox" / "character_identities.json"

SKIN_TONES = {
    "light": (1.0, 0.82, 0.66),
    "tan": (0.97, 0.67, 0.40),
    "brown": (0.62, 0.40, 0.25),
    "deep": (0.42, 0.26, 0.17),
    "noob": (0.96, 0.80, 0.10),
}

HEAD_STYLES = ["round", "square"]

PERSONALITIES = {
    "curious":   dict(default_pose="relaxed", idle_action="look_around", walk_speed=1.00),
    "calm":      dict(default_pose="relaxed", idle_action="idle", walk_speed=0.90),
    "energetic": dict(default_pose="relaxed", idle_action="dance", walk_speed=1.15),
    "shy":       dict(default_pose="relaxed", idle_action="look_around", walk_speed=0.85),
    "regal":     dict(default_pose="hands_hips", idle_action="idle", walk_speed=0.95),
    "sleepy":    dict(default_pose="relaxed", idle_action="idle", walk_speed=0.80),
    "goofy":     dict(default_pose="relaxed", idle_action="dance", walk_speed=1.10),
    "brave":     dict(default_pose="hands_hips", idle_action="idle", walk_speed=1.05),
}

VOICE_PROFILES = {
    "kid_boy":    dict(eleven_voice="adam", stability=0.45, similarity_boost=0.80, style=0.45),
    "kid_girl":   dict(eleven_voice="adam", stability=0.50, similarity_boost=0.78, style=0.50),
    "adult_male": dict(eleven_voice="adam", stability=0.60, similarity_boost=0.82, style=0.30),
    "adult_female": dict(eleven_voice="adam", stability=0.58, similarity_boost=0.80, style=0.35),
    "goofy":      dict(eleven_voice="adam", stability=0.36, similarity_boost=0.76, style=0.62),
    "narrator":   dict(eleven_voice="adam", stability=0.70, similarity_boost=0.85, style=0.20),
}


def _legacy(name, **over):
    """Identity that reproduces an existing ``roblox_rig.PRESETS`` entry exactly."""
    base = dict(
        id=name.lower(), name=name, legacy_preset=name, proportions={},
        skin=SKIN_TONES["tan"], head_style="round", face_style="smile",
        hair={}, clothing={}, accessories=[], voice={}, personality={},
    )
    base.update(over)
    return base


CHARACTER_IDENTITIES = {
    # ---------------------------------------------------------------- legacy 8
    # These resolve through `legacy_preset`, so their appearance is identical to
    # the shipped public/roblox/characters/*.blend files.
    "theo": _legacy("Theo", face_style="smile",
                    voice=dict(VOICE_PROFILES["kid_boy"], eleven_voice="adam"),
                    personality=dict(PERSONALITIES["curious"], id="curious")),
    "max": _legacy("Max", face_style="smile",
                   voice=dict(VOICE_PROFILES["kid_boy"], stability=0.42),
                   personality=dict(PERSONALITIES["goofy"], id="goofy")),
    "lily": _legacy("Lily", face_style="grin",
                    voice=dict(VOICE_PROFILES["kid_girl"]),
                    personality=dict(PERSONALITIES["energetic"], id="energetic")),
    "mom": _legacy("Mom", face_style="smile",
                   voice=dict(VOICE_PROFILES["adult_female"]),
                   personality=dict(PERSONALITIES["calm"], id="calm")),
    "dad": _legacy("Dad", face_style="smile",
                   voice=dict(VOICE_PROFILES["adult_male"]),
                   personality=dict(PERSONALITIES["calm"], id="calm")),
    "king": _legacy("King", face_style="confident",
                    voice=dict(VOICE_PROFILES["adult_male"], stability=0.72, style=0.15),
                    personality=dict(PERSONALITIES["regal"], id="regal")),
    "officer": _legacy("Officer", face_style="sleep",
                       voice=dict(VOICE_PROFILES["adult_male"], stability=0.68),
                       personality=dict(PERSONALITIES["sleepy"], id="sleepy")),
    "noob": _legacy("Noob", face_style="smile",
                    voice=dict(VOICE_PROFILES["goofy"]),
                    personality=dict(PERSONALITIES["goofy"], id="goofy")),

    # ------------------------------------------------------- new identities
    "aiko": dict(
        id="aiko", name="Aiko", legacy_preset=None,
        proportions=dict(body_scale=1.0, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["light"], head_style="round", face_style="neutral",
        hair=dict(style="spiky", color=(0.07, 0.06, 0.09), seed=5, fringe_dir=-1.0),
        clothing=dict(top=(0.13, 0.24, 0.52), pants=(0.24, 0.26, 0.36), accent=(0.96, 0.96, 0.98),
                      shoes=(0.10, 0.10, 0.12), sleeves="long", bottom="skirt",
                      outfit="school_uniform", print="none", fabric=True, details=()),
        accessories=["satchel"],
        voice=dict(VOICE_PROFILES["kid_girl"], stability=0.52),
        personality=dict(PERSONALITIES["shy"], id="shy"),
    ),
    "dev": dict(
        id="dev", name="Dev", legacy_preset=None,
        proportions=dict(body_scale=1.02, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["brown"], head_style="round", face_style="smirk",
        hair=dict(style="curly", color=(0.08, 0.06, 0.05), seed=9, fringe_dir=1.0),
        clothing=dict(top=(0.26, 0.70, 0.36), pants=(0.36, 0.40, 0.48), accent=(0.97, 0.97, 0.99),
                      shoes=(0.92, 0.92, 0.94), sleeves="long", bottom="pants",
                      outfit="hoodie", print="none", fabric=True, details=("cuffs",)),
        accessories=["headphones"],
        voice=dict(VOICE_PROFILES["kid_boy"], stability=0.40, style=0.55),
        personality=dict(PERSONALITIES["goofy"], id="goofy"),
    ),
    "mira": dict(
        id="mira", name="Mira", legacy_preset=None,
        proportions=dict(body_scale=1.0, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["tan"], head_style="round", face_style="smile",
        hair=dict(style="bob", color=(0.72, 0.42, 0.18), seed=4, fringe_dir=1.0),
        clothing=dict(top=(0.86, 0.44, 0.68), pants=(0.72, 0.30, 0.54), accent=(1.0, 0.86, 0.40),
                      shoes=(0.99, 0.96, 0.92), sleeves="short", bottom="pants",
                      outfit="dress", print="heart", print_color=(1.0, 0.86, 0.40), fabric=True, details=()),
        accessories=["flower_crown"],
        voice=dict(VOICE_PROFILES["kid_girl"], stability=0.55),
        personality=dict(PERSONALITIES["energetic"], id="energetic"),
    ),
    "sable": dict(
        id="sable", name="Sable", legacy_preset=None,
        proportions=dict(body_scale=1.06, head_scale=1.0, arm_scale=1.0, leg_scale=1.02),
        skin=SKIN_TONES["light"], head_style="round", face_style="confident",
        hair=dict(style="side_swept", color=(0.10, 0.08, 0.07), seed=2, fringe_dir=-1.0),
        clothing=dict(top=(0.10, 0.11, 0.15), pants=(0.10, 0.11, 0.15), accent=(0.62, 0.10, 0.14),
                      shoes=(0.05, 0.05, 0.06), sleeves="long", bottom="pants",
                      outfit="suit", print="none", fabric=True, details=("collar",)),
        accessories=["sunglasses"],
        voice=dict(VOICE_PROFILES["adult_male"], stability=0.74, style=0.12),
        personality=dict(PERSONALITIES["regal"], id="regal"),
    ),
    "pip": dict(
        id="pip", name="Pip", legacy_preset=None,
        proportions=dict(body_scale=0.94, head_scale=1.04, arm_scale=1.0, leg_scale=0.96),
        skin=SKIN_TONES["tan"], head_style="round", face_style="grin",
        hair=dict(style="buzz", color=(0.52, 0.30, 0.12), seed=6, fringe_dir=1.0),
        clothing=dict(top=(0.99, 0.78, 0.22), pants=(0.28, 0.44, 0.72), accent=(0.16, 0.60, 0.94),
                      shoes=(0.94, 0.94, 0.96), sleeves="short", bottom="shorts",
                      outfit="tshirt", print="bolt", print_color=(0.14, 0.52, 0.92), fabric=True, details=()),
        accessories=["backpack"],
        voice=dict(VOICE_PROFILES["kid_boy"], stability=0.38, style=0.60),
        personality=dict(PERSONALITIES["curious"], id="curious"),
    ),
    "rowan": dict(
        id="rowan", name="Rowan", legacy_preset=None,
        proportions=dict(body_scale=1.0, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["deep"], head_style="round", face_style="smile",
        hair=dict(style="ponytail", color=(0.16, 0.09, 0.05), seed=8, fringe_dir=1.0),
        clothing=dict(top=(0.36, 0.58, 0.30), pants=(0.30, 0.32, 0.36), accent=(0.90, 0.72, 0.30),
                      shoes=(0.32, 0.22, 0.14), sleeves="long", bottom="pants",
                      outfit="jacket", print="none", fabric=True, details=()),
        accessories=["scarf"],
        voice=dict(VOICE_PROFILES["kid_girl"], stability=0.48),
        personality=dict(PERSONALITIES["brave"], id="brave"),
    ),
    "zephyr": dict(
        id="zephyr", name="Zephyr", legacy_preset=None,
        proportions=dict(body_scale=1.04, head_scale=1.0, arm_scale=1.02, leg_scale=1.0),
        skin=SKIN_TONES["light"], head_style="round", face_style="smirk",
        hair=dict(style="mohawk", color=(0.14, 0.66, 0.88), seed=11, fringe_dir=1.0),
        clothing=dict(top=(0.16, 0.22, 0.38), pants=(0.12, 0.14, 0.20), accent=(0.30, 0.86, 0.92),
                      shoes=(0.08, 0.08, 0.10), sleeves="long", bottom="pants",
                      outfit="themed", print="none", fabric=True, details=()),
        accessories=["wings"],
        voice=dict(VOICE_PROFILES["kid_boy"], stability=0.44, style=0.50),
        personality=dict(PERSONALITIES["brave"], id="brave"),
    ),
    "tessa": dict(
        id="tessa", name="Tessa", legacy_preset=None,
        proportions=dict(body_scale=1.0, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["brown"], head_style="round", face_style="nervous",
        hair=dict(style="braids", color=(0.20, 0.10, 0.06), seed=7, fringe_dir=1.0),
        clothing=dict(top=(0.20, 0.32, 0.58), pants=(0.22, 0.24, 0.34), accent=(0.94, 0.94, 0.96),
                      shoes=(0.14, 0.14, 0.18), sleeves="long", bottom="pants",
                      outfit="school_uniform", print="none", fabric=True, details=()),
        accessories=["monocle"],
        voice=dict(VOICE_PROFILES["kid_girl"], stability=0.58),
        personality=dict(PERSONALITIES["shy"], id="shy"),
    ),
    "nori": dict(
        id="nori", name="Nori", legacy_preset=None,
        proportions=dict(body_scale=0.98, head_scale=1.02, arm_scale=1.0, leg_scale=0.98),
        skin=SKIN_TONES["tan"], head_style="round", face_style="laugh",
        hair=dict(style="layered", color=(0.34, 0.20, 0.12), seed=13, fringe_dir=1.0),
        clothing=dict(top=(0.92, 0.52, 0.22), pants=(0.24, 0.28, 0.40), accent=(0.98, 0.96, 0.90),
                      shoes=(0.90, 0.90, 0.92), sleeves="long", bottom="pants",
                      outfit="hoodie", print="none", fabric=True, details=("kangaroo",)),
        accessories=["beanie"],
        voice=dict(VOICE_PROFILES["kid_boy"], stability=0.46),
        personality=dict(PERSONALITIES["goofy"], id="goofy"),
    ),
    "wren": dict(
        id="wren", name="Wren", legacy_preset=None,
        proportions=dict(body_scale=1.0, head_scale=1.0, arm_scale=1.0, leg_scale=1.0),
        skin=SKIN_TONES["light"], head_style="round", face_style="smile",
        hair=dict(style="wavy_long", color=(0.86, 0.62, 0.30), seed=15, fringe_dir=-1.0),
        clothing=dict(top=(0.94, 0.94, 0.98), pants=(0.36, 0.52, 0.78), accent=(0.28, 0.82, 0.70),
                      shoes=(0.86, 0.80, 0.68), sleeves="short", bottom="pants",
                      outfit="tshirt", print="star", print_color=(0.28, 0.82, 0.70), fabric=True, details=()),
        accessories=["amulet"],
        voice=dict(VOICE_PROFILES["kid_girl"], stability=0.50),
        personality=dict(PERSONALITIES["curious"], id="curious"),
    ),
}

# identifier aliases so episodes can use either the slug or the display name
ALIASES = {k: k for k in CHARACTER_IDENTITIES}
for _k, _v in CHARACTER_IDENTITIES.items():
    ALIASES.setdefault(_v["name"].lower(), _k)

REQUIRED_IDENTITY_KEYS = {
    "id", "name", "legacy_preset", "proportions", "skin", "head_style",
    "face_style", "hair", "clothing", "accessories", "voice", "personality",
}

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def resolve(name):
    """Resolve an identity slug, display name or alias to a canonical id."""
    if name is None:
        return None
    key = str(name).strip()
    if key in CHARACTER_IDENTITIES:
        return key
    low = key.lower()
    if low in ALIASES:
        return ALIASES[low]
    return None


def get(name):
    cid = resolve(name)
    if cid is None:
        raise KeyError(f"Unknown character identity {name!r}; available: {sorted(CHARACTER_IDENTITIES)}")
    return CHARACTER_IDENTITIES[cid]


def validate_identity(cid, ident):
    """Structural validation of one identity. Returns a list of error strings."""
    E = []
    if not _ID_RE.match(str(cid)):
        E.append(f"{cid!r}: id must be a lowercase slug [a-z0-9_]")
    if ident.get("id") != cid:
        E.append(f"{cid!r}: id field {ident.get('id')!r} does not match its key")
    missing = REQUIRED_IDENTITY_KEYS - set(ident)
    if missing:
        E.append(f"{cid!r}: missing keys {sorted(missing)}")
        return E
    if not ident.get("name"):
        E.append(f"{cid!r}: empty name")
    if ident["head_style"] not in HEAD_STYLES:
        E.append(f"{cid!r}: head_style {ident['head_style']!r} not in {HEAD_STYLES}")
    skin = ident["skin"]
    if not (isinstance(skin, (list, tuple)) and len(skin) == 3 and all(0.0 <= c <= 1.0 for c in skin)):
        E.append(f"{cid!r}: skin must be an sRGB triple")
    props = ident["proportions"]
    for k, lo, hi in (("body_scale", 0.85, 1.25), ("head_scale", 0.90, 1.20),
                      ("arm_scale", 0.90, 1.15), ("leg_scale", 0.90, 1.20)):
        v = props.get(k, 1.0)
        if not (lo <= float(v) <= hi):
            E.append(f"{cid!r}: proportions.{k}={v} outside [{lo}, {hi}]")

    from . import hair as hair_mod
    hair = ident["hair"]
    if ident.get("legacy_preset"):
        if hair:
            E.append(f"{cid!r}: a legacy_preset identity must not override hair")
    else:
        if hair.get("style") not in hair_mod.ALL_STYLES:
            E.append(f"{cid!r}: hair.style {hair.get('style')!r} not in {hair_mod.ALL_STYLES}")
        col = hair.get("color")
        if not (isinstance(col, (list, tuple)) and len(col) == 3):
            E.append(f"{cid!r}: hair.color must be an sRGB triple")

    from . import clothing as clothing_mod
    from . import accessories as accessory_mod
    cloth = ident["clothing"]
    if not ident.get("legacy_preset"):
        if cloth.get("outfit", "none") not in clothing_mod.OUTFITS:
            E.append(f"{cid!r}: clothing.outfit {cloth.get('outfit')!r} not in {clothing_mod.OUTFITS}")
        if cloth.get("print", "none") not in clothing_mod.PRINTS:
            E.append(f"{cid!r}: clothing.print {cloth.get('print')!r} not in {clothing_mod.PRINTS}")
        if cloth.get("sleeves", "long") not in ("long", "short", "none"):
            E.append(f"{cid!r}: clothing.sleeves {cloth.get('sleeves')!r} invalid")
        if cloth.get("bottom", "pants") not in ("pants", "shorts", "skirt"):
            E.append(f"{cid!r}: clothing.bottom {cloth.get('bottom')!r} invalid")
    for acc in ident["accessories"]:
        if acc not in accessory_mod.ACCESSORY_REGISTRY:
            E.append(f"{cid!r}: unknown accessory {acc!r}")

    if ident["face_style"] not in FACE_STYLES:
        E.append(f"{cid!r}: face_style {ident['face_style']!r} not in the 16-cell atlas")

    voice = ident["voice"]
    if "eleven_voice" not in voice:
        E.append(f"{cid!r}: voice.eleven_voice missing")
    personality = ident["personality"]
    if personality.get("id") not in PERSONALITIES:
        E.append(f"{cid!r}: personality.id {personality.get('id')!r} not in {sorted(PERSONALITIES)}")
    return E


def validate_all():
    errs = []
    for cid, ident in CHARACTER_IDENTITIES.items():
        errs.extend(validate_identity(cid, ident))
    return errs


# The 16 atlas expression ids are owned by roblox_rig; duplicated here only as a
# constant so identity files can be validated without importing bpy.
FACE_STYLES = [
    "smile", "grin", "worried", "shocked",
    "laugh", "sleep", "angry", "sad",
    "neutral", "blink", "talk", "smirk",
    "surprised", "confident", "cry", "nervous",
]


def to_json_document():
    """Serialise the identity registry for public/roblox/character_identities.json."""
    out = {}
    for cid, ident in sorted(CHARACTER_IDENTITIES.items()):
        out[cid] = {
            "id": ident["id"],
            "name": ident["name"],
            "legacy_preset": ident.get("legacy_preset"),
            "proportions": dict(ident.get("proportions") or {}),
            "skin": list(ident["skin"]),
            "head_style": ident["head_style"],
            "face_style": ident["face_style"],
            "hair": dict(ident.get("hair") or {}),
            "clothing": dict(ident.get("clothing") or {}),
            "accessories": list(ident.get("accessories") or []),
            "voice": dict(ident.get("voice") or {}),
            "personality": dict(ident.get("personality") or {}),
            "blender": {
                "collection": ident["name"],
                "blend_file": f"public/roblox/characters/{ident['name']}.blend",
            },
        }
    return {
        "schema_version": "2.0",
        "total_identities": len(out),
        "skin_tones": {k: list(v) for k, v in SKIN_TONES.items()},
        "personalities": PERSONALITIES,
        "identities": out,
    }


def write_json(path=None):
    path = Path(path) if path else IDENTITY_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_json_document(), indent=2) + "\n", encoding="utf-8")
    return path
