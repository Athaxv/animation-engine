"""
Minimal ElevenLabs client (stdlib only): text-to-speech with timestamps, voices, sound effects.

The API key is read from the environment variable ELEVENLABS_API_KEY or from a line
    ELEVENLABS_API_KEY=...
in the project's .env file. Never put the key in code, shots.json or chat.

    python pipeline/eleven.py voices      # list the voices on your account (name, id, labels)
    python pipeline/eleven.py check       # is the key there and valid? (prints subscription quota)
"""
import base64, json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io"


def api_key():
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if k:
        return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("ELEVENLABS_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def available():
    return bool(api_key())


def _req(method, path, body=None, accept="application/json", tries=4):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(tries):
        req = urllib.request.Request(API + path, data=data, method=method, headers={
            "xi-api-key": api_key(), "Content-Type": "application/json", "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:400]
            if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"ElevenLabs {method} {path} -> HTTP {e.code}: {msg}") from None
        except urllib.error.URLError as e:
            if attempt < tries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"ElevenLabs unreachable: {e}") from None


def voices():
    return json.loads(_req("GET", "/v1/voices"))["voices"]


def resolve_voice(name_or_id, cache={}):
    """Accept a voice id or a (case-insensitive) voice name from the account."""
    if not cache:
        for v in voices():
            cache[v["voice_id"]] = v["voice_id"]
            cache.setdefault(v["name"].lower(), v["voice_id"])
            cache.setdefault(v["name"].split(" ")[0].lower(), v["voice_id"])
    key = name_or_id if name_or_id in cache else name_or_id.lower()
    if key not in cache:
        raise KeyError(f"voice {name_or_id!r} not on this ElevenLabs account (python pipeline/eleven.py voices)")
    return cache[key]


def tts(text, voice_id, model="eleven_multilingual_v2", settings=None, previous_text=None, next_text=None,
        fmt="mp3_44100_128"):
    """-> (mp3_bytes, words[(word, t0, t1)]) using the character alignment."""
    body = {"text": text, "model_id": model}
    if settings:
        body["voice_settings"] = settings
    if previous_text:
        body["previous_text"] = previous_text
    if next_text:
        body["next_text"] = next_text
    r = json.loads(_req("POST", f"/v1/text-to-speech/{voice_id}/with-timestamps?output_format={fmt}", body))
    audio = base64.b64decode(r["audio_base64"])
    al = r.get("alignment") or r.get("normalized_alignment") or {}
    chars = al.get("characters", [])
    t0s = al.get("character_start_times_seconds", [])
    t1s = al.get("character_end_times_seconds", [])
    words, cur, a, b = [], "", None, None
    for ch, s, e in zip(chars, t0s, t1s):
        if ch.isspace():
            if cur:
                words.append((cur, a, b))
            cur, a = "", None
            continue
        if a is None:
            a = s
        cur += ch
        b = e
    if cur:
        words.append((cur, a, b))
    # drop punctuation-only tokens (e.g. a lone "-" or "...")
    words = [w for w in words if any(c.isalnum() for c in w[0])]
    return audio, words


def sound_effect(prompt, seconds=None, influence=0.45):
    body = {"text": prompt, "prompt_influence": influence}
    if seconds:
        body["duration_seconds"] = seconds
    return _req("POST", "/v1/sound-generation", body, accept="audio/mpeg")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if not available():
        sys.exit("No key: put ELEVENLABS_API_KEY=... into the .env file in the project folder")
    if cmd == "voices":
        for v in sorted(voices(), key=lambda v: v["name"]):
            labels = ", ".join(f"{k}={x}" for k, x in (v.get("labels") or {}).items())
            print(f"{v['name']:28s} {v['voice_id']}  {labels}")
    else:
        sub = json.loads(_req("GET", "/v1/user/subscription"))
        print("key OK. tier:", sub.get("tier"), " characters used:", sub.get("character_count"), "/", sub.get("character_limit"))
