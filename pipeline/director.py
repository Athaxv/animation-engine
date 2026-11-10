"""
Cinematic Director Agent: transforms an episode's story + shots.json (+ timing.json)
into a rich, validated intermediate storyboard.json (and optionally compiles to shots.json).

    python pipeline/director.py runs/pilot/wi_sounds_from_future --llm --provider gemini --compile
    python pipeline/director.py episodes/<ep> --provider deterministic --compile

Providers:
  gemini         Official Google Gen AI SDK (google-genai), reads GEMINI_API_KEY and GEMINI_MODEL
                 (default: gemini-3.8-flash). Never silently falls back to deterministic unless
                 --fallback-deterministic is explicitly passed.
  openai         OpenAI Chat Completions API via OPENAI_API_KEY.
  deterministic  Built-in rule-based & timing-aware Cinematic Director engine.
"""
import argparse, datetime, json, math, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocab as V       # noqa: E402
import validate as VA   # noqa: E402
import compiler as CO   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
FALLBACK_GEMINI_MODELS = ("gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.0-flash")

# Verb-to-action mapping (only verified actions from vocab.ACTIONS)
ACTION_CUES = [
    ({"run", "runs", "ran", "running", "sprint", "sprints", "sprinted", "rush", "rushed", "burst", "bolted", "escape", "escaped"}, "run_to"),
    ({"jump", "jumps", "jumped", "leap", "leapt"}, "jump"),
    ({"walk", "walks", "walked", "walking", "step", "steps", "stepped", "enter", "entered", "arrive", "arrives", "arrived", "pulled", "pull"}, "walk_to"),
    ({"collapse", "collapsed", "faint", "fainted"}, "fall_back"),
    ({"cry", "cries", "crying", "sob", "sobbing"}, "cry"),
    ({"laugh", "laughs", "laughing", "giggle", "giggling"}, "laugh"),
    ({"celebrate", "celebrates", "cheered"}, "celebrate"),
    ({"shiver", "shivers", "tremble", "terrified", "scared", "louder"}, "shiver"),
    ({"froze", "shocked", "gasped", "suddenly", "bolted"}, "surprise_hop"),
    ({"look", "looked", "zoom", "zoomed", "read", "noticed", "strange", "search", "heard", "hearing"}, "look_around"),
    ({"warn", "warned", "told", "explain", "explained", "asked", "said", "say"}, "gestures"),
    ({"wave", "waves", "waved"}, "wave"),
    ({"nod", "nods", "nodded", "agreed"}, "nod"),
]

WORLD_RULE_CUES = {"world", "town", "everyone", "people", "born", "nobody", "rule", "law", "every"}


def _read_config_var(name, default=""):
    """
    Read configuration variable `name` without ever printing secret values:
      1. Process environment (os.environ)
      2. Project .env file (ROOT / '.env')
      3. Windows User / Machine Environment Registry (on win32)
    """
    val = os.environ.get(name, "").strip()
    if val:
        return val
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            if k.strip() == name:
                v_clean = v.strip().strip('"').strip("'")
                if v_clean:
                    return v_clean
    if sys.platform == "win32":
        try:
            import winreg
            for hive, subkey in (
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as reg_k:
                        v, _ = winreg.QueryValueEx(reg_k, name)
                        if v and str(v).strip():
                            return str(v).strip()
                except OSError:
                    pass
        except Exception:
            pass
    return default


def _sanitize_error(msg):
    """Scrub any API keys or bearer tokens from error messages before logging or saving."""
    s = str(msg)
    s = re.sub(r"AIza[0-9A-Za-z\-_]{20,}", "AIza***REDACTED***", s)
    s = re.sub(r"sk-[0-9A-Za-z\-_]{15,}", "sk-***REDACTED***", s)
    s = re.sub(r"key=[0-9A-Za-z\-_]{15,}", "key=***REDACTED***", s)
    return s


def _load_timing(ep):
    tf = ep / "timing.json"
    if tf.exists():
        try:
            td = json.loads(tf.read_text(encoding="utf-8"))
            return {s["id"]: s for s in td.get("shots", []) if "id" in s}
        except Exception:
            pass
    return {}


def _infer_action_from_text(text):
    words = set(re.sub(r"[^\w' ]", "", text.lower()).split())
    for trigger_set, act in ACTION_CUES:
        if words & trigger_set:
            return act
    return None


def _reachable_dest(st, start_mark, start_dx, start_dy, marks, max_dist, multi_cast=False):
    """Pick a valid destination mark or (to_dx, to_dy) in `st` within `max_dist` studs."""
    step = round(min(max(1.5, max_dist * 0.45), 2.4), 2)
    if multi_cast:
        return {"to": start_mark, "to_dx": round(start_dx, 2), "to_dy": round(start_dy - step, 2)}

    p0 = VA._world_xy(marks, start_mark, start_dx, start_dy)
    if p0 is None:
        return {"to": start_mark, "to_dx": round(start_dx + step, 2), "to_dy": round(start_dy, 2)}

    best = None
    for m_name, m_info in marks.items():
        if m_name.startswith("cam_") or m_name == start_mark or "seat" in m_info:
            continue
        pm = (float(m_info["pos"][0]), float(m_info["pos"][1]))
        dist = math.hypot(pm[0] - p0[0], pm[1] - p0[1])
        if 1.5 <= dist <= max_dist:
            if best is None or abs(dist - max_dist * 0.65) < abs(best[0] - max_dist * 0.65):
                best = (dist, m_name)
    if best:
        return {"to": best[1]}

    dir_x = 1.0 if p0[0] <= 0 else -1.0
    return {"to": start_mark, "to_dx": round(start_dx + dir_x * step, 2), "to_dy": round(start_dy, 2)}


def _deoverlap_positions(loc, chars, pos_map, act_map, marks):
    """Ensure every pair of characters in the shot has >= R6_MIN_SEPARATION studs of XY clearance."""
    if len(chars) < 2:
        return
    for _pass in range(6):
        moved = False
        coords = []
        for n in chars:
            p = pos_map[n]
            mk = p.get("mark", "center")
            dx = float(p.get("dx", 0.0))
            dy = float(p.get("dy", 0.0))
            sc = float(act_map.get(n, {}).get("scale", 1.0))
            xy = VA._world_xy(marks, mk, dx, dy) or (dx, dy)
            coords.append([n, mk, dx, dy, sc, xy[0], xy[1]])

        coords.sort(key=lambda item: (item[5], item[0]))
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                a, b = coords[i], coords[j]
                dist = math.hypot(a[5] - b[5], a[6] - b[6])
                min_sep = (VA.R6_MIN_SEPARATION + 0.15) * min(a[4], b[4])
                if dist < min_sep:
                    need = (min_sep - dist) * 0.55 + 0.08
                    a[2] = round(a[2] - need, 2)
                    b[2] = round(b[2] + need, 2)
                    pos_map[a[0]]["dx"] = a[2]
                    pos_map[b[0]]["dx"] = b[2]
                    moved = True
        if not moved:
            break


def _populate_world_building(sb, cat, custom_chars, idx):
    """Add background life on sparse public sets when narration introduces a world rule."""
    loc = sb["location"]
    chars = sb["characters"]
    words = set(re.sub(r"[^\w' ]", "", sb["narration"].lower()).split())
    if loc not in ("street", "classroom"):
        return
    if len(chars) >= 3 or not (words & WORLD_RULE_CUES or idx == 0):
        return

    candidates = ["Max", "Mom", "Officer", "Noob", "Lily", "Dad"]
    marks = cat["sets"][loc]["marks"]
    if loc == "street":
        bg_slots = [
            ("sidewalk_a", -2.2, 1.0, "relaxed", "smile"),
            ("sidewalk_c", 2.4, 1.0, "arms_crossed", "neutral"),
        ]
    else:
        bg_slots = [
            ("desk_1", 0.0, 0.0, "sit", "neutral"),
            ("desk_3", 0.0, 0.0, "sit", "smile"),
        ]

    focal = chars[0] if chars else "camera"
    slot_idx = 0
    for cand in candidates:
        if len(chars) >= 3 or slot_idx >= len(bg_slots):
            break
        if cand in chars:
            continue
        mk, dx, dy, pose, face = bg_slots[slot_idx]
        if mk not in marks:
            continue
        slot_idx += 1
        chars.append(cand)
        sb["character_positions"][cand] = {"mark": mk, "dx": dx, "dy": dy, "facing": focal}
        sb["character_actions"][cand] = {"pose": pose, "action": "idle"}
        sb["character_expressions"][cand] = face


def direct_storyboard(shots_data, timing_map=None, world_build=True):
    """
    Apply deterministic cinematic direction rules to produce a validated storyboard.json dict.
    """
    timing_map = timing_map or {}
    cat = V.catalog()
    sb_data = CO.shots_to_storyboard(shots_data)
    sb_shots = sb_data["storyboard"]
    custom_chars = sb_data.get("metadata", {}).get("characters", {})

    prev_cam_sig = None
    shot_history = []
    prev_set = None
    prev_scale = {}

    for idx, sb in enumerate(sb_shots):
        sid = sb["id"]
        loc = sb["location"]
        marks = cat["sets"][loc]["marks"]
        narration = sb.get("narration", "")
        nw = len(narration.split())
        t_info = timing_map.get(sid)
        dur = float(t_info["duration"]) if t_info else (nw / 2.8 + float(sb.get("hold", 0.0)) if nw else 2.5)

        if world_build:
            _populate_world_building(sb, cat, custom_chars, idx)

        chars = sb["characters"]
        pos_map = sb["character_positions"]
        act_map = sb["character_actions"]
        exp_map = sb["character_expressions"]
        chg_map = sb["character_changes"]
        hand_map = sb.get("props", {}).get("hand", {})

        inferred_act = _infer_action_from_text(narration)
        any_active = any(act_map.get(n, {}).get("action", "idle") != "idle" for n in chars) or bool(chg_map)

        if not any_active and chars and inferred_act:
            primary = sb.get("camera_target") if sb.get("camera_target") in chars else chars[0]
            a_info = act_map.setdefault(primary, {"pose": "relaxed", "action": "idle"})
            if inferred_act in ("walk_to", "run_to") and a_info.get("pose") not in ("sit", "lie"):
                spd = VA.RUN_SPEED if inferred_act == "run_to" else VA.WALK_SPEED
                max_d = max(2.0, (dur - VA.LOCO_OVERHEAD - 0.3) * spd)
                for cn in (chars if len(chars) == 2 else [primary]):
                    ca = act_map.setdefault(cn, {"pose": "relaxed", "action": "idle"})
                    cp = pos_map.setdefault(cn, {"mark": "center", "facing": "camera"})
                    if ca.get("pose") not in ("sit", "lie"):
                        dest = _reachable_dest(
                            loc, cp.get("mark", "center"), float(cp.get("dx", 0.0)), float(cp.get("dy", 0.0)),
                            marks, max_d, multi_cast=(len(chars) > 1)
                        )
                        ca["action"] = inferred_act
                        ca.update(dest)
            elif a_info.get("pose") not in ("sit", "lie"):
                a_info["action"] = inferred_act

        for n in chars:
            a_info = act_map.get(n, {})
            p_info = pos_map.get(n, {})
            mk = p_info.get("mark", "center")
            dx = float(p_info.get("dx", 0.0))
            dy = float(p_info.get("dy", 0.0))
            xy0 = VA._world_xy(marks, mk, dx, dy)
            act_name = a_info.get("action", "idle")
            if act_name in ("walk_to", "run_to") and xy0 is not None:
                d_xy = VA._dest_xy(marks, xy0, a_info)
                if d_xy is not None:
                    dist = math.hypot(d_xy[0] - xy0[0], d_xy[1] - xy0[1])
                    spd = VA.RUN_SPEED if act_name == "run_to" else VA.WALK_SPEED
                    max_d = max(1.8, (dur - VA.LOCO_OVERHEAD - 0.2) * spd)
                    if dist > max_d:
                        ratio = max_d / dist
                        a_info.pop("to_offset", None)
                        a_info["to"] = mk
                        a_info["to_dx"] = round(dx + (d_xy[0] - xy0[0]) * ratio, 2)
                        a_info["to_dy"] = round(dy + (d_xy[1] - xy0[1]) * ratio, 2)

            if hand_map.get(n) and a_info.get("pose") in ("stand", "relaxed"):
                a_info["pose"] = "hold"

            if a_info.get("pose") == "sit" and "seat" not in marks.get(mk, {}):
                a_info["pose"] = "sad" if exp_map.get(n) in ("sad", "sleep", "worried", "cry") else "relaxed"

            sc_val = float(a_info.get("scale", 1.0))
            if loc == prev_set and n in prev_scale and abs(sc_val - prev_scale[n]) > 0.35:
                if not any("scale" in ch for ch in chg_map.get(n, [])) and act_name not in ("pop_in", "poof"):
                    a_info["scale"] = prev_scale[n]
            prev_scale[n] = float(a_info.get("scale", 1.0))

            if n in chg_map:
                valid_chgs = []
                for ch in chg_map[n]:
                    at_t = float(ch.get("at", 0.5))
                    ch_act = ch.get("action")
                    need = VA.ACTION_DURATIONS.get(ch_act, 0.25) if ch_act else 0.25
                    if at_t + need > dur - 0.15:
                        at_t = round(max(0.25, dur - need - 0.2), 2)
                        ch = dict(ch)
                        ch["at"] = at_t
                    valid_chgs.append(ch)
                chg_map[n] = valid_chgs

        if dur >= 3.2 and chars and not chg_map:
            primary = sb.get("camera_target") if sb.get("camera_target") in chars else chars[0]
            cur_face = exp_map.get(primary, "smile")
            cur_act = act_map.get(primary, {}).get("action", "idle")
            if cur_act == "idle":
                follow_act = "nod" if cur_face in ("smile", "grin", "confident") else "look_around"
                chg_map[primary] = [{"at": round(dur * 0.48, 2), "action": follow_act}]

        _deoverlap_positions(loc, chars, pos_map, act_map, marks)

        c_shot = sb.get("camera_framing", "medium")
        c_angle = sb.get("camera_angle", "eye")
        c_move = sb.get("camera_movement", "static")
        tgt = sb.get("camera_target") or (chars[0] if chars else "center")

        if c_shot in ("two_shot", "over_shoulder") and len(chars) < 2:
            c_shot = "medium"

        if tgt in chars:
            tgt_props = list(hand_map.get(tgt, [])) + [p for ch in chg_map.get(tgt, []) for p in ch.get("props", [])]
            if tgt_props and c_shot in ("close_up", "extreme_close_up", "medium_close"):
                c_shot = "two_shot" if len(chars) == 2 else "medium"

        if len(shot_history) >= 2 and shot_history[-1] == c_shot and shot_history[-2] == c_shot:
            tgt_has_props = tgt in chars and bool(
                list(hand_map.get(tgt, [])) + [p for ch in chg_map.get(tgt, []) for p in ch.get("props", [])]
            )
            if len(chars) >= 3:
                c_shot = "group" if c_shot != "group" else "wide"
            elif len(chars) == 2:
                if c_shot == "two_shot":
                    c_shot = "group"
                else:
                    c_shot = "two_shot"
            else:
                if tgt_has_props:
                    c_shot = "wide" if c_shot == "medium" else "medium"
                else:
                    c_shot = "medium_close" if c_shot == "medium" else ("medium" if c_shot == "close_up" else "close_up")

        if prev_cam_sig == (c_shot, c_angle, c_move):
            alt_moves = ["push_in", "orbit_right", "orbit_left", "pull_out"]
            for m_cand in alt_moves:
                if m_cand != c_move:
                    c_move = m_cand
                    break
            if prev_cam_sig == (c_shot, c_angle, c_move):
                c_angle = "low" if c_angle == "eye" else "eye"

        if dur >= 3.2 and c_move == "static":
            c_move = "push_in" if idx % 2 == 0 else "orbit_right"

        sb["camera_framing"] = c_shot
        sb["camera_angle"] = c_angle
        sb["camera_movement"] = c_move
        sb["camera_target"] = tgt

        cast_summary = ", ".join(
            f"{n}@{pos_map[n].get('mark')}({act_map[n].get('pose')}/{exp_map[n]}/{act_map[n].get('action')})"
            for n in chars
        )
        sb["visual_goal"] = f"{loc} ({sb.get('dressing', 'day')}) [{c_shot}/{c_angle}/{c_move} -> {tgt}]: {cast_summary}"

        prev_cam_sig = (c_shot, c_angle, c_move)
        shot_history.append(c_shot)
        prev_set = loc

    return sb_data


def _build_director_prompt(sb_data, timing_map):
    """Build the comprehensive Cinematic Animation Director prompt with full catalog & timing context."""
    cat = V.catalog()
    shot_timings = {
        sid: {"duration_seconds": round(float(t.get("duration", 2.5)), 2), "start_seconds": round(float(t.get("start", 0.0)), 2)}
        for sid, t in (timing_map or {}).items()
    }
    vocab_spec = {
        "sets": {
            s_name: {
                "dressings": s_info["dressings"],
                "marks": {m: v for m, v in s_info["marks"].items() if not m.startswith("cam_")},
            }
            for s_name, s_info in cat["sets"].items()
        },
        "set_staging_notes": {
            "kitchen": "Dining table spans x in [-8.5, 0.5]; Couch spans x in [5.5, 14.5]. Place standing characters in the open corridor on mark 'center' with dx in [-2.6, 0.2] and dy in [-2.0, -1.0] so furniture never blocks the camera.",
            "classroom": "Front row of student desks is desk_1 (x=-10, y=-0.8), desk_2 (x=0, y=-0.8), desk_3 (x=10, y=-0.8). Prefer desk_1..desk_3 over desk_4..desk_9 so push_in cameras stay well inside the front wall (y=-15.0) and show the green chalkboard behind the students.",
            "bedroom": "Marks: bed (lie/sleep), bed_sit (seat), bedside, center (open floor), desk, door, window. For night scenes (s15-s19), stage characters on 'center' or 'bedside' with facing='camera' or toward each other and use light props (flashlight, alarm_clock) for readability.",
            "street": "Marks: sidewalk_a (x=-6), sidewalk_b (x=0), sidewalk_c (x=6), road (y=-8), lawn (y=10.5), house_door. Keep interacting characters within 2.2..3.5 studs of each other on the same mark using dx offsets.",
        },
        "characters_allowed": sorted(set(cat["characters"]) | set(sb_data.get("metadata", {}).get("characters", {}))),
        "poses": V.POSES,
        "faces": V.FACES,
        "actions": V.ACTIONS,
        "locomotion_speeds_studs_per_sec": {"walk_to": 6.0, "run_to": 14.0, "walk_in": 6.0, "walk_out": 6.0, "run_out": 14.0},
        "camera_framing": V.CAMERA_SHOTS,
        "camera_angle": V.CAMERA_ANGLES,
        "camera_movement": V.CAMERA_MOVES,
        "transitions": V.TRANSITIONS,
        "fx": ["shake", "tint", "punch", "flash", "freeze"],
        "props": V.PROP_KINDS,
        "sfx": V.sfx_names(),
        "r6_min_character_separation_studs": 2.15,
    }

    return (
        "You are an expert Roblox Cinematic Animation Director and Visual Storyteller.\n"
        "Transform the input storyboard JSON into an engaging, visually dynamic, cinema-grade storyboard "
        "that strictly obeys the engine vocabulary and preserves every shot's 'id', 'speaker', 'narration', and 'metadata'.\n\n"
        "### MANDATORY CREATIVE DIRECTION RULES:\n"
        "1. DEMONSTRATE FUTURE-SOUND PREMONITIONS VISUALLY (s01-s04):\n"
        "   - Show anticipation -> character reaction BEFORE the event -> the event occurring afterward (via timed 'character_changes', 'pop_at'/'poof_at' placed props, or 'walk_in' arrivals) -> bystander reactions.\n"
        "   - Do not rely solely on hand-to-ear poses; use head turns ('look_around'), pointing ('point'/'point_side'), jumping in shock ('surprise_hop'), catching/holding objects ('pose': 'hold' + 'props'), and characters walking in ('walk_in').\n"
        "2. PURPOSEFUL CHARACTER ACTING & REAL LOCOMOTION:\n"
        "   - Never leave characters 'idle' when the narration describes movement or strong emotion.\n"
        "   - When narration describes walking, entering, running, or rushing (e.g. s04, s07, s08, s12, s15, s19, s22), use real root locomotion ('walk_to', 'run_to', 'walk_in') with reachable destinations within the shot duration, paired with timed 'character_changes' (pose, face, action, props).\n"
        "3. DELIBERATE SHOT VARIETY (ESPECIALLY s10-s18):\n"
        "   - Avoid consecutive close-up-heavy sequences. Mix 'medium', 'two_shot', 'group', 'wide', and 'medium_close' with 'track', 'orbit_left', 'orbit_right', 'push_in', 'pull_out', 'whip_in', and 'crash_zoom'.\n"
        "   - Reserve tight 'close_up' shots for peak emotional beats (such as s11 and s18).\n"
        "   - Never repeat the exact same (camera_framing, camera_angle, camera_movement) in consecutive shots, and never use 3 identical camera_framing values in a row.\n"
        "   - Never use 'close_up' or 'medium_close' on a target character holding a prop (use 'medium' or 'two_shot' so the prop is not cropped).\n"
        "4. NIGHT-SCENE READABILITY (s15-s19):\n"
        "   - Stage characters in the open 'center' or 'bedside' marks facing the camera or 3/4 toward each other so the camera-following key light illuminates their faces clearly against the dark bedroom.\n\n"
        f"### ENGINE VOCABULARY & STAGING CONSTRAINTS:\n{json.dumps(vocab_spec, indent=2)}\n\n"
        f"### EXACT SHOT TIMINGS (SECONDS):\n{json.dumps(shot_timings, indent=2)}\n\n"
        f"### INPUT STORYBOARD JSON:\n{json.dumps(sb_data, indent=2)}\n\n"
        "Return ONLY a valid JSON object matching the exact root schema: "
        '{"schema_version": "1.0", "episode": "...", "metadata": {...}, "storyboard": [...]}.'
    )


def _classify_gemini_error(exc):
    """Classify a google-genai exception into a structured, sanitized error record."""
    msg = _sanitize_error(exc)
    low = msg.lower()
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 401 or "api_key_invalid" in low or "unauthenticated" in low or "invalid api key" in low:
        err_type = "authentication_error"
        transient = False
    elif code == 403 or "permission_denied" in low or "forbidden" in low:
        err_type = "permission_error"
        transient = False
    elif code == 404 or "not_found" in low or "not found" in low or "is not supported" in low:
        err_type = "unsupported_model_error"
        transient = False
    elif code == 429 or "resource_exhausted" in low or "quota" in low or "rate limit" in low:
        err_type = "rate_limit_or_quota_error"
        transient = True
    elif code in (500, 502, 503, 504) or "unavailable" in low or "deadline" in low or "connection" in low or "timeout" in low:
        err_type = "network_or_transient_error"
        transient = True
    else:
        err_type = "api_error"
        transient = False
    return {
        "error_type": err_type,
        "status_code": code,
        "transient": transient,
        "message": msg[:500],
    }


def _call_gemini_director(sb_data, timing_map, model_name=None, allow_model_fallback=True):
    """
    Execute the Cinematic Director using the official Google Gen AI SDK (`google-genai`).
    Never silently falls back to deterministic direction.
    Returns (refined_sb_data, exec_report).
    """
    api_key = _read_config_var("GEMINI_API_KEY")
    req_model = model_name or _read_config_var("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    exec_report = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "provider": "gemini",
        "sdk": "google-genai",
        "requested_model": req_model,
        "actual_model_used": None,
        "api_key_configured": bool(api_key),
        "api_call_attempted": False,
        "api_call_succeeded": False,
        "response_parsed": False,
        "validation_passed": False,
        "revision_passes_used": 0,
        "fallback_used": False,
        "token_usage": None,
        "api_errors": [],
    }

    if not api_key:
        setup_msg = (
            "GEMINI_API_KEY is not configured.\n"
            "Setup instructions:\n"
            f"  1. Open {ROOT / '.env'} and add a line: GEMINI_API_KEY=<your_google_gemini_api_key>\n"
            "     (or set $env:GEMINI_API_KEY in PowerShell / Windows User Environment Variables).\n"
            f"  2. Optionally set GEMINI_MODEL={DEFAULT_GEMINI_MODEL} and DIRECTOR_PROVIDER=gemini.\n"
            "  3. Re-run: python pipeline/director.py <episode_dir> --llm --provider gemini --compile"
        )
        exec_report["api_errors"].append({
            "error_type": "missing_api_key",
            "status_code": None,
            "transient": False,
            "message": setup_msg,
        })
        return None, exec_report

    try:
        from google import genai
        from google.genai import types
        exec_report["sdk_version"] = getattr(genai, "__version__", "installed")
    except ImportError as e:
        exec_report["api_errors"].append({
            "error_type": "missing_sdk",
            "status_code": None,
            "transient": False,
            "message": f"google-genai SDK is not installed ({e}). Run: pip install google-genai",
        })
        return None, exec_report

    client = genai.Client(api_key=api_key)
    models_to_try = [req_model]
    if allow_model_fallback:
        for fb_m in FALLBACK_GEMINI_MODELS:
            if fb_m not in models_to_try:
                models_to_try.append(fb_m)

    base_prompt = _build_director_prompt(sb_data, timing_map)
    prompt = base_prompt

    for m_idx, cur_model in enumerate(models_to_try):
        # Up to 2 creative/validation revision passes
        for rev_pass in range(3):
            # Bounded retry for transient network / 429 errors (max 2 retries)
            resp = None
            for attempt in range(3):
                exec_report["api_call_attempted"] = True
                try:
                    resp = client.models.generate_content(
                        model=cur_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.35,
                        ),
                    )
                    exec_report["api_call_succeeded"] = True
                    exec_report["actual_model_used"] = cur_model
                    break
                except Exception as exc:
                    err_info = _classify_gemini_error(exc)
                    err_info["model_attempted"] = cur_model
                    err_info["attempt"] = attempt + 1
                    exec_report["api_errors"].append(err_info)
                    if err_info["error_type"] == "unsupported_model_error":
                        print(f"[director/gemini] Model {cur_model!r} returned 404/unsupported.", flush=True)
                        break
                    if err_info["transient"] and attempt < 2:
                        wait_s = 2.0 * (attempt + 1)
                        print(f"[director/gemini] Transient {err_info['error_type']} on {cur_model!r}; retrying in {wait_s}s...", flush=True)
                        time.sleep(wait_s)
                        continue
                    if err_info["transient"] and allow_model_fallback and m_idx + 1 < len(models_to_try):
                        print(f"[director/gemini] Model {cur_model!r} unavailable after 3 attempts; trying next Gemini model...", flush=True)
                        break
                    return None, exec_report

            if resp is None:
                # Model was unsupported (404); try next model in models_to_try if allowed
                break

            # Record token usage metadata when available
            um = getattr(resp, "usage_metadata", None)
            if um is not None:
                exec_report["token_usage"] = {
                    "prompt_token_count": getattr(um, "prompt_token_count", None),
                    "candidates_token_count": getattr(um, "candidates_token_count", None),
                    "total_token_count": getattr(um, "total_token_count", None),
                }

            raw_text = (getattr(resp, "text", None) or "").strip()
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.DOTALL).strip()

            try:
                candidate = json.loads(raw_text)
                exec_report["response_parsed"] = True
            except Exception as pe:
                exec_report["api_errors"].append({
                    "error_type": "malformed_json_output",
                    "status_code": None,
                    "transient": False,
                    "message": f"Failed to parse JSON from Gemini response: {pe}",
                })
                if rev_pass < 2:
                    exec_report["revision_passes_used"] += 1
                    prompt = base_prompt + f"\n\nYour previous output was not valid JSON ({pe}). Return ONLY a valid JSON object."
                    continue
                return None, exec_report

            # Preserve exact metadata, shot IDs, speakers, and narration text before validating
            orig_by_id = {s["id"]: s for s in sb_data["storyboard"]}
            if isinstance(candidate, dict) and isinstance(candidate.get("storyboard"), list):
                candidate["episode"] = sb_data.get("episode")
                candidate["metadata"] = sb_data.get("metadata", {})
                for s_cand in candidate["storyboard"]:
                    if isinstance(s_cand, dict) and s_cand.get("id") in orig_by_id:
                        o_shot = orig_by_id[s_cand["id"]]
                        s_cand["narration"] = o_shot["narration"]
                        s_cand["speaker"] = o_shot["speaker"]
                        if "hold" in o_shot:
                            s_cand["hold"] = o_shot["hold"]

            val_errs = CO.validate_storyboard(candidate, sb_data.get("episode"))
            if not val_errs and len(candidate.get("storyboard", [])) == len(sb_data["storyboard"]):
                exec_report["validation_passed"] = True
                return candidate, exec_report

            err_summary = val_errs or [f"Expected {len(sb_data['storyboard'])} shots, got {len(candidate.get('storyboard', []))}"]
            exec_report["api_errors"].append({
                "error_type": "schema_validation_error",
                "status_code": None,
                "transient": False,
                "message": f"Pass {rev_pass + 1} validation errors: {err_summary[:10]}",
            })
            if rev_pass < 2:
                exec_report["revision_passes_used"] += 1
                prompt = (
                    base_prompt
                    + f"\n\nFix these exact storyboard validation errors from your previous response:\n{json.dumps(err_summary)}\n"
                    + "Remember: use ONLY valid marks, poses, faces, actions, props, and sfx from the provided vocabulary."
                )
            else:
                return None, exec_report

    return None, exec_report


def _call_openai_director(sb_data, timing_map, model_name="gpt-4o-mini"):
    """Execute the Cinematic Director using OpenAI Chat Completions API without silent fallback."""
    api_key = _read_config_var("OPENAI_API_KEY")
    exec_report = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "provider": "openai",
        "requested_model": model_name,
        "actual_model_used": None,
        "api_key_configured": bool(api_key),
        "api_call_attempted": False,
        "api_call_succeeded": False,
        "response_parsed": False,
        "validation_passed": False,
        "revision_passes_used": 0,
        "fallback_used": False,
        "token_usage": None,
        "api_errors": [],
    }
    if not api_key:
        exec_report["api_errors"].append({
            "error_type": "missing_api_key",
            "status_code": None,
            "transient": False,
            "message": "OPENAI_API_KEY is not configured in environment or .env.",
        })
        return None, exec_report

    prompt = _build_director_prompt(sb_data, timing_map)
    for rev_pass in range(2):
        exec_report["api_call_attempted"] = True
        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({
                    "model": model_name,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            exec_report["api_call_succeeded"] = True
            exec_report["actual_model_used"] = body.get("model", model_name)
            if "usage" in body:
                exec_report["token_usage"] = body["usage"]
            candidate = json.loads(body["choices"][0]["message"]["content"])
            exec_report["response_parsed"] = True
            errs = CO.validate_storyboard(candidate, sb_data.get("episode"))
            if not errs:
                exec_report["validation_passed"] = True
                return candidate, exec_report
            exec_report["revision_passes_used"] += 1
            prompt += f"\nFix these validation errors: {errs}"
        except urllib.error.HTTPError as e:
            err_body = _sanitize_error(e.read().decode("utf-8", "replace")[:400])
            exec_report["api_errors"].append({
                "error_type": "http_error",
                "status_code": e.code,
                "transient": e.code in (429, 500, 502, 503, 504),
                "message": f"OpenAI HTTP {e.code}: {err_body}",
            })
            break
        except Exception as e:
            exec_report["api_errors"].append({
                "error_type": type(e).__name__,
                "status_code": None,
                "transient": False,
                "message": _sanitize_error(e),
            })
            break
    return None, exec_report


def run_director(ep_dir, compile_out=False, use_llm=False, provider=None, model=None,
                 fallback_deterministic=False, world_build=True):
    ep = Path(ep_dir).resolve()
    shots_file = ep / "shots.json"
    if not shots_file.exists():
        raise FileNotFoundError(f"Missing {shots_file}")

    shots_data = json.loads(shots_file.read_text(encoding="utf-8"))
    timing_map = _load_timing(ep)

    resolved_provider = (provider or _read_config_var("DIRECTOR_PROVIDER") or ("gemini" if use_llm else "deterministic")).lower()
    if use_llm and resolved_provider == "deterministic":
        resolved_provider = "gemini"

    if resolved_provider in ("gemini", "openai"):
        # Prepare baseline structured storyboard for the LLM to refine
        seed_sb = CO.shots_to_storyboard(shots_data)
        if resolved_provider == "gemini":
            llm_sb, exec_report = _call_gemini_director(seed_sb, timing_map, model_name=model)
        else:
            llm_sb, exec_report = _call_openai_director(seed_sb, timing_map, model_name=model or "gpt-4o-mini")

        exec_file = ep / "director_execution.json"
        if llm_sb is None:
            exec_report["fallback_used"] = bool(fallback_deterministic)
            exec_file.write_text(json.dumps(exec_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            last_err = exec_report["api_errors"][-1]["message"] if exec_report["api_errors"] else "Unknown LLM error"
            print(f"ERROR [director/{resolved_provider}]: LLM execution failed:\n{last_err}", flush=True)
            if not fallback_deterministic:
                raise RuntimeError(
                    f"LLM director ({resolved_provider}) failed and silent fallback is disabled. "
                    f"See {exec_file} for details, or pass --fallback-deterministic to explicitly use deterministic mode."
                )
            print("[director] --fallback-deterministic was explicitly requested; running deterministic director.", flush=True)
            sb_data = direct_storyboard(shots_data, timing_map=timing_map, world_build=world_build)
        else:
            # Run deterministic spatial/timing guardrails on the LLM's storyboard to guarantee 0 R6 overlaps & valid marks
            compiled_tmp = CO.compile_storyboard(llm_sb, shots_data)
            sb_data = direct_storyboard(compiled_tmp, timing_map=timing_map, world_build=False)
            # Preserve the LLM's visual_goal descriptions
            llm_goals = {s["id"]: s.get("visual_goal") for s in llm_sb.get("storyboard", []) if "id" in s}
            for s in sb_data["storyboard"]:
                if llm_goals.get(s["id"]):
                    s["visual_goal"] = llm_goals[s["id"]]
            exec_file.write_text(json.dumps(exec_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(
                f"[director/{resolved_provider}] SUCCESS: model={exec_report['actual_model_used']} "
                f"tokens={exec_report.get('token_usage')} revisions={exec_report['revision_passes_used']}",
                flush=True,
            )
    else:
        exec_report = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "provider": "deterministic",
            "requested_model": None,
            "actual_model_used": "deterministic_rules_v2",
            "api_key_configured": False,
            "api_call_attempted": False,
            "api_call_succeeded": False,
            "response_parsed": True,
            "validation_passed": True,
            "revision_passes_used": 0,
            "fallback_used": False,
            "token_usage": None,
            "api_errors": [],
        }
        sb_data = direct_storyboard(shots_data, timing_map=timing_map, world_build=world_build)
        (ep / "director_execution.json").write_text(json.dumps(exec_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    errs = CO.validate_storyboard(sb_data, ep.name)
    if errs:
        raise ValueError(f"Director produced invalid storyboard: {errs}")

    sb_file = ep / "storyboard.json"
    sb_file.write_text(json.dumps(sb_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[director] wrote {sb_file} ({len(sb_data['storyboard'])} shots)")

    if compile_out:
        c_errs, c_warns = CO.compile_episode(ep)
        for w in c_warns:
            print("WARN ", w)
        for e in c_errs:
            print("ERROR", e)
        if c_errs:
            raise RuntimeError(f"Compilation failed with {len(c_errs)} error(s)")
        print(f"[director] compiled {sb_file} -> {shots_file} (0 errors, {len(c_warns)} warnings)")
    return sb_data


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Cinematic Director Agent: generate storyboard.json and optionally compile to shots.json.")
    ap.add_argument("episode_dir", help="Episode folder path (e.g. runs/pilot/wi_sounds_from_future)")
    ap.add_argument("--compile", action="store_true", help="Compile storyboard.json into shots.json after directing")
    ap.add_argument("--llm", action="store_true", help="Require real LLM director execution (no silent deterministic fallback)")
    ap.add_argument("--provider", choices=["gemini", "openai", "deterministic"], default=None,
                    help="Director provider (default: gemini when --llm is set, else deterministic or DIRECTOR_PROVIDER)")
    ap.add_argument("--model", default=None, help=f"LLM model name override (default: GEMINI_MODEL or {DEFAULT_GEMINI_MODEL})")
    ap.add_argument("--fallback-deterministic", action="store_true",
                    help="Explicitly allow falling back to deterministic director if the LLM API call fails")
    ap.add_argument("--no-world-build", action="store_true", help="Do not add extra background characters to sparse public sets")
    a = ap.parse_args()
    try:
        run_director(
            a.episode_dir,
            compile_out=a.compile,
            use_llm=a.llm,
            provider=a.provider,
            model=a.model,
            fallback_deterministic=a.fallback_deterministic,
            world_build=not a.no_world_build,
        )
    except Exception as e:
        sys.exit(f"DIRECTOR FAILED: {e}")


if __name__ == "__main__":
    main()
