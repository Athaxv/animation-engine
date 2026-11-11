"""
The engine's vocabulary: every word a shots.json may use. Plain Python (no Blender).

    python pipeline/vocab.py            # print the cheat-sheet (what Claude reads before writing a script)

Poses, faces and cast presets are parsed from the rig sources, sets and marks come from
public/roblox/catalog.json (pipeline/catalog.py), so this never drifts from the assets.
"""
import ast, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
CATALOG = ROOT / "public" / "roblox" / "catalog.json"
SFX_DIR = ROOT / "public" / "audio" / "sfx"
MUSIC_DIR = ROOT / "public" / "audio" / "music"
FORMATS_DIR = ROOT / "formats"


def _assign(path, var):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == var for t in node.targets):
            return node.value
    raise KeyError(f"{var} not in {path}")


def _keys(path, var):
    return [k.value for k in _assign(path, var).keys if isinstance(k, ast.Constant)]


POSES = _keys(PIPE / "roblox_motions.py", "POSES")
FACES = [e.value for e in _assign(PIPE / "roblox_rig.py", "FACE_NAMES").elts]
PRESETS = _keys(PIPE / "roblox_rig.py", "PRESETS")

# ---- one-shot actions (start at the shot start or at a change's "at")
ACTIONS = {
    "idle":         "breathing, tiny weight shifts (default)",
    "talk":         "mouth flaps on the shot's words + explaining gestures",
    "talk_still":   "mouth flaps on the shot's words, body keeps the pose",
    "gestures":     "big explaining arm beats, no mouth",
    "walk_to":      "walk to `to` (a mark of this set) or `to_offset` [dx, dy]",
    "run_to":       "run to `to` / `to_offset`",
    "walk_in":      "walk into frame from `from` (left|right|back) to the mark",
    "walk_out":     "walk out of frame toward `to_side` (left|right)",
    "run_out":      "run out of frame toward `to_side`",
    "jump":         "Roblox jump",
    "celebrate":    "two happy hops + arms up",
    "surprise_hop": "small shocked hop (face goes shocked)",
    "fall_back":    "faint / fall flat on the back",
    "nod":          "nod yes",
    "shake_head":   "shake head no",
    "wave":         "wave hello",
    "laugh":        "lean back laughing",
    "cry":          "hands on face, sobbing",
    "look_around":  "head looks left/right",
    "shiver":       "tremble (scared / cold)",
    "sleep":        "lie down asleep (use on bed mark)",
    "sit_down":     "sit down on the mark's seat",
    "stand_up":     "stand up from the seat",
    "dance":        "silly Roblox dance loop",
    "spin":         "spin 360 on the spot",
    "float":        "rise into the air and bob (no gravity)",
    "poof":         "shrink to nothing (vanish)",
    "pop_in":       "appear from nothing",
    # Phase 03: Interactive & choreography actions
    "handshake":    "coordinated handshake gesture with arm reach and shake",
    "hug":          "coordinated warm embrace with arm wrap and hold",
    "pickup":       "bend waist, reach arm to prop, lift into hold",
    "drop":         "release held prop to ground with gravity drop",
    "pass_prop":    "extend arm with prop to pass to another character",
    "catch_prop":   "reach arm forward to receive prop into hold",
    "approach":     "smooth accelerated walk toward target character or mark",
    "push_prop":    "pushing movement with hands braced forward",
}
# persistent per-character state a cast entry or a change may set
STATE_KEYS = {"pose", "face", "scale", "tint", "props", "action"}

CAMERA_SHOTS = ["extreme_wide", "wide", "medium", "medium_close", "close_up", "extreme_close_up",
                "two_shot", "group", "over_shoulder", "insert"]
CAMERA_ANGLES = ["eye", "low", "high", "top", "dutch"]
CAMERA_MOVES = ["static", "push_in", "pull_out", "pan_left", "pan_right", "orbit_left", "orbit_right",
                "track", "whip_in", "crash_zoom", "shake"]
FACINGS = ["camera", "left", "right", "away", "<character name>", "<mark name>"]
TRANSITIONS = ["cut", "whip", "flash", "fade_black", "glitch"]
FX = {
    "shake":   "camera shake  {type, at, dur, strength}",
    "tint":    "recolor a character's skin  {type, target, color:[r,g,b], amount, at, over}",
    "punch":   "edit-side zoom punch on the beat  {type, at}",
    "flash":   "white flash  {type, at}",
    "freeze":  "freeze-frame + zoom for a beat (edit side)  {type, at, dur}",
    "slowmo":  "not supported",
}
# props (props.py PROP_KINDS): in a hand (cast "props": [...]) or standing in the world (shot "place": [...]).
# "sign:TEXT" / "paper:TEXT" / "flag:TEXT" print TEXT on the prop.
PROP_KINDS = [e.value for e in _assign(PIPE / "props.py", "PROP_KINDS").elts]
TEXT_PROPS = sorted(e.value for e in _assign(PIPE / "props.py", "TEXT_PROPS").elts)
PROPS = [f"{k}:<TEXT>" if k in TEXT_PROPS else k for k in PROP_KINDS]
PLACE_KEYS = {
    "prop":    "prop kind (any of PROPS, text props as 'sign:TEXT')",
    "mark":    "set mark it stands on (required)",
    "id":      "name for camera.target (default place0, place1, ...)",
    "dx/dy/z": "offset from the mark in metres (z lifts it, e.g. onto a table ~2.0)",
    "scale":   "size multiplier (1 = hand size; 4-8 = giant comedy prop)",
    "rot":     "turn around the vertical axis, degrees (0 = front faces the camera side -Y)",
    "pop_at":  "seconds into the shot: appears with a pop (+ pop sfx). Omit = there from the start",
    "poof_at": "seconds into the shot: vanishes with a poof (+ poof sfx)",
}
# ---- Phase 2 character system: pulled from the registry so it cannot drift.
# characters/ is bpy-free by design, so this import is safe outside Blender.
CHARACTERS_NS = None
try:
    if str(PIPE) not in sys.path:
        sys.path.insert(0, str(PIPE))
    import characters as CHARACTERS_NS  # noqa: E402
except Exception:                        # pragma: no cover - registry missing
    CHARACTERS_NS = None

if CHARACTERS_NS:
    HAIR_STYLES = list(CHARACTERS_NS.HAIR_ALL_STYLES)
    OUTFITS = list(CHARACTERS_NS.OUTFITS)
    PRINTS = list(CHARACTERS_NS.PRINTS)
    ACCESSORIES = sorted(CHARACTERS_NS.ACCESSORY_REGISTRY)
    ACCESSORY_ZONES = list(CHARACTERS_NS.ACCESSORY_ZONES)
    IDENTITIES = sorted(CHARACTERS_NS.CHARACTER_IDENTITIES)
    IDENTITY_NAMES = sorted(v["name"] for v in CHARACTERS_NS.CHARACTER_IDENTITIES.values())
    LEGACY_HAIR = [s for s in HAIR_STYLES if s in {"messy", "short", "under_cap", "swept", "long", "pigtails", "bald"}]
else:                                    # pragma: no cover - graceful fallback
    HAIR_STYLES = ["messy", "short", "under_cap", "swept", "long", "pigtails", "bald"]
    OUTFITS = ["none"]
    PRINTS = ["none"]
    ACCESSORIES = []
    ACCESSORY_ZONES = ["head_top", "face", "body"]
    IDENTITIES = []
    IDENTITY_NAMES = []
    LEGACY_HAIR = HAIR_STYLES
HATS = [None, "crown", "police", "cap"]
EXTRAS = ["mustache", "glasses", "monster"]
DETAILS = ["moon", "pocket", "cuffs", "robe", "badge", "belt", "buttons", "collar", "heart", "hood", "kangaroo", "stripes"]
SLEEVES = ["long", "short", "none"]
BOTTOMS = ["pants", "shorts", "skirt"]

CAST_NOTES = {
    "Theo":    "hero kid, brown messy hair, sky-blue moon pajamas (default narrator)",
    "Max":     "best friend, glasses, green hoodie",
    "Lily":    "little sister, ginger pigtails, yellow striped top, pink skirt",
    "Mom":     "mom, long brown hair, lilac heart top",
    "Dad":     "dad, mustache, blue polo",
    "King":    "the town's king, crown + red robe",
    "Officer": "sleepy police officer, cap, mustache",
    "Noob":    "classic Roblox noob (yellow head, blue torso, green legs)",
}


def catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac"}


def _audio_names(d):
    return sorted({p.stem for sub in (d, d / "synth") if sub.exists() for p in sub.iterdir() if p.suffix.lower() in AUDIO_EXT})


def sfx_names():
    return _audio_names(SFX_DIR)


def music_moods():
    return _audio_names(MUSIC_DIR)


def formats():
    return sorted(p.name for p in FORMATS_DIR.iterdir() if (p / "format.json").exists()) if FORMATS_DIR.exists() else []


def cheat_sheet():
    c = catalog()
    L = ["# Engine vocabulary (generated by pipeline/vocab.py)", ""]
    L.append("## Cast (prebuilt)")
    for n in c["characters"]:
        L.append(f"- **{n}**: {CAST_NOTES.get(n, '')}")
    L.append("\n## Cast (Phase 2 identities: appearance + voice live in the identity, not per shot)")
    for cid in IDENTITIES:
        i = CHARACTERS_NS.get(cid)
        if i.get("legacy_preset"):
            continue
        cloth = i.get("clothing") or {}
        hair = i.get("hair") or {}
        accs = ", ".join(i.get("accessories") or []) or "none"
        voice = (i.get("voice") or {}).get("eleven_voice") or "-"
        L.append(f"- **{i['name']}** (`identity: \"{cid}\"`): {i.get('face_style')} face · {hair.get('style')} hair · "
                 f"{cloth.get('outfit', 'none')} outfit · accessories: {accs} · eleven voice: {voice}")
    L.append("- identity rule: `characters: {Name: {\"identity\": \"<id>\"}}` builds whatever the identity says; "
             "appearance overrides on that entry are ignored, so a character looks identical in every scene "
             "(the old `base` + override path still works for one-off looks)")
    L.append("- one-off custom characters: top-level `characters` {Name: {base: <preset>, ...overrides}} "
             f"(hair_style {HAIR_STYLES}, hat {HATS}, extras {EXTRAS}, details {DETAILS}, sleeves {SLEEVES}, "
             f"bottom {BOTTOMS}, colors sRGB 0-1 for skin/hair/top/pants/shoes/accent)")
    L.append(f"- identity asset pool: hair {HAIR_STYLES} (legacy: {', '.join(LEGACY_HAIR)}), outfits {OUTFITS}, "
             f"prints {PRINTS}, accessories {ACCESSORIES} (zones {ACCESSORY_ZONES})")
    L.append("")
    L.append("## Sets -> dressings -> marks  (pos x,y,z / default facing; seat = sit height)")
    for s, info in c["sets"].items():
        ms = []
        for m, v in info["marks"].items():
            if m.startswith("cam_"):
                continue
            ms.append(m + ("(seat)" if "seat" in v else ""))
        L.append(f"- **{s}** [{', '.join(info['dressings'])}]: {', '.join(ms)}")
    L.append("  any cast entry may add `dx`/`dy` (studs, +x = screen right in the default view, +y = deeper)")
    L.append("")
    L.append(f"## Poses\n{', '.join(POSES)}")
    L.append(f"\n## Faces\n{', '.join(FACES)}")
    L.append("\n## Actions")
    for k, v in ACTIONS.items():
        L.append(f"- `{k}`: {v}")
    L.append(f"\n## Camera\n- shot: {', '.join(CAMERA_SHOTS)}\n- angle: {', '.join(CAMERA_ANGLES)}"
             f"\n- move: {', '.join(CAMERA_MOVES)}\n- target: a cast name, a mark, or a placed prop id")
    L.append(f"\n## Facing\n{', '.join(FACINGS)}")
    L.append(f"\n## Transitions (into the NEXT shot)\n{', '.join(TRANSITIONS)}")
    L.append("\n## FX")
    for k, v in FX.items():
        L.append(f"- `{k}`: {v}")
    L.append(f"\n## Props (hand: cast 'props', needs pose 'hold' to show in the hand)\n{', '.join(PROPS)}")
    L.append("\n## World props (shot 'place': [{...}])")
    for k, v in PLACE_KEYS.items():
        L.append(f"- `{k}`: {v}")
    L.append(f"\n## SFX\n{', '.join(sfx_names()) or '(none yet: run pipeline/make_audio_assets.py)'}")
    L.append(f"\n## Music moods\n{', '.join(music_moods()) or '(none)'}")
    L.append(f"\n## Formats\n{', '.join(formats()) or '(none)'}")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(cheat_sheet())
