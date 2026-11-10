"""
Validate an episode shots.json against the pipeline (cast, poses, expressions, sets, marks).
Runs with plain Python (no Blender needed):
    python pipeline/validate_shots.py episodes/ep01_blue_lies/shots.json
"""
import ast, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SETS = {
    "town_square": {"podium", "stage_left", "stage_right", "center", "crowd_front_l", "crowd_front_r", "crowd_back_l", "crowd_back_r"},
    "street": {"sidewalk_a", "sidewalk_b", "sidewalk_c", "mailbox", "grandpa_door", "path_start"},
    "house_interior": {"table_a", "table_b", "couch", "door"},
    "hero_room": {"mirror", "bed", "door", "window", "center"},
}
CAM_SHOTS = {"extreme_wide", "wide", "medium", "medium_close", "close_up", "extreme_close_up", "two_shot", "over_shoulder", "insert"}
CAM_ANGLES = {"eye", "low", "high", "top", "dutch"}
CAM_MOVES = {"static", "push_in", "pull_out", "pan_left", "pan_right", "orbit_left", "orbit_right", "track", "whip_in", "shake"}
ACTIONS = {"idle", "talk", "gestures", "walk_in", "walk_to", "surprise_hop", "nod", "shake_head", "jump", "blink"}
FX = {"blue_skin", "silhouette"}
TRANSITIONS = {"cut", "whip", "flash", "fade_black"}


def dict_keys(path, var):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == var for t in node.targets):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise KeyError(f"{var} not found in {path}")


def main(p):
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    cast = dict_keys(ROOT / "cast.py", "CAST")
    poses = dict_keys(ROOT / "motions.py", "POSES")
    exprs = dict_keys(ROOT / "blocky_rig.py", "EXPRESSIONS")
    errs, total, used = [], 0.0, set()
    ids = set()
    for s in data["shots"]:
        sid = s["id"]
        if sid in ids: errs.append(f"{sid}: duplicate id")
        ids.add(sid)
        total += s["duration"]
        st = s["set"]
        if st not in SETS: errs.append(f"{sid}: unknown set {st}")
        names = {c["name"] for c in s["cast"]}
        if s["speaker"] not in ("narrator",) and s["speaker"] not in names:
            errs.append(f"{sid}: speaker {s['speaker']} not in shot")
        cam = s["camera"]
        for k, ok in (("shot", CAM_SHOTS), ("angle", CAM_ANGLES), ("move", CAM_MOVES)):
            if cam[k] not in ok: errs.append(f"{sid}: camera.{k} '{cam[k]}' invalid")
        if cam["target"] not in names and cam["target"] not in SETS.get(st, set()):
            errs.append(f"{sid}: camera target '{cam['target']}' is neither a cast member in shot nor a mark")
        marks_used = set()
        for c in s["cast"]:
            n = c["name"]; used.add(n)
            if n not in cast: errs.append(f"{sid}: unknown character {n}")
            if c["mark"] not in SETS.get(st, set()): errs.append(f"{sid}: {n} mark '{c['mark']}' not in {st}")
            if c["mark"] in marks_used: errs.append(f"{sid}: two characters on mark {c['mark']}")
            marks_used.add(c["mark"])
            if c["pose"] not in poses: errs.append(f"{sid}: {n} pose '{c['pose']}' unknown")
            if c["expression"] not in exprs: errs.append(f"{sid}: {n} expression '{c['expression']}' unknown")
            if c["action"] not in ACTIONS: errs.append(f"{sid}: {n} action '{c['action']}' unknown")
            f = c["facing"]
            if f not in {"camera", "left", "right", "away"} | names | SETS.get(st, set()):
                errs.append(f"{sid}: {n} facing '{f}' invalid")
            for ch in c.get("changes", []):
                if not 0 <= ch["at"] <= s["duration"]: errs.append(f"{sid}: {n} change at {ch['at']} outside shot")
                if "pose" in ch and ch["pose"] not in poses: errs.append(f"{sid}: change pose '{ch['pose']}' unknown")
                if "expression" in ch and ch["expression"] not in exprs: errs.append(f"{sid}: change expression '{ch['expression']}' unknown")
        for fx in s.get("fx", []):
            if fx["type"] not in FX: errs.append(f"{sid}: fx '{fx['type']}' unknown")
            if fx.get("target") not in names: errs.append(f"{sid}: fx target {fx.get('target')} not in shot")
        for sf in s.get("sfx", []):
            if not 0 <= sf["at"] <= s["duration"]: errs.append(f"{sid}: sfx {sf['name']} at {sf['at']} outside shot")
        if s.get("transition", "cut") not in TRANSITIONS: errs.append(f"{sid}: transition invalid")
    words = sum(len(s["text"].split()) for s in data["shots"])
    print(f"{len(data['shots'])} shots, {total:.1f}s estimated, {words} words "
          f"({words / max(total, 1):.2f} words/s), characters used: {sorted(used)}")
    sets_used = sorted({s['set'] for s in data['shots']})
    print("sets needed:", sets_used)
    props = sorted({p for s in data["shots"] for c in s["cast"] for p in c.get("props", [])})
    print("props needed:", props)
    sfx = sorted({x["name"] for s in data["shots"] for x in s.get("sfx", [])})
    print("sfx needed:", sfx)
    if errs:
        print(f"\n{len(errs)} problem(s):")
        for e in errs: print("  -", e)
        return 1
    print("\nOK: no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "episodes/ep01_blue_lies/shots.json"))
