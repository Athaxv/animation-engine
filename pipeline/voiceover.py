"""
Voiceover: per-shot narration/dialogue -> audio clips + word timings -> timing.json (re-times the episode).

    python pipeline/voiceover.py episodes/<ep>
    python pipeline/voiceover.py episodes/<ep> --only s10,s12     # regenerate some shots
    python pipeline/voiceover.py episodes/<ep> --engine edge       # force an engine
    python pipeline/voiceover.py --list-voices

Engines
  elevenlabs  natural, expressive (needs ELEVENLABS_API_KEY in .env; cast in public/audio/eleven_voices.json)
  edge        free Microsoft Edge TTS (fallback)
Choice: --engine > shots.json "tts" > format.json "tts" > elevenlabs if a key is set, else edge.

Outputs (in the episode folder):
    audio/<shot>.mp3       one clip per shot that has text
    timing.json            real shot start/duration + every word's absolute time (captions + lip sync)
    narration_preview.mp3  all clips back-to-back, just for listening
"""
import argparse, asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eleven  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Edge TTS cast: speaker -> (voice, rate, pitch). Overridden by format.json / shots.json "voices".
VOICES = {
    "narrator": ("en-US-AndrewNeural", "+10%", "+0Hz"),
    "Theo":     ("en-US-AndrewNeural", "+10%", "+4Hz"),
    "Max":      ("en-US-GuyNeural", "+10%", "+2Hz"),
    "Lily":     ("en-US-AnaNeural", "+6%", "+0Hz"),
    "Mom":      ("en-US-EmmaNeural", "+6%", "+0Hz"),
    "Dad":      ("en-US-ChristopherNeural", "+4%", "-4Hz"),
    "King":     ("en-GB-RyanNeural", "-4%", "-8Hz"),
    "Officer":  ("en-US-EricNeural", "-6%", "-10Hz"),
    "Noob":     ("en-US-RogerNeural", "+14%", "+10Hz"),
}
ELEVEN_CFG = ROOT / "public" / "audio" / "eleven_voices.json"
BITRATE = {"edge": 48000, "elevenlabs": 128000}
LEAD_IN = 0.08               # silence before speech starts inside a shot
TAIL = 0.22                  # breathing room after the last word
TAIL_BEFORE_FADE = 0.5       # extra hold before fade_black transitions
MIN_SHOT = 0.9               # never cut faster than this


async def synth_edge(text, voice, rate, pitch):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    audio, words = bytearray(), []
    async for ch in com.stream():
        if ch["type"] == "audio":
            audio.extend(ch["data"])
        elif ch["type"] == "WordBoundary":
            t0 = ch["offset"] / 1e7
            words.append((ch["text"], t0, t0 + ch["duration"] / 1e7))
    return bytes(audio), words


def pick_engine(data, fmt_json, forced):
    eng = forced or data.get("tts") or fmt_json.get("tts") or ("elevenlabs" if eleven.available() else "edge")
    if eng == "elevenlabs" and not eleven.available():
        print("! ElevenLabs requested but no ELEVENLABS_API_KEY in .env -> using edge")
        eng = "edge"
    return eng


def identity_voice(name):
    """
    ElevenLabs cast entry derived from a character identity's voice profile.

    Identities carry ``voice.eleven_voice`` plus stability / similarity / style so a
    character sounds the same in every episode that casts them by identity.
    """
    if not name:
        return None
    try:
        if str(ROOT / "pipeline") not in sys.path:
            sys.path.insert(0, str(ROOT / "pipeline"))
        import characters as _ch
        cid = _ch.resolve(name)
        if not cid:
            return None
        prof = _ch.get(cid).get("voice") or {}
    except Exception:
        return None
    voice = prof.get("eleven_voice")
    if not voice:
        return None
    out = {"voice": voice}
    for k in ("stability", "similarity_boost", "style", "speed"):
        if k in prof:
            out[k] = prof[k]
    return out


def eleven_cast(data):
    cfg = json.loads(ELEVEN_CFG.read_text(encoding="utf-8"))
    cast = dict(cfg["voices"])
    for name, spec in data.get("characters", {}).items():
        entry = spec.get("eleven_voice")
        if isinstance(entry, str):
            entry = {"voice": entry}
        if isinstance(entry, dict):
            # an explicit per-episode override always wins
            cast[name] = entry
        elif name not in cast:
            by_identity = identity_voice(spec.get("identity"))
            if by_identity:
                cast[name] = by_identity
            elif spec.get("base") in cast:
                cast[name] = cast[spec["base"]]
    for k, v in data.get("eleven_voices", {}).items():
        cast[k] = {**cast.get(k, {}), **v}
    return data.get("eleven_model", cfg.get("model", "eleven_multilingual_v2")), cast


async def main(ep_dir, only=frozenset(), force=False, engine=None):
    ep = Path(ep_dir)
    data = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    out = ep / "audio"
    out.mkdir(exist_ok=True)
    narrator = data.get("narrator", "Theo")
    fp = ROOT / "formats" / data.get("format", "_") / "format.json"
    fmt_json = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
    eng = pick_engine(data, fmt_json, engine)
    print("tts engine:", eng)

    voices = dict(VOICES)
    voices.update({k: tuple(v) for k, v in fmt_json.get("voices", {}).items()})
    voices.update({k: tuple(v) for k, v in data.get("voices", {}).items()})
    for name, spec in data.get("characters", {}).items():
        if "voice" in spec:
            voices[name] = tuple(spec["voice"])
    if eng == "elevenlabs":
        model, cast = eleven_cast(data)

    shots = data["shots"]
    texts = [(s.get("text") or "").strip() for s in shots]
    sem = asyncio.Semaphore(2 if eng == "elevenlabs" else 4)
    results = {}

    async def do(i, shot):
        sid, text = shot["id"], texts[i]
        if not text:
            return
        mp3 = out / f"{sid}.mp3"
        meta = out / f"{sid}.json"
        spk = shot.get("speaker", "narrator")
        if eng == "elevenlabs":
            v = cast.get(spk) or cast["narrator"]
            settings = {k: v[k] for k in ("stability", "similarity_boost", "style", "speed", "use_speaker_boost") if k in v}
            # neighbouring lines of the same speaker give the model the flow of the story
            prev_t = next((texts[j] for j in range(i - 1, -1, -1) if texts[j] and shots[j].get("speaker", "narrator") == spk), None)
            next_t = next((texts[j] for j in range(i + 1, len(shots)) if texts[j] and shots[j].get("speaker", "narrator") == spk), None)
            key = f"eleven|{model}|{v['voice']}|{json.dumps(settings, sort_keys=True)}|{text}"
        else:
            voice, rate, pitch = voices.get(spk, voices["narrator"])
            key = f"{voice}|{rate}|{pitch}|{text}"
        if not force and sid not in only and mp3.exists() and meta.exists():
            cached = json.loads(meta.read_text(encoding="utf-8"))
            if cached.get("key") == key:          # same text + voice -> reuse
                results[sid] = cached
                return
        async with sem:
            for attempt in range(3):
                try:
                    if eng == "elevenlabs":
                        vid = eleven.resolve_voice(v["voice"])
                        audio, words = await asyncio.to_thread(eleven.tts, text, vid, model, settings, prev_t, next_t)
                    else:
                        audio, words = await synth_edge(text, voice, rate, pitch)
                    break
                except KeyError:
                    raise
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1.5)
        mp3.write_bytes(audio)
        info = {"key": key, "engine": eng, "speaker": spk, "audio_len": round(len(audio) * 8 / BITRATE[eng], 3),
                "words": [[w, round(a, 3), round(b, 3)] for w, a, b in words]}
        meta.write_text(json.dumps(info, indent=1), encoding="utf-8")
        results[sid] = info
        print(f"  {sid} {spk:9s} {info['audio_len']:5.2f}s  {text[:60]}")

    await asyncio.gather(*(do(i, s) for i, s in enumerate(shots)))

    # ---- re-time
    t = 0.0
    timing = {"episode": data["episode"], "fps": data["fps"], "narrator": narrator, "engine": eng, "shots": []}
    preview = bytearray()
    for s in shots:
        sid = s["id"]
        info = results.get(sid)
        if info:
            # TTS clips can carry trailing silence, so time the shot from the last word
            speech_end = info["words"][-1][2] if info["words"] else info["audio_len"]
            tail = TAIL_BEFORE_FADE if s.get("transition") == "fade_black" else TAIL
            dur = max(MIN_SHOT, LEAD_IN + speech_end + tail + s.get("hold", 0.0))
            words = [{"w": w, "t0": round(t + LEAD_IN + a, 3), "t1": round(t + LEAD_IN + b, 3)} for w, a, b in info["words"]]
            preview.extend((out / f"{sid}.mp3").read_bytes())
        else:
            dur, words = s.get("duration", 1.5) + s.get("hold", 0.0), []
        dur = round(dur, 3)
        timing["shots"].append({
            "id": sid, "start": round(t, 3), "duration": dur,
            "start_frame": round(t * data["fps"]) + 1, "frames": max(1, round(dur * data["fps"])),
            "speaker": s.get("speaker", "narrator"),
            "audio": f"audio/{sid}.mp3" if info else None,
            "audio_start": round(t + LEAD_IN, 3) if info else None,
            "words": words,
        })
        t += dur
    timing["total"] = round(t, 3)
    timing["total_frames"] = round(t * data["fps"])
    (ep / "timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    (ep / "narration_preview.mp3").write_bytes(bytes(preview))
    print(f"\nTotal {t:.1f}s ({timing['total_frames']} frames @ {data['fps']}fps), engine {eng}")
    print("wrote", ep / "timing.json")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir", nargs="?")
    ap.add_argument("--only", default="", help="comma-separated shot ids to regenerate")
    ap.add_argument("--force", action="store_true", help="regenerate every clip")
    ap.add_argument("--engine", choices=["elevenlabs", "edge"])
    ap.add_argument("--list-voices", action="store_true")
    a = ap.parse_args()
    if a.list_voices:
        print("edge cast:")
        for k, v in VOICES.items():
            print(f"  {k:9s} {v}")
        print("elevenlabs cast (public/audio/eleven_voices.json):")
        for k, v in json.loads(ELEVEN_CFG.read_text(encoding="utf-8"))["voices"].items():
            print(f"  {k:9s} {v}")
        print("elevenlabs key:", "found" if eleven.available() else "missing (.env ELEVENLABS_API_KEY=...)")
        sys.exit(0)
    if not a.episode_dir:
        ap.error("episode_dir required")
    asyncio.run(main(a.episode_dir, set(filter(None, a.only.split(","))), a.force, a.engine))
