"""
Shot Compiler: converts intermediate storyboard.json <-> shots.json.

    python pipeline/compiler.py episodes/<ep>                  # compile storyboard.json -> shots.json
    python pipeline/compiler.py episodes/<ep> --from-shots     # extract shots.json -> storyboard.json
    python pipeline/compiler.py episodes/<ep> --check          # validate storyboard.json without writing

Enforces strict vocabulary against catalog.json and vocab.py before writing shots.json,
and preserves narration text, shot IDs, speaker assignments, and top-level episode metadata
so voiceover timing (timing.json) remains intact.
"""
import argparse, json, re, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocab as V      # noqa: E402
import validate as VA  # noqa: E402

STORYBOARD_SHOT_KEYS = {
    "id", "speaker", "narration", "hold", "duration",
    "visual_goal", "location", "dressing",
    "characters", "character_positions", "character_actions",
    "character_expressions", "character_changes",
    "props", "camera_framing", "camera_angle", "camera_movement", "camera_target",
    "fx", "sfx", "transition", "caption_emphasis",
}


def infer_visual_goal(shot):
    """Summarize the visual intent of an existing shots.json entry."""
    st = shot.get("set", "street")
    cam = shot.get("camera", {})
    cast_bits = []
    for c in shot.get("cast", []):
        n = c.get("name", "?")
        act = c.get("action", "idle")
        pose = c.get("pose", "relaxed")
        face = c.get("face", "smile")
        props = c.get("props", [])
        desc = f"{n} ({pose}/{face}, {act})"
        if props:
            desc += f" holding {props}"
        cast_bits.append(desc)
    return f"{st} [{cam.get('shot', 'medium')}/{cam.get('angle', 'eye')}/{cam.get('move', 'static')}]: " + ", ".join(cast_bits)


def shots_to_storyboard(shots_data):
    """Convert a shots.json dict into the structured intermediate storyboard.json dict."""
    sb_shots = []
    for s in shots_data.get("shots", []):
        cast = s.get("cast", [])
        char_names = [c["name"] for c in cast if "name" in c]
        positions = {}
        actions = {}
        expressions = {}
        changes = {}
        hand_props = {}

        for c in cast:
            n = c["name"]
            pos_entry = {"mark": c.get("mark", "center")}
            if c.get("dx"):
                pos_entry["dx"] = round(float(c["dx"]), 2)
            if c.get("dy"):
                pos_entry["dy"] = round(float(c["dy"]), 2)
            pos_entry["facing"] = c.get("facing", "camera")
            positions[n] = pos_entry

            act_entry = {
                "pose": c.get("pose", "relaxed"),
                "action": c.get("action", "idle"),
            }
            for k in ("to", "to_offset", "to_dx", "to_dy", "from", "to_side", "face_after", "scale", "tint"):
                if k in c:
                    act_entry[k] = c[k]
            actions[n] = act_entry
            expressions[n] = c.get("face", "smile")
            if c.get("changes"):
                changes[n] = c["changes"]
            if c.get("props"):
                hand_props[n] = list(c["props"])

        cam = s.get("camera", {})
        sb_shot = {
            "id": s["id"],
            "speaker": s.get("speaker", "narrator"),
            "narration": s.get("text", ""),
            "visual_goal": s.get("visual_goal") or infer_visual_goal(s),
            "location": s.get("set", "street"),
            "dressing": s.get("dressing") or V.catalog()["sets"].get(s.get("set", "street"), {}).get("dressings", ["day"])[0],
            "characters": char_names,
            "character_positions": positions,
            "character_actions": actions,
            "character_expressions": expressions,
            "character_changes": changes,
            "props": {
                "hand": hand_props,
                "placed": list(s.get("place", [])),
            },
            "camera_framing": cam.get("shot", "medium"),
            "camera_angle": cam.get("angle", "eye"),
            "camera_movement": cam.get("move", "static"),
            "camera_target": cam.get("target") or (char_names[0] if char_names else "center"),
            "fx": list(s.get("fx", [])),
            "sfx": list(s.get("sfx", [])),
            "transition": s.get("transition", "cut"),
            "caption_emphasis": list(s.get("emphasis", [])),
        }
        if "hold" in s:
            sb_shot["hold"] = s["hold"]
        if "duration" in s:
            sb_shot["duration"] = s["duration"]
        sb_shots.append(sb_shot)

    meta = {k: v for k, v in shots_data.items() if k != "shots"}
    return {
        "schema_version": "1.0",
        "episode": shots_data.get("episode", ""),
        "metadata": meta,
        "storyboard": sb_shots,
    }


def validate_storyboard(sb_data, ep_name=None):
    """Validate storyboard.json against catalog.json and vocab.py before compiling."""
    errs = []
    E = errs.append
    if not isinstance(sb_data, dict):
        return ["storyboard.json root must be a JSON object"]
    sb_shots = sb_data.get("storyboard")
    if not isinstance(sb_shots, list) or not sb_shots:
        return ["storyboard.json must contain a non-empty 'storyboard' list"]

    cat = V.catalog()
    sfx_ok = set(V.sfx_names())
    prop_kinds = set(V.PROP_KINDS)
    meta = sb_data.get("metadata", {})
    custom = meta.get("characters", {})
    cast_ok = set(cat["characters"]) | set(custom)
    speakers_ok = {"narrator"} | cast_ok

    if ep_name and sb_data.get("episode") and sb_data["episode"] != ep_name:
        E(f"storyboard episode {sb_data['episode']!r} does not match folder {ep_name!r}")

    seen_ids = set()
    for i, sb in enumerate(sb_shots):
        sid = sb.get("id", f"#{i}")
        P = f"storyboard[{sid}]:"
        if sid in seen_ids:
            E(f"{P} duplicate shot id")
        seen_ids.add(sid)
        unknown = set(sb.keys()) - STORYBOARD_SHOT_KEYS
        if unknown:
            E(f"{P} unknown storyboard field(s) {sorted(unknown)}")
        loc = sb.get("location")
        if loc not in cat["sets"]:
            E(f"{P} location {loc!r} not in {list(cat['sets'])}")
            continue
        marks = cat["sets"][loc]["marks"]
        dressings = cat["sets"][loc]["dressings"]
        if sb.get("dressing") and sb["dressing"] not in dressings:
            E(f"{P} dressing {sb.get('dressing')!r} not in {dressings}")
        if sb.get("speaker", "narrator") not in speakers_ok:
            E(f"{P} speaker {sb.get('speaker')!r} not in {sorted(speakers_ok)}")

        chars = sb.get("characters", [])
        if len(chars) != len(set(chars)):
            E(f"{P} duplicate character in 'characters'")
        pos_map = sb.get("character_positions", {})
        act_map = sb.get("character_actions", {})
        exp_map = sb.get("character_expressions", {})
        chg_map = sb.get("character_changes", {})
        props_spec = sb.get("props", {})
        hand_map = props_spec.get("hand", {}) if isinstance(props_spec, dict) else {}
        placed_list = props_spec.get("placed", []) if isinstance(props_spec, dict) else []

        for n in chars:
            if n not in cast_ok:
                E(f"{P} character {n!r} not in allowed cast {sorted(cast_ok)}")
            p_info = pos_map.get(n, {})
            mk = p_info.get("mark")
            if mk not in marks:
                E(f"{P} {n} mark {mk!r} not in {loc} marks")
            fcg = p_info.get("facing", "camera")
            if fcg not in ("camera", "left", "right", "away") and fcg not in chars and fcg not in marks:
                E(f"{P} {n} facing {fcg!r} invalid")

            a_info = act_map.get(n, {})
            if a_info.get("pose", "relaxed") not in V.POSES:
                E(f"{P} {n} pose {a_info.get('pose')!r} not in POSES")
            if a_info.get("action", "idle") not in V.ACTIONS:
                E(f"{P} {n} action {a_info.get('action')!r} not in ACTIONS")
            if a_info.get("to") and a_info["to"] not in marks:
                E(f"{P} {n} destination mark {a_info['to']!r} not in {loc} marks")

            face = exp_map.get(n, "smile")
            if face not in V.FACES:
                E(f"{P} {n} expression {face!r} not in FACES")

            for hp in hand_map.get(n, []):
                if str(hp).split(":")[0] not in prop_kinds:
                    E(f"{P} {n} hand prop {hp!r} not in PROPS")

            for ch in chg_map.get(n, []):
                if "at" not in ch:
                    E(f"{P} {n} change missing 'at'")
                if "pose" in ch and ch["pose"] not in V.POSES:
                    E(f"{P} {n} change pose {ch['pose']!r} not in POSES")
                if "face" in ch and ch["face"] not in V.FACES:
                    E(f"{P} {n} change face {ch['face']!r} not in FACES")
                if "action" in ch and ch["action"] not in V.ACTIONS:
                    E(f"{P} {n} change action {ch['action']!r} not in ACTIONS")
                if ch.get("to") and ch["to"] not in marks:
                    E(f"{P} {n} change destination {ch['to']!r} not in {loc} marks")
                for cp in ch.get("props", []):
                    if str(cp).split(":")[0] not in prop_kinds:
                        E(f"{P} {n} change prop {cp!r} not in PROPS")

        placed_ids = set()
        for k, pl in enumerate(placed_list):
            if str(pl.get("prop", "")).split(":")[0] not in prop_kinds:
                E(f"{P} placed[{k}] prop {pl.get('prop')!r} not in PROPS")
            if pl.get("mark") not in marks:
                E(f"{P} placed[{k}] mark {pl.get('mark')!r} not in {loc} marks")
            pid = pl.get("id", f"place{k}")
            placed_ids.add(pid)

        if sb.get("camera_framing", "medium") not in V.CAMERA_SHOTS:
            E(f"{P} camera_framing {sb.get('camera_framing')!r} not in {V.CAMERA_SHOTS}")
        if sb.get("camera_angle", "eye") not in V.CAMERA_ANGLES:
            E(f"{P} camera_angle {sb.get('camera_angle')!r} not in {V.CAMERA_ANGLES}")
        if sb.get("camera_movement", "static") not in V.CAMERA_MOVES:
            E(f"{P} camera_movement {sb.get('camera_movement')!r} not in {V.CAMERA_MOVES}")
        tgt = sb.get("camera_target")
        if tgt and tgt not in chars and tgt not in marks and tgt not in placed_ids:
            E(f"{P} camera_target {tgt!r} is not a cast member, mark of {loc}, or placed prop id")
        if sb.get("transition", "cut") not in V.TRANSITIONS:
            E(f"{P} transition {sb.get('transition')!r} not in {V.TRANSITIONS}")
        for x in sb.get("sfx", []):
            if x.get("name") not in sfx_ok:
                E(f"{P} sfx {x.get('name')!r} not in {sorted(sfx_ok)}")
        for fx in sb.get("fx", []):
            if fx.get("type") not in V.FX or fx.get("type") == "slowmo":
                E(f"{P} fx {fx.get('type')!r} not supported")

    return errs


def compile_storyboard(sb_data, base_shots_data=None):
    """Compile a validated storyboard.json dict into the engine's shots.json dict."""
    meta = dict(base_shots_data or {})
    meta.update(sb_data.get("metadata", {}))
    if sb_data.get("episode"):
        meta["episode"] = sb_data["episode"]

    orig_by_id = {s["id"]: s for s in (base_shots_data or {}).get("shots", []) if "id" in s}
    compiled_shots = []

    for sb in sb_data.get("storyboard", []):
        sid = sb["id"]
        orig = orig_by_id.get(sid, {})
        # Preserve original narration text & speaker when compiling a directed storyboard
        text = orig.get("text") if "text" in orig and orig["text"] else sb.get("narration", "")
        speaker = orig.get("speaker") if "speaker" in orig else sb.get("speaker", "narrator")

        chars = sb.get("characters", [])
        pos_map = sb.get("character_positions", {})
        act_map = sb.get("character_actions", {})
        exp_map = sb.get("character_expressions", {})
        chg_map = sb.get("character_changes", {})
        props_spec = sb.get("props", {})
        hand_map = props_spec.get("hand", {}) if isinstance(props_spec, dict) else {}
        placed_list = props_spec.get("placed", []) if isinstance(props_spec, dict) else []

        cast = []
        for n in chars:
            p_info = pos_map.get(n, {})
            a_info = act_map.get(n, {})
            entry = {
                "name": n,
                "mark": p_info.get("mark", "center"),
            }
            if "dx" in p_info and abs(float(p_info["dx"])) > 1e-4:
                entry["dx"] = round(float(p_info["dx"]), 2)
            if "dy" in p_info and abs(float(p_info["dy"])) > 1e-4:
                entry["dy"] = round(float(p_info["dy"]), 2)
            entry["facing"] = p_info.get("facing", "camera")
            entry["pose"] = a_info.get("pose", "relaxed")
            entry["face"] = exp_map.get(n, "smile")
            entry["action"] = a_info.get("action", "idle")

            for k in ("to", "to_offset", "to_dx", "to_dy", "from", "to_side", "face_after", "scale", "tint"):
                if k in a_info:
                    entry[k] = a_info[k]
            if hand_map.get(n):
                entry["props"] = list(hand_map[n])
            if chg_map.get(n):
                entry["changes"] = list(chg_map[n])
            cast.append(entry)

        shot_out = {
            "id": sid,
            "set": sb.get("location", "street"),
            "dressing": sb.get("dressing", "day"),
            "speaker": speaker,
            "text": text,
        }
        if "hold" in orig:
            shot_out["hold"] = orig["hold"]
        elif "hold" in sb:
            shot_out["hold"] = sb["hold"]
        if "duration" in orig:
            shot_out["duration"] = orig["duration"]
        elif "duration" in sb:
            shot_out["duration"] = sb["duration"]

        shot_out["camera"] = {
            "shot": sb.get("camera_framing", "medium"),
            "angle": sb.get("camera_angle", "eye"),
            "move": sb.get("camera_movement", "static"),
            "target": sb.get("camera_target") or (chars[0] if chars else "center"),
        }
        shot_out["cast"] = cast
        if placed_list:
            shot_out["place"] = placed_list
        if sb.get("fx"):
            shot_out["fx"] = list(sb["fx"])
        if sb.get("sfx"):
            shot_out["sfx"] = list(sb["sfx"])

        # Validate emphasis words against text
        low_words = set(re.sub(r"[^\w' ]", "", text.lower()).split())
        emph = [w for w in sb.get("caption_emphasis", []) if w.lower() in low_words]
        if not emph and orig.get("emphasis"):
            emph = [w for w in orig["emphasis"] if w.lower() in low_words]
        shot_out["emphasis"] = emph
        shot_out["transition"] = sb.get("transition", "cut")
        compiled_shots.append(shot_out)

    meta["shots"] = compiled_shots
    return meta


def compile_episode(ep_dir, check_only=False):
    ep = Path(ep_dir).resolve()
    sb_file = ep / "storyboard.json"
    shots_file = ep / "shots.json"
    if not sb_file.exists():
        raise FileNotFoundError(f"Missing {sb_file}. Run 'python pipeline/director.py {ep.name}' first.")

    sb_data = json.loads(sb_file.read_text(encoding="utf-8"))
    errs = validate_storyboard(sb_data, ep.name)
    if errs:
        return errs, []

    base_shots = json.loads(shots_file.read_text(encoding="utf-8")) if shots_file.exists() else {}
    compiled = compile_storyboard(sb_data, base_shots)

    if check_only:
        return [], []

    if shots_file.exists():
        shutil.copy2(shots_file, ep / "shots.pre_compile.json")
    shots_file.write_text(json.dumps(compiled, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return VA.validate(ep)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Compile storyboard.json <-> shots.json with strict vocabulary validation.")
    ap.add_argument("episode_dir", help="Episode folder path (e.g. episodes/wi_3am_monster)")
    ap.add_argument("--from-shots", action="store_true", help="Extract storyboard.json from existing shots.json")
    ap.add_argument("--check", action="store_true", help="Validate storyboard.json without writing shots.json")
    a = ap.parse_args()

    ep = Path(a.episode_dir).resolve()
    if a.from_shots:
        shots_file = ep / "shots.json"
        if not shots_file.exists():
            sys.exit(f"ERROR: {shots_file} not found")
        d = json.loads(shots_file.read_text(encoding="utf-8"))
        sb = shots_to_storyboard(d)
        out = ep / "storyboard.json"
        out.write_text(json.dumps(sb, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {out} ({len(sb['storyboard'])} shots)")
        return

    errs, warns = compile_episode(ep, check_only=a.check)
    for w in warns:
        print("WARN ", w)
    for e in errs:
        print("ERROR", e)
    if errs:
        print(f"COMPILE FAILED: {len(errs)} error(s)")
        sys.exit(1)
    print(f"compiled {ep / 'storyboard.json'} -> {ep / 'shots.json'} (0 errors, {len(warns)} warnings)")


if __name__ == "__main__":
    main()
