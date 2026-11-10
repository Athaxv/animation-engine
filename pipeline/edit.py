"""
Edit step: raw render + voice + music + SFX + captions + hook title + transitions -> final mp4.

    blender -b --factory-startup --python pipeline/edit.py -- <episode_dir> preview|final [--no-music]

Reads shots.json, timing.json, formats/<format>/format.json (caption style, music, title card)
and render/raw_<quality>.mp4. Writes out/<episode>[_nomusic]_<quality>.mp4.
"""
import bpy, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
SFX = ROOT / "public" / "audio" / "sfx"
MUSIC = ROOT / "public" / "audio" / "music"
FONTS = [ROOT / "public" / "fonts" / "caption.ttf", Path(r"C:\Windows\Fonts\seguibl.ttf"), Path(r"C:\Windows\Fonts\ariblk.ttf")]

DEFAULT_FMT = {
    "music": "quirky", "music_volume": 0.12, "voice_volume": 1.0, "sfx_volume": 0.55,
    "captions": {"style": "word", "case": "lower", "size": 118, "y": 0.42, "color": [1, 1, 1, 1],
                 "highlight": [1.0, 0.86, 0.15, 1], "outline": 0.10, "pop": True, "max_words": 3},
    "title_card": {"show": True, "y": 0.83, "size": 74, "seconds": 3.2, "box": [1, 1, 1, 1], "color": [0.05, 0.05, 0.06, 1]},
    "end_card": {"show": False, "text": "PART 2?", "seconds": 1.4},
    "auto_sfx": True,
}
AUTO_SFX = {"surprise_hop": "pop", "jump": "boing", "celebrate": "boing", "fall_back": "thud", "poof": "poof",
            "pop_in": "pop", "spin": "slide_up", "float": "slide_up", "run_to": "cartoon_run", "run_out": "cartoon_run"}
TRANSITION_SFX = {"whip": "whoosh", "glitch": "glitch", "flash": "pop"}


def deep_merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def font():
    for p in FONTS:
        if p.exists():
            return bpy.data.fonts.load(str(p), check_existing=True)
    return None


def find_audio(folder, name):
    """folder/<name>.* (ElevenLabs / user files) wins over folder/synth/<name>.wav (generated)."""
    for d in (folder, folder / "synth"):
        for ext in (".mp3", ".wav", ".ogg", ".flac"):
            p = d / f"{name}{ext}"
            if p.exists():
                return p
    return None


def clean(w):
    return re.sub(r"[^\w']", "", w.lower())


def main(ep_dir, quality="preview", no_music=False):
    ep = Path(ep_dir).resolve()
    data = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    timing = json.loads((ep / "timing.json").read_text(encoding="utf-8"))
    fmt = dict(DEFAULT_FMT)
    fp = ROOT / "formats" / data.get("format", "_") / "format.json"
    if fp.exists():
        fmt = deep_merge(fmt, json.loads(fp.read_text(encoding="utf-8")).get("edit", {}))
    fmt = deep_merge(fmt, data.get("edit", {}))
    fps = data.get("fps", 30)
    F = lambda t: int(round(t * fps)) + 1

    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.name = "Edit"
    sc.view_settings.view_transform = "Standard"
    sc.sequencer_colorspace_settings.name = "sRGB"
    sc.render.fps = fps
    sc.render.resolution_x, sc.render.resolution_y = data.get("resolution", [1080, 1920])
    sc.render.resolution_percentage = 50 if quality == "preview" else 100
    sc.frame_start, sc.frame_end = 1, timing["total_frames"]
    se = sc.sequence_editor_create()
    S = se.strips
    fnt = font()

    # ---- picture
    raw = ep / "render" / f"raw_{quality}.mp4"
    mv = S.new_movie("raw", str(raw), 1, 1, fit_method='FIT')
    mv.frame_final_end = sc.frame_end + 1

    # ---- voice
    vol_voice = fmt["voice_volume"]
    for i, s in enumerate(timing["shots"]):
        if s.get("audio"):
            snd = S.new_sound(f"vo_{s['id']}", str(ep / s["audio"]), 2 + (i % 2), F(s["audio_start"]))
            snd.volume = vol_voice

    # ---- music (looped)
    mood = data.get("music", fmt["music"])
    mp = find_audio(MUSIC, mood) if mood and not no_music else None
    if mp:
        f, k = 1, 0
        while f <= sc.frame_end:
            m = S.new_sound(f"music{k}", str(mp), 4, f)
            m.volume = fmt["music_volume"]
            f = m.frame_final_end; k += 1
        last = m
        last.frame_final_end = min(last.frame_final_end, sc.frame_end + 1)
        # fade out over the last second
        last.volume = fmt["music_volume"]; last.keyframe_insert("volume", frame=max(1, sc.frame_end - fps))
        last.volume = 0.0; last.keyframe_insert("volume", frame=sc.frame_end)

    # ---- sfx: explicit + automatic
    T = {s["id"]: s for s in timing["shots"]}
    events = []           # (frame, name, gain)
    starts = [T[s["id"]]["start_frame"] for s in data["shots"]] + [sc.frame_end + 1]
    for i, shot in enumerate(data["shots"]):
        f0 = starts[i]
        for x in shot.get("sfx", []):
            events.append((f0 + int(round(x.get("at", 0) * fps)), x["name"], x.get("gain", 1.0)))
        if fmt.get("auto_sfx", True):
            for c in shot.get("cast", []):
                acts = [(0.0, c.get("action"))] + [(ch["at"], ch.get("action")) for ch in c.get("changes", []) if ch.get("action")]
                for at, a in acts:
                    if a in AUTO_SFX:
                        events.append((f0 + int(round(at * fps)) + (2 if a == "surprise_hop" else 0), AUTO_SFX[a], 0.8))
            for fx in shot.get("fx", []):
                if fx.get("type") == "shake":
                    events.append((f0 + int(round(fx.get("at", 0) * fps)), "boom", 0.9))
            for pl in shot.get("place", []):
                if "pop_at" in pl:
                    events.append((f0 + int(round(pl["pop_at"] * fps)), "pop", 0.9))
                if "poof_at" in pl:
                    events.append((f0 + int(round(pl["poof_at"] * fps)), "poof", 0.9))
            tr = shot.get("transition", "cut")
            if tr in TRANSITION_SFX and i + 1 < len(data["shots"]):
                events.append((starts[i + 1] - (5 if tr == "whip" else 0), TRANSITION_SFX[tr], 0.8))
    used = {}
    for k, (fr, name, gain) in enumerate(sorted(events)):
        p = find_audio(SFX, name)
        if not p or fr > sc.frame_end:
            continue
        if used.get(name, -99) > fr - 4:           # no machine-gun duplicates
            continue
        used[name] = fr
        s = S.new_sound(f"sfx{k}_{name}", str(p), 5 + (k % 3), max(1, fr))
        s.volume = fmt["sfx_volume"] * gain

    # ---- picture bumps: whip / punch / glitch / zoom-hold on the movie strip
    bumps = []
    for i, shot in enumerate(data["shots"]):
        f0 = starts[i]
        tr = shot.get("transition", "cut")
        if i + 1 < len(data["shots"]):
            C = starts[i + 1]
            if tr == "whip":
                bumps += [(C - 4, 1.0, 0), (C - 1, 1.22, -70), (C, 1.22, 70), (C + 4, 1.0, 0)]
            elif tr == "glitch":
                bumps += [(C - 3, 1.0, 0), (C - 2, 1.05, 40), (C - 1, 1.0, -50), (C, 1.06, 30), (C + 1, 1.0, -20), (C + 2, 1.0, 0)]
        for fx in shot.get("fx", []):
            a = f0 + int(round(fx.get("at", 0) * fps))
            if fx.get("type") == "punch":
                bumps += [(a - 1, 1.0, 0), (a + 2, 1.12, 0), (a + 9, 1.0, 0)]
            elif fx.get("type") == "freeze":
                d = int(round(fx.get("dur", 0.6) * fps))
                bumps += [(a - 1, 1.0, 0), (a + 2, 1.18, 0), (a + d, 1.18, 0), (a + d + 3, 1.0, 0)]
    base = mv.transform.scale_x                    # FIT scale (raw may be smaller than the output)
    for fr, sc_, ox in sorted(bumps):
        if 1 <= fr <= sc.frame_end:
            mv.transform.scale_x = mv.transform.scale_y = base * sc_
            mv.transform.offset_x = ox * base
            for p in ("scale_x", "scale_y", "offset_x"):
                mv.transform.keyframe_insert(p, frame=fr)

    # ---- flashes / fades (color strips over the picture)
    def overlay(name, rgb, a, b, peak_at, peak=1.0):
        a, b = max(1, a), min(sc.frame_end, b)
        if b <= a:
            return
        cs = S.new_effect(name, type='COLOR', channel=9, frame_start=a, length=b - a + 1)
        cs.color = rgb
        cs.blend_type = 'ALPHA_OVER'
        for fr, v in ((a, 0.0 if peak_at > a else peak), (peak_at, peak), (b, 0.0)):
            cs.blend_alpha = v; cs.keyframe_insert("blend_alpha", frame=fr)

    for i, shot in enumerate(data["shots"]):
        f0 = starts[i]
        tr = shot.get("transition", "cut")
        if i + 1 < len(data["shots"]):
            C = starts[i + 1]
            if tr == "flash":
                overlay(f"flash{i}", (1, 1, 1), C, C + 6, C, 0.95)
            elif tr == "fade_black":
                overlay(f"fade{i}", (0, 0, 0), C - 9, C + 9, C, 1.0)
        for fx in shot.get("fx", []):
            if fx.get("type") == "flash":
                a = f0 + int(round(fx.get("at", 0) * fps))
                overlay(f"fxflash{i}", (1, 1, 1), a, a + 6, a, 0.9)

    # ---- captions
    cap = fmt["captions"]
    emph = set()
    for shot in data["shots"]:
        emph.update(clean(w) for w in shot.get("emphasis", []))
    words = [w for s in timing["shots"] for w in s.get("words", [])]
    groups = []
    if cap["style"] == "word":
        groups = [[w] for w in words]
    else:
        g = []
        for w in words:
            if g and (len(g) >= cap.get("max_words", 3) or w["t0"] - g[-1]["t1"] > 0.3 or re.search(r"[.,!?]$", g[-1]["w"])):
                groups.append(g); g = []
            g.append(w)
        if g:
            groups.append(g)
    for k, g in enumerate(groups):
        a = F(g[0]["t0"])
        nxt = groups[k + 1][0]["t0"] if k + 1 < len(groups) else None
        end_t = min(nxt, g[-1]["t1"] + 0.35) if nxt is not None else g[-1]["t1"] + 0.35
        b = max(a + 3, F(end_t) - 1)
        b = min(b, sc.frame_end)
        if a > sc.frame_end:
            continue
        txt = " ".join(re.sub(r"[\"“”]", "", w["w"]) for w in g)
        txt = txt.upper() if cap.get("case") == "upper" else txt.lower() if cap.get("case") == "lower" else txt
        t = S.new_effect(f"cap{k:03d}", type='TEXT', channel=10, frame_start=a, length=b - a + 1)
        t.text = txt
        if fnt:
            t.font = fnt
        t.font_size = cap["size"] if len(txt) < 14 else int(cap["size"] * 14 / len(txt) * 1.1)
        hot = any(clean(w["w"]) in emph for w in g)
        t.color = cap["highlight"] if hot else cap["color"]
        t.use_outline = cap.get("outline", 0) > 0
        t.outline_color = (0, 0, 0, 1)
        t.outline_width = cap.get("outline", 0.1)
        t.use_shadow = True
        t.shadow_color = (0, 0, 0, 0.6); t.shadow_offset = 0.04; t.shadow_blur = 0.4
        t.location = (0.5, cap["y"])
        t.alignment_x = 'CENTER'; t.anchor_x = 'CENTER'; t.anchor_y = 'CENTER'
        t.wrap_width = 0.9
        t.blend_type = 'ALPHA_OVER'
        if cap.get("pop", True):
            for fr, v in ((a, 0.55), (a + 2, 1.12), (a + 4, 1.0)):
                t.transform.scale_x = t.transform.scale_y = v
                t.transform.keyframe_insert("scale_x", frame=fr)
                t.transform.keyframe_insert("scale_y", frame=fr)

    # ---- hook title card (top of the frame, first seconds)
    tc = fmt["title_card"]
    hook = data.get("hook_title")
    if tc.get("show") and hook:
        length = min(sc.frame_end, int(tc.get("seconds", 3.0) * fps))
        t = S.new_effect("hook", type='TEXT', channel=11, frame_start=1, length=length)
        t.text = hook
        if fnt:
            t.font = fnt
        t.font_size = tc["size"] if len(hook) <= 22 else int(tc["size"] * 22 / len(hook) * 1.15)
        t.color = tc["color"]
        t.use_box = True; t.box_color = tc["box"]; t.box_margin = 0.025
        try:
            t.box_roundness = 0.6
        except Exception:
            pass
        t.location = (0.5, tc["y"]); t.alignment_x = 'CENTER'; t.anchor_x = 'CENTER'; t.anchor_y = 'CENTER'
        t.wrap_width = 0.86
        t.blend_type = 'ALPHA_OVER'
        for fr, v in ((1, 0.7), (4, 1.06), (7, 1.0)):
            t.transform.scale_x = t.transform.scale_y = v
            t.transform.keyframe_insert("scale_x", frame=fr); t.transform.keyframe_insert("scale_y", frame=fr)

    ec = fmt["end_card"]
    end_text = data.get("end_text", ec.get("text") if ec.get("show") else None)
    if end_text:
        length = int(ec.get("seconds", 1.4) * fps)
        t = S.new_effect("endcard", type='TEXT', channel=11, frame_start=max(1, sc.frame_end - length + 1), length=length)
        t.text = end_text
        if fnt:
            t.font = fnt
        t.font_size = 96; t.color = (1, 0.86, 0.15, 1)
        t.use_outline = True; t.outline_color = (0, 0, 0, 1); t.outline_width = 0.12
        t.location = (0.5, 0.7); t.alignment_x = 'CENTER'; t.anchor_x = 'CENTER'; t.anchor_y = 'CENTER'
        t.blend_type = 'ALPHA_OVER'

    # ---- output
    r = sc.render
    try:
        r.image_settings.media_type = 'VIDEO'
    except Exception:
        pass
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH' if quality == "final" else 'MEDIUM'
    r.ffmpeg.audio_codec = 'AAC'
    r.ffmpeg.audio_bitrate = 192
    r.ffmpeg.audio_channels = 'STEREO'
    r.ffmpeg.audio_mixrate = 48000
    out = ep / "out"
    out.mkdir(exist_ok=True)
    suffix = "_nomusic" if no_music else ""
    r.filepath = str(out / f"{data['episode']}{suffix}_{quality}.mp4")
    bpy.ops.wm.save_as_mainfile(filepath=str(ep / "render" / f"edit_{quality}{suffix}.blend"))
    print("RENDER edit ->", r.filepath, flush=True)
    bpy.ops.render.render(animation=True)
    print("DONE", r.filepath, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv[0], argv[1] if len(argv) > 1 else "preview", "--no-music" in argv)
