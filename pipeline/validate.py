"""
Check an episode's shots.json against the engine vocabulary and cinematic QA rules
before anything slow runs.

    python pipeline/validate.py episodes/<ep>
    python pipeline/validate.py episodes/<ep> --json

Exit code 1 on technical errors. Cinematic / pacing / continuity warnings are reported
with actionable suggestions and do not block production.
"""
import argparse, json, math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocab as V  # noqa: E402

PROP_KINDS = set(V.PROP_KINDS)
PLACE_KEYS = {"prop", "mark", "id", "dx", "dy", "z", "scale", "rot", "pop_at", "poof_at"}
CHANGE_KEYS = {"at", "pose", "face", "action", "scale", "over", "tint", "props", "to", "to_offset", "to_dx", "to_dy",
               "from", "to_side", "face_after"}
CAST_KEYS = {"name", "mark", "dx", "dy", "facing", "pose", "face", "action", "changes", "scale", "tint", "props",
             "to", "to_offset", "to_dx", "to_dy", "from", "to_side", "face_after"}

# Derived from pipeline/roblox_rig.py (torso 2x1x2, arms at x=±1.5 width 1 -> total arm span 4.0 studs)
R6_TORSO_W = 2.0
R6_ARM_SPAN = 4.0
R6_MIN_SEPARATION = 2.0   # minimum center-to-center XY studs before shoulders/arms overlap

# Derived from pipeline/roblox_motions.py locomotion speeds & one-shot durations (@30fps)
WALK_SPEED = 6.0          # studs / second
RUN_SPEED = 14.0          # studs / second
LOCO_OVERHEAD = 0.30      # 4 turn frames + 5 settle frames at 30fps
ACTION_DURATIONS = {
    "jump": 0.77,         # 3 + 14 + 6 frames
    "surprise_hop": 0.24, # 7 frames
    "fall_back": 0.54,    # 16 frames
    "wave": 1.27,         # 38 frames
    "nod": 0.67,          # 20 frames
    "shake_head": 0.80,   # 24 frames
    "look_around": 1.67,  # 50 frames
    "celebrate": 1.27,    # 38 frames
    "spin": 0.60,         # 18 frames
    "sit_down": 0.27,     # 8 frames
    "stand_up": 0.27,     # 8 frames
    "walk_in": 1.97,      # 10 studs @ 6 studs/s + overhead
    "walk_out": 2.63,     # 14 studs @ 6 studs/s + overhead
    "run_out": 1.30,      # 14 studs @ 14 studs/s + overhead
}

MOVEMENT_VERBS = {
    "walk", "walks", "walked", "walking",
    "run", "runs", "ran", "running",
    "sprint", "sprints", "sprinted", "sprinting",
    "jump", "jumps", "jumped", "jumping",
    "rush", "rushes", "rushed", "rushing",
    "burst", "bursts", "bolted", "escape", "escaped", "escaping",
    "pull", "pulled", "enter", "entered", "arrive", "arrives", "arrived",
    "collapse", "collapsed", "faint", "fainted", "fall", "falls", "fell",
}


def _world_xy(marks, mark_name, dx=0.0, dy=0.0):
    info = marks.get(mark_name)
    if not info:
        return None
    pos = info["pos"]
    return (float(pos[0]) + float(dx or 0.0), float(pos[1]) + float(dy or 0.0))


def _dest_xy(marks, start_xy, act_spec):
    if act_spec.get("to") and act_spec["to"] in marks:
        return _world_xy(marks, act_spec["to"], act_spec.get("to_dx", 0.0), act_spec.get("to_dy", 0.0))
    off = act_spec.get("to_offset")
    if isinstance(off, (list, tuple)) and len(off) >= 2 and start_xy is not None:
        return (start_xy[0] + float(off[0]), start_xy[1] + float(off[1]))
    if start_xy is not None and act_spec.get("action") in ("walk_to", "run_to"):
        return (start_xy[0], start_xy[1] + 6.0)
    return None


def validate_detailed(ep_dir):
    ep = Path(ep_dir)
    errs, warns = [], []
    per_shot = {}

    def add_err(msg, sid=None, fix=None):
        errs.append(msg)
        if sid:
            per_shot.setdefault(sid, {"errors": [], "warnings": [], "suggestions": []})
            per_shot[sid]["errors"].append(msg)
            if fix:
                per_shot[sid]["suggestions"].append(fix)

    def add_warn(msg, sid=None, fix=None):
        warns.append(msg)
        if sid:
            per_shot.setdefault(sid, {"errors": [], "warnings": [], "suggestions": []})
            per_shot[sid]["warnings"].append(msg)
            if fix:
                per_shot[sid]["suggestions"].append(fix)

    try:
        d = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"errors": [f"shots.json unreadable: {e}"], "warnings": [], "shots": {}}

    timing_map = {}
    timing_file = ep / "timing.json"
    if timing_file.exists():
        try:
            td = json.loads(timing_file.read_text(encoding="utf-8"))
            timing_map = {s["id"]: s for s in td.get("shots", []) if "id" in s}
        except Exception:
            pass

    cat = V.catalog()
    sfx = set(V.sfx_names())
    fmts = set(V.formats())

    if d.get("format") not in fmts:
        add_err(f"format {d.get('format')!r} not in {sorted(fmts)}")
    for k in ("episode", "title", "shots"):
        if k not in d:
            add_err(f"missing top-level {k!r}")
    if d.get("episode") and d["episode"] != ep.name:
        add_err(f"episode {d['episode']!r} must equal the folder name {ep.name!r}")
    if d.get("music") and d["music"] not in V.music_moods():
        add_err(f"music {d['music']!r} not in {V.music_moods()}")

    custom = d.get("characters", {})
    for n, spec in custom.items():
        if spec.get("base", "Theo") not in V.PRESETS:
            add_err(f"character {n}: base {spec.get('base')!r} not in {V.PRESETS}")
        if spec.get("hair_style") and spec["hair_style"] not in V.HAIR_STYLES:
            add_err(f"character {n}: hair_style {spec['hair_style']!r} not in {V.HAIR_STYLES}")
        if spec.get("hat") not in V.HATS:
            add_err(f"character {n}: hat {spec.get('hat')!r} not in {V.HATS}")
        for x in spec.get("extras", []):
            if x not in V.EXTRAS:
                add_err(f"character {n}: extra {x!r} not in {V.EXTRAS}")
        for x in spec.get("details", []):
            if x not in V.DETAILS:
                add_err(f"character {n}: detail {x!r} not in {V.DETAILS}")
        if n in cat["characters"]:
            add_err(f"character {n}: name clashes with a prebuilt character")
    cast_ok = set(cat["characters"]) | set(custom)
    speakers = {"narrator"} | cast_ok

    ids = set()
    shots = d.get("shots", [])
    if not shots:
        add_err("no shots")

    prev_cam_sig = None
    shot_size_run = []
    prev_set = None
    prev_dressing = None
    prev_char_scale = {}

    for i, s in enumerate(shots):
        sid = s.get("id", f"#{i}")
        per_shot.setdefault(sid, {"errors": [], "warnings": [], "suggestions": []})
        P = f"{sid}:"
        if sid in ids:
            add_err(f"{P} duplicate id", sid)
        ids.add(sid)
        st = s.get("set")
        if st not in cat["sets"]:
            add_err(f"{P} set {st!r} not in {list(cat['sets'])}", sid)
            continue
        marks = cat["sets"][st]["marks"]
        dressing = s.get("dressing") or cat["sets"][st]["dressings"][0]
        if s.get("dressing") and s["dressing"] not in cat["sets"][st]["dressings"]:
            add_err(f"{P} dressing {s['dressing']!r} not in {cat['sets'][st]['dressings']}", sid)

        text = (s.get("text") or "").strip()
        spk = s.get("speaker", "narrator")
        if spk not in speakers:
            add_err(f"{P} speaker {spk!r} must be 'narrator' or a cast name", sid)
        if not text and "duration" not in s:
            add_err(f"{P} silent shot needs a 'duration'", sid)

        nw = len(text.split())
        t_info = timing_map.get(sid)
        est_dur = float(t_info["duration"]) if t_info else (nw / 2.8 + float(s.get("hold", 0.0)) if nw else float(s.get("duration", 1.5)))
        if nw > 16:
            add_warn(f"{P} {nw} words in one shot (~{nw / 2.8:.1f}s) - split it, cuts should land every 1.5-3 s",
                     sid, "Split long narration into two consecutive shots or tighten wording to <= 14 words.")

        names = [c.get("name") for c in s.get("cast", [])]
        if len(names) != len(set(names)):
            add_err(f"{P} a character appears twice", sid)

        # Speaker presence check for dialogue lines
        if spk != "narrator" and spk in cast_ok and spk not in names:
            add_warn(f"{P} speaker {spk!r} is not in the shot's cast",
                     sid, f"Add {spk!r} to cast or change speaker to 'narrator'.")

        cam = s.get("camera", {})
        c_shot = cam.get("shot", "medium")
        c_angle = cam.get("angle", "eye")
        c_move = cam.get("move", "static")
        if c_shot not in V.CAMERA_SHOTS:
            add_err(f"{P} camera.shot {c_shot!r} not in {V.CAMERA_SHOTS}", sid)
        if c_angle not in V.CAMERA_ANGLES:
            add_err(f"{P} camera.angle {c_angle!r} not in {V.CAMERA_ANGLES}", sid)
        if c_move not in V.CAMERA_MOVES:
            add_err(f"{P} camera.move {c_move!r} not in {V.CAMERA_MOVES}", sid)

        # Cinematic check 1: Consecutive identical camera compositions / 3 identical framings
        cam_sig = (c_shot, c_angle, c_move)
        if prev_cam_sig == cam_sig:
            add_warn(f"{P} consecutive shot repeats identical camera composition ({c_shot}, {c_angle}, {c_move})",
                     sid, "Vary camera shot size, angle, or movement from the previous shot.")
        prev_cam_sig = cam_sig

        shot_size_run.append(c_shot)
        if len(shot_size_run) >= 3 and shot_size_run[-1] == shot_size_run[-2] == shot_size_run[-3]:
            add_warn(f"{P} 3 identical camera shot sizes ({c_shot!r}) in a row",
                     sid, "Alternate between wide/medium/two_shot/close_up framings.")

        placed = set()
        for k, pl in enumerate(s.get("place", [])):
            R = f"{P} place[{k}]:"
            for key in pl:
                if key not in PLACE_KEYS:
                    add_err(f"{R} unknown key {key!r} (allowed {sorted(PLACE_KEYS)})", sid)
            if str(pl.get("prop", "")).split(":")[0] not in PROP_KINDS:
                add_err(f"{R} prop {pl.get('prop')!r} not in {V.PROPS}", sid)
            if pl.get("mark") not in marks:
                add_err(f"{R} mark {pl.get('mark')!r} not a mark of {st}", sid)
            for key in ("dx", "dy", "z", "scale", "rot", "pop_at", "poof_at"):
                if key in pl and not isinstance(pl[key], (int, float)):
                    add_err(f"{R} {key} must be a number", sid)
            if isinstance(pl.get("scale"), (int, float)) and not 0.1 <= pl["scale"] <= 30:
                add_warn(f"{R} scale {pl['scale']} is extreme", sid)
            for key in ("pop_at", "poof_at"):
                if isinstance(pl.get(key), (int, float)) and pl[key] < 0:
                    add_err(f"{R} {key} must be >= 0 seconds", sid)
            pid = pl.get("id", f"place{k}")
            if pid in placed or pid in names:
                add_err(f"{R} id {pid!r} is used twice in this shot", sid)
            placed.add(pid)

        tgt = cam.get("target")
        if tgt and tgt not in names and tgt not in marks and tgt not in placed:
            add_err(f"{P} camera.target {tgt!r} is neither a cast member, a mark of {st}, nor a placed prop id", sid)
        if c_shot in ("two_shot", "over_shoulder") and len(names) < 2:
            add_warn(f"{P} {c_shot} with fewer than 2 characters",
                     sid, "Add a second character or switch camera.shot to 'medium' / 'medium_close'.")

        # Cinematic check 5: Camera target mismatch
        if tgt and tgt in marks and not tgt.startswith("cam_") and names and c_shot in ("close_up", "extreme_close_up", "medium_close"):
            add_warn(f"{P} {c_shot} targets mark {tgt!r} instead of a character in cast {names}",
                     sid, f"Set camera.target to {names[0]!r} so the close-up frames the character's face.")

        if s.get("transition", "cut") not in V.TRANSITIONS:
            add_err(f"{P} transition {s.get('transition')!r} not in {V.TRANSITIONS}", sid)
        for fx in s.get("fx", []):
            if fx.get("type") not in V.FX or fx.get("type") == "slowmo":
                add_err(f"{P} fx {fx.get('type')!r} not supported", sid)
            if fx.get("type") == "tint" and fx.get("target") not in names:
                add_err(f"{P} tint target {fx.get('target')!r} not in this shot", sid)
        for x in s.get("sfx", []):
            if x.get("name") not in sfx:
                add_err(f"{P} sfx {x.get('name')!r} not in {sorted(sfx)}", sid)

        low = re.sub(r"[^\w' ]", "", text.lower()).split()
        for w in s.get("emphasis", []):
            if w.lower() not in low:
                add_warn(f"{P} emphasis {w!r} is not a word of the line",
                         sid, "Pick an emphasis keyword that appears verbatim in the shot's text.")

        # Track character coordinates & actions for cinematic checks
        char_coords = []
        any_non_idle = False
        any_changes = False

        for c in s.get("cast", []):
            n = c.get("name")
            Q = f"{P} {n}:"
            if n not in cast_ok:
                add_err(f"{Q} unknown character (prebuilt: {cat['characters']}, or define it in 'characters')", sid)
            for k in c:
                if k not in CAST_KEYS:
                    add_err(f"{Q} unknown key {k!r}", sid)
            mk = c.get("mark")
            if mk not in marks:
                add_err(f"{Q} mark {mk!r} not in {st} marks {[m for m in marks if not m.startswith('cam_')]}", sid)
            if c.get("pose", "relaxed") not in V.POSES:
                add_err(f"{Q} pose {c.get('pose')!r} not in POSES", sid)
            if c.get("face", "smile") not in V.FACES:
                add_err(f"{Q} face {c.get('face')!r} not in {V.FACES}", sid)
            act0 = c.get("action", "idle")
            if act0 not in V.ACTIONS:
                add_err(f"{Q} action {act0!r} not in ACTIONS", sid)
            if act0 != "idle":
                any_non_idle = True
            f = c.get("facing", "camera")
            if f not in ("camera", "left", "right", "away") and f not in names and f not in marks:
                add_err(f"{Q} facing {f!r} must be camera/left/right/away, a cast member of this shot or a mark", sid)
            if c.get("pose") == "sit" and "seat" not in marks.get(mk, {}):
                add_warn(f"{Q} sits on mark {mk!r} which has no seat (will hover / clip)",
                         sid, f"Move {n} to a seat mark or change pose from 'sit'.")

            for p in c.get("props", []):
                if p.split(":")[0] not in PROP_KINDS:
                    add_err(f"{Q} prop {p!r} not in {V.PROPS}", sid)
            # Cinematic check 4: Prop cropping
            all_char_props = list(c.get("props", [])) + [p for ch in c.get("changes", []) for p in ch.get("props", [])]
            if all_char_props and tgt == n and c_shot in ("medium_close", "close_up", "extreme_close_up"):
                add_warn(f"{Q} holds {all_char_props} but the {c_shot} crops below the chest - use medium to show the prop",
                         sid, "Change camera.shot to 'medium' or 'two_shot' so held props are visible.")

            if c.get("to") and c["to"] not in marks:
                add_err(f"{Q} walk target {c['to']!r} not a mark of {st}", sid)

            xy = _world_xy(marks, mk, c.get("dx", 0.0), c.get("dy", 0.0)) if mk in marks else None
            sc_val = float(c.get("scale", 1.0))
            if xy is not None:
                char_coords.append((n, xy, sc_val, mk))

            # Cinematic check 6 & 7: Movement distance vs shot duration & action overflow
            all_acts = [(0.0, act0, c)]
            for ch in c.get("changes", []):
                any_changes = True
                for k in ch:
                    if k not in CHANGE_KEYS:
                        add_err(f"{Q} change has unknown key {k!r}", sid)
                if "at" not in ch:
                    add_err(f"{Q} change without 'at'", sid)
                if "pose" in ch and ch["pose"] not in V.POSES:
                    add_err(f"{Q} change pose {ch['pose']!r} unknown", sid)
                if "face" in ch and ch["face"] not in V.FACES:
                    add_err(f"{Q} change face {ch['face']!r} unknown", sid)
                if "action" in ch:
                    if ch["action"] not in V.ACTIONS:
                        add_err(f"{Q} change action {ch['action']!r} unknown", sid)
                    else:
                        if ch["action"] != "idle":
                            any_non_idle = True
                        all_acts.append((float(ch.get("at", 0.0)), ch["action"], ch))
                if ch.get("to") and ch["to"] not in marks:
                    add_err(f"{Q} change walk target {ch['to']!r} not a mark of {st}", sid)
                for p in ch.get("props", []):
                    if p.split(":")[0] not in PROP_KINDS:
                        add_err(f"{Q} change prop {p!r} unknown", sid)
                if isinstance(ch.get("at"), (int, float)) and ch["at"] >= est_dur:
                    add_warn(f"{Q} change at {ch['at']:.2f}s occurs at or after shot end (~{est_dur:.2f}s)",
                             sid, f"Move change 'at' earlier (< {max(0.2, est_dur - 0.5):.1f}s).")

            cur_xy = xy
            for at_t, act_name, act_spec in all_acts:
                if act_name in ("walk_to", "run_to") and cur_xy is not None:
                    d_xy = _dest_xy(marks, cur_xy, act_spec)
                    if d_xy is not None:
                        dist = math.hypot(d_xy[0] - cur_xy[0], d_xy[1] - cur_xy[1])
                        spd = RUN_SPEED if act_name == "run_to" else WALK_SPEED
                        req_t = dist / spd + LOCO_OVERHEAD
                        avail_t = max(0.1, est_dur - at_t)
                        if req_t > avail_t + 0.35:
                            add_warn(
                                f"{Q} {act_name} covers {dist:.1f} studs (~{req_t:.1f}s required) but only {avail_t:.1f}s available in shot",
                                sid,
                                f"Use a closer destination (<= {spd * avail_t:.1f} studs) or switch walk_to -> run_to."
                            )
                        cur_xy = d_xy
                elif act_name in ACTION_DURATIONS and at_t > 0:
                    need = ACTION_DURATIONS[act_name]
                    if at_t + need > est_dur + 0.25:
                        add_warn(
                            f"{Q} action {act_name!r} starting at {at_t:.2f}s needs ~{need:.2f}s and may be cut off at {est_dur:.2f}s",
                            sid,
                            f"Trigger {act_name!r} earlier (at <= {max(0.0, est_dur - need):.2f}s)."
                        )

            # Cinematic check 10 (character scale continuity within the same set)
            if st == prev_set and n in prev_char_scale:
                has_scale_anim = any("scale" in ch for ch in c.get("changes", [])) or act0 in ("pop_in", "poof")
                if abs(sc_val - prev_char_scale[n]) > 0.35 and not has_scale_anim:
                    add_warn(
                        f"{Q} scale jumps from {prev_char_scale[n]} to {sc_val} in the same set without a scale animation",
                        sid, "Keep character scale consistent across consecutive shots in the same set."
                    )
            prev_char_scale[n] = sc_val

        # Cinematic check 2: Character position overlap (R6 rig shoulder clearance)
        for idx_a in range(len(char_coords)):
            n1, xy1, sc1, mk1 = char_coords[idx_a]
            for idx_b in range(idx_a + 1, len(char_coords)):
                n2, xy2, sc2, mk2 = char_coords[idx_b]
                dist = math.hypot(xy1[0] - xy2[0], xy1[1] - xy2[1])
                min_sep = R6_MIN_SEPARATION * min(sc1, sc2)
                if dist < min_sep - 0.05:
                    add_warn(
                        f"{P} {n1} and {n2} are {dist:.2f} studs apart (< {min_sep:.1f}s R6 clearance) and may overlap",
                        sid,
                        f"Add dx/dy offsets on {n1} and {n2} so they are at least {min_sep:.1f} studs apart."
                    )

        # Cinematic check 3: Idle character when narration describes movement
        words_set = set(low)
        matched_verbs = sorted(words_set & MOVEMENT_VERBS)
        if matched_verbs and names and not any_non_idle and not any_changes:
            add_warn(
                f"{P} narration describes action ({', '.join(matched_verbs)}) but all characters are idle with no changes",
                sid,
                "Assign a purposeful action (walk_to, run_to, jump, look_around, surprise_hop) or timed changes."
            )

        # Cinematic check 8: Lack of meaningful visual development
        has_fx = bool(s.get("fx"))
        has_dyn_place = any("pop_at" in pl or "poof_at" in pl for pl in s.get("place", []))
        if est_dur >= 3.5 and c_move == "static" and not any_non_idle and not any_changes and not has_fx and not has_dyn_place:
            add_warn(
                f"{P} static shot (~{est_dur:.1f}s) has no character action, changes, or camera motion",
                sid,
                "Add a camera move (push_in, orbit_left/right) and a character action or mid-shot expression change."
            )

        # Cinematic check 10: Set / dressing continuity
        if st == prev_set and prev_dressing and dressing != prev_dressing:
            time_words = {"night", "morning", "evening", "sunset", "later", "afternoon", "day", "hours"}
            if not (words_set & time_words) and s.get("transition", "cut") == "cut":
                add_warn(
                    f"{P} dressing changes from {prev_dressing!r} to {dressing!r} in {st!r} on a hard cut without a time cue",
                    sid,
                    "Keep dressing consistent within the same scene or use a 'whip'/'flash' transition."
                )
        prev_set = st
        prev_dressing = dressing

    th = d.get("thumbnail", {})
    if th and th.get("shot") not in ids:
        add_err(f"thumbnail.shot {th.get('shot')!r} is not a shot id")
    if shots and len(shots) < 6:
        add_warn(f"only {len(shots)} shots - short videos still need a cut every 1.5-3 s")

    return {"errors": errs, "warnings": warns, "shots": per_shot}


def validate(ep_dir):
    res = validate_detailed(ep_dir)
    return res["errors"], res["warnings"]


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Validate an episode's shots.json against vocabulary and cinematic QA rules.")
    ap.add_argument("episode_dir", help="Path to the episode folder (e.g. episodes/wi_3am_monster)")
    ap.add_argument("--json", action="store_true", help="Print detailed per-shot JSON report")
    a = ap.parse_args()
    detail = validate_detailed(a.episode_dir)
    if a.json:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
    else:
        for x in detail["warnings"]:
            print("WARN ", x)
        for x in detail["errors"]:
            print("ERROR", x)
        print(f"{len(detail['errors'])} error(s), {len(detail['warnings'])} warning(s)")
    sys.exit(1 if detail["errors"] else 0)
