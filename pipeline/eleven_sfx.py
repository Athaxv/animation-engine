"""
Generate the sound-effect library with ElevenLabs (text -> sound) into public/audio/sfx/<name>.mp3.
These win over the numpy-synthesized fallbacks in public/audio/sfx/synth/.

    python pipeline/eleven_sfx.py                 # create every missing one
    python pipeline/eleven_sfx.py --only boom,crickets --force
    python pipeline/eleven_sfx.py --list

Costs ElevenLabs credits (roughly per second of generated audio); run it once, the files are reused forever.
Add a new effect: add a line to LIB (name: (prompt, seconds)), run with --only <name>.
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eleven  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "public" / "audio" / "sfx"

LIB = {
    # --- upgrades of the synthesized basics (same names, the engine already uses them)
    "whoosh":         ("fast cartoon whoosh swipe transition, clean, short", 0.6),
    "pop":            ("cartoon bubble pop, bright and short", 0.5),
    "boing":          ("cartoon spring boing jump sound", 0.8),
    "bonk":           ("cartoon bonk hit on the head, wooden knock, comedic", 0.6),
    "ding":           ("bright bell ding notification, single hit", 1.0),
    "boom":           ("deep cinematic bass boom impact hit, meme style dramatic reveal", 1.6),
    "thud":           ("cartoon body falling flat on the floor, soft thud", 0.7),
    "riser":          ("short tension riser whoosh building up, ends abruptly", 2.0),
    "record_scratch": ("vinyl record scratch freeze-frame, comedic", 0.8),
    "poof":           ("magic poof smoke puff disappearing, cartoon", 0.8),
    "slide_up":       ("slide whistle going up, cartoon", 0.8),
    "slide_down":     ("slide whistle going down, cartoon fail", 0.9),
    "buzzer":         ("game show wrong answer buzzer", 0.9),
    "correct":        ("game show correct answer ding ding chime", 1.0),
    "glitch":         ("digital glitch stutter transition, short", 0.6),
    "sparkle":        ("magical sparkle shimmer chime", 1.0),
    "tick":           ("single clock tick", 0.3),
    "cartoon_run":    ("cartoon running feet scramble, fast comedic", 1.0),
    "drum_hit":       ("punchy comedy rimshot drum hit", 0.8),
    # --- new, for cringe / absurd comedy
    "crickets":       ("crickets chirping in awkward silence, comedic, night", 2.5),
    "sad_trombone":   ("sad trombone wah wah wah waaah, comedic fail", 2.2),
    "crowd_gasp":     ("small crowd gasping in shock, indoor", 1.4),
    "crowd_laugh":    ("small crowd laughing, sitcom audience laughter", 2.5),
    "crowd_cheer":    ("crowd cheering and clapping excitedly", 2.5),
    "crowd_aww":      ("audience going awww, sympathetic", 1.8),
    "dun_dun_dun":    ("dramatic orchestral sting dun dun dunnn, comedic suspense", 2.2),
    "punch":          ("cartoon punch impact, comedic", 0.5),
    "slip":           ("cartoon slip on banana peel then thud", 1.2),
    "splash":         ("water splash, someone falling into water", 1.2),
    "explosion":      ("cartoon explosion, comedic, not scary", 1.6),
    "siren":          ("short police siren whoop whoop", 1.6),
    "phone_ring":     ("smartphone ringtone ringing", 2.0),
    "door_knock":     ("three knocks on a wooden door", 1.2),
    "cash_register":  ("cash register cha-ching", 1.0),
    "camera_shutter": ("camera shutter click", 0.4),
    "gulp":           ("cartoon nervous gulp swallow", 0.6),
    "magic":          ("magic spell whoosh with sparkles, transformation", 1.5),
    "drumroll":       ("snare drum roll building suspense, ends with cymbal crash", 3.0),
    "heartbeat":      ("tense heartbeat thump thump", 2.0),
    "applause":       ("audience applause", 2.5),
    "alarm":          ("alarm clock ringing loudly", 2.0),
    "evil_laugh":     ("cartoon villain evil laugh, comedic, mwahaha", 2.2),
    "yawn":           ("a cartoon sleepy yawn", 1.6),
    "tada":           ("ta-da fanfare, short triumphant", 1.4),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (p, s) in LIB.items():
            have = (OUT / f"{k}.mp3").exists()
            print(f"{'*' if have else ' '} {k:15s} {s:4.1f}s  {p}")
        return
    if not eleven.available():
        sys.exit("No key: put ELEVENLABS_API_KEY=... into the .env file in the project folder")
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, a.only.split(",")))
    for name, (prompt, secs) in LIB.items():
        if only and name not in only:
            continue
        dst = OUT / f"{name}.mp3"
        if dst.exists() and not a.force:
            continue
        audio = eleven.sound_effect(prompt, secs)
        dst.write_bytes(audio)
        print(f"  {name:15s} {len(audio) // 1024:4d} KB")
    print("done ->", OUT)


if __name__ == "__main__":
    main()
