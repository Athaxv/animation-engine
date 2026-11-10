"""
One command from shots.json to a finished, upload-ready video.

    python pipeline/make.py episodes/<ep>                        # preview: validate, voice, build, sheet, raw, edit
    python pipeline/make.py episodes/<ep> --direct               # opt-in Cinematic Director (direct + compile after voice)
    python pipeline/make.py episodes/<ep> --motion-qa            # include 3-point motion sheet + visual_qa.json
    python pipeline/make.py episodes/<ep> --final                # 1080x1920 + no-music copy + thumbnail + publish/
    python pipeline/make.py episodes/<ep> --only sheet           # run single stages (comma list)
    python pipeline/make.py episodes/<ep> --from build           # resume from a stage

Stages: validate, voice, direct, compile, build, sheet, motion_qa, raw, edit, thumb, publish
  direct    -> storyboard.json                   (Cinematic Director Agent)
  compile   -> shots.json                        (Shot Compiler from storyboard.json)
  sheet     -> render/contact_sheet.png          (one labelled still per shot + visual_qa.json)
  motion_qa -> render/motion_sheet.png           (start/mid/end stills + 3D telemetry in visual_qa.json)
  raw       -> render/raw_<q>.mp4                (3D only, no sound)
  edit      -> out/<ep>_<q>.mp4                  (voice + music + sfx + captions + transitions)
  publish   -> publish/<ep>/                     (exported mp4s, thumbnail, tiktok.txt, youtube.txt)
Blender logs go to render/logs/<stage>.log.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
STAGES = ["validate", "voice", "direct", "compile", "build", "sheet", "motion_qa", "raw", "edit", "thumb", "publish"]
BLENDER_STAGES = {"build", "sheet", "motion_qa", "raw", "edit", "thumb"}


def blender_exe():
    """
    Resolve blender.exe using priority:
      1. BLENDER environment variable
      2. shutil.which("blender")
      3. C:\\Program Files\\Blender Foundation\\Blender *\\blender.exe (and D:\\blender.exe fallback)
    Verifies the resolved file exists before returning.
    """
    env_b = os.environ.get("BLENDER", "").strip()
    if env_b:
        p = Path(env_b)
        if p.is_file():
            return str(p)
        sys.exit(f"BLENDER environment variable points to a non-existent file: {env_b}")

    which_b = shutil.which("blender")
    if which_b and Path(which_b).is_file():
        return str(Path(which_b).resolve())

    found = sorted(
        glob.glob(r"C:\Program Files\Blender Foundation\Blender *\blender.exe"),
        key=lambda p: [int(x) if x.isdigit() else x for x in Path(p).parent.name.split()[-1].split(".")],
    )
    for cand in reversed(found):
        if Path(cand).is_file():
            return cand

    fallback = Path(r"D:\blender.exe")
    if fallback.is_file():
        return str(fallback)

    sys.exit("Blender not found: set the BLENDER environment variable or add blender.exe to PATH")


def fail(msg):
    sys.exit(f"ERROR: {msg}")


def load_json(path, description):
    if not path.exists():
        fail(f"Missing {description}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"Invalid JSON in {description} ({path}): {e}")


def check_stage_inputs(st, ep, q):
    """Verify all required inputs for stage `st` exist before launching subprocesses."""
    if not ep.exists() or not ep.is_dir():
        fail(f"Episode folder does not exist: {ep}")

    shots_file = ep / "shots.json"
    sb_file = ep / "storyboard.json"
    timing_file = ep / "timing.json"

    if st == "compile":
        load_json(sb_file, "storyboard.json (run '--only direct' or 'compiler.py --from-shots' first)")
        return

    data = load_json(shots_file, "shots.json")
    ep_name = data.get("episode", ep.name)
    blend = ep / f"{ep_name}.blend"

    if st == "build":
        if not timing_file.exists():
            fail(f"Stage 'build' requires {timing_file}. Run '--only voice' first to generate word timings.")
        load_json(timing_file, "timing.json")
    elif st in ("sheet", "motion_qa", "raw"):
        if not blend.exists():
            fail(f"Stage '{st}' requires Blender scene {blend}. Run '--only build' first.")
        if st == "motion_qa" and not timing_file.exists():
            fail(f"Stage 'motion_qa' requires {timing_file}. Run '--only voice' first.")
    elif st == "edit":
        raw_mp4 = ep / "render" / f"raw_{q}.mp4"
        if not raw_mp4.exists() or raw_mp4.stat().st_size == 0:
            fail(f"Stage 'edit' requires rendered video {raw_mp4}. Run '--only raw' first.")
        timing = load_json(timing_file, "timing.json (run '--only voice' first)")
        missing_audio = [
            str(ep / s["audio"])
            for s in timing.get("shots", [])
            if s.get("audio") and not (ep / s["audio"]).exists()
        ]
        if missing_audio:
            fail(f"Stage 'edit' is missing {len(missing_audio)} audio clip(s) (e.g. {missing_audio[0]}). Run '--only voice' first.")
    elif st == "thumb":
        if not blend.exists():
            fail(f"Stage 'thumb' requires Blender scene {blend}. Run '--only build' first.")
        load_json(timing_file, "timing.json (run '--only voice' first)")
    elif st == "publish":
        out_dir = ep / "out"
        videos = list(out_dir.glob(f"*_{q}.mp4")) if out_dir.exists() else []
        if not videos:
            fail(f"Stage 'publish' requires exported video in {out_dir / f'{ep_name}_{q}.mp4'}. Run '--only edit' first.")


def run(cmd, log=None, label="", expect_token=None, expect_file=None):
    t = time.time()
    print(f"[{label}] ...", flush=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "w", encoding="utf-8", errors="replace") as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=ROOT)
        text = log.read_text(encoding="utf-8", errors="replace")
        has_tb = "Traceback (most recent call last):" in text
        token_ok = True if not expect_token else (expect_token in text)
        file_ok = True if not expect_file else (Path(expect_file).exists() and Path(expect_file).stat().st_size > 0)
        if p.returncode != 0 or has_tb or not token_ok or not file_ok:
            print("\n".join(text.splitlines()[-40:]))
            reasons = []
            if p.returncode != 0:
                reasons.append(f"exit code {p.returncode}")
            if has_tb:
                reasons.append("Python traceback in log")
            if not token_ok:
                reasons.append(f"missing completion marker {expect_token!r}")
            if not file_ok:
                reasons.append(f"missing or empty output {expect_file}")
            sys.exit(f"[{label}] FAILED ({', '.join(reasons)}; log: {log})")
    else:
        p = subprocess.run(cmd, cwd=ROOT)
        if p.returncode != 0:
            sys.exit(f"[{label}] FAILED (exit code {p.returncode})")
        if expect_file and (not Path(expect_file).exists() or Path(expect_file).stat().st_size == 0):
            sys.exit(f"[{label}] FAILED (missing or empty output {expect_file})")
    print(f"[{label}] ok  {time.time() - t:.0f}s", flush=True)


def contact_sheet(ep, data):
    from PIL import Image, ImageDraw, ImageFont
    sheet_json = ep / "render" / "sheet" / "sheet.json"
    info = load_json(sheet_json, "render/sheet/sheet.json")
    text = {s["id"]: s.get("text", "") for s in data["shots"]}
    ims = [Image.open(i["png"]).convert("RGB") for i in info]
    w, h = ims[0].size
    cols = min(8, len(ims)); rows = (len(ims) + cols - 1) // cols
    lab = 46
    S = Image.new("RGB", (w * cols, (h + lab) * rows), (20, 20, 24))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(S)
    for k, (im, i) in enumerate(zip(ims, info)):
        x, y = (k % cols) * w, (k // cols) * (h + lab)
        S.paste(im, (x, y))
        t = f"{i['id']}  {text.get(i['id'], '')}"
        lines, cur = [], ""
        for word in t.split():
            if len(cur) + len(word) > w // 7:
                lines.append(cur); cur = word
            else:
                cur = (cur + " " + word).strip()
        lines.append(cur)
        for j, ln in enumerate(lines[:3]):
            d.text((x + 4, y + h + 2 + j * 14), ln, fill=(235, 235, 235), font=font)
    out = ep / "render" / "contact_sheet.png"
    S.save(out)
    print("contact sheet:", out)


def thumbnail(ep, data, fmt):
    from PIL import Image, ImageDraw, ImageFont
    src = ep / "render" / "thumb.png"
    im = Image.open(src).convert("RGB")
    hook = data.get("hook_title") or data.get("title", "")
    if hook:
        d = ImageDraw.Draw(im)
        W, H = im.size
        size = int(W * 0.085)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\seguibl.ttf", size)
        except Exception:
            font = ImageFont.load_default()
        words, lines, cur = hook.split(), [], ""
        for wd in words:
            test = (cur + " " + wd).strip()
            if d.textlength(test, font=font) > W * 0.86:
                lines.append(cur); cur = wd
            else:
                cur = test
        lines.append(cur)
        lh = int(size * 1.15)
        top = int(H * 0.08)
        box_h = lh * len(lines) + int(size * 0.5)
        d.rounded_rectangle((int(W * 0.04), top, int(W * 0.96), top + box_h), radius=int(size * 0.4), fill=(255, 255, 255))
        for j, ln in enumerate(lines):
            tw = d.textlength(ln, font=font)
            d.text(((W - tw) / 2, top + int(size * 0.2) + j * lh), ln, fill=(15, 15, 18), font=font)
    out = ep / "out" / "thumbnail.png"
    out.parent.mkdir(exist_ok=True)
    im.save(out)
    print("thumbnail:", out)


def publish(ep, data, fmt, q="final"):
    dst = ROOT / "publish" / data["episode"]
    dst.mkdir(parents=True, exist_ok=True)
    copied = list((ep / "out").glob("*_final.mp4"))
    if not copied and (ep / "out").exists():
        copied = list((ep / "out").glob(f"*_{q}.mp4"))
    for f in copied:
        shutil.copy2(f, dst / f.name)
    if (ep / "out" / "thumbnail.png").exists():
        shutil.copy2(ep / "out" / "thumbnail.png", dst / "thumbnail.png")
    pub = data.get("publish", {})
    fp = fmt.get("publish", {})
    tags = list(dict.fromkeys(pub.get("hashtags", []) + fp.get("hashtags", [])))
    tt = pub.get("tiktok_caption", data.get("title", ""))
    (dst / "tiktok.txt").write_text(f"{tt}\n\n{' '.join(tags)}\n", encoding="utf-8")
    yt_title = pub.get("youtube_title", data.get("title", ""))
    yt_desc = pub.get("youtube_description", data.get("logline", data.get("title", "")))
    yt_tags = list(dict.fromkeys(pub.get("tags", []) + fp.get("youtube_tags", [])))
    (dst / "youtube.txt").write_text(
        f"TITLE:\n{yt_title}\n\nDESCRIPTION:\n{yt_desc}\n\n{' '.join(tags)}\n\nTAGS:\n{', '.join(yt_tags)}\n",
        encoding="utf-8")
    print("publish package:", dst)
    for p in sorted(dst.iterdir()):
        print("   ", p.name)


def main():
    ap = argparse.ArgumentParser(description="Orchestrate the Roblox animation pipeline from shots.json to finished video.")
    ap.add_argument("episode_dir", help="Episode folder path (e.g. episodes/wi_3am_monster)")
    ap.add_argument("--final", action="store_true", help="Render 1080x1920 final video + no-music copy + thumbnail + publish/")
    ap.add_argument("--direct", action="store_true", help="Opt-in: run Cinematic Director + Shot Compiler before building")
    ap.add_argument("--motion-qa", action="store_true", help="Opt-in: render 3-point start/mid/end motion sheet and visual_qa.json")
    ap.add_argument("--only", default="", help=f"Comma-separated stages to run ({', '.join(STAGES)})")
    ap.add_argument("--from", dest="start", default="", help="Resume pipeline starting from this stage")
    a = ap.parse_args()

    ep = Path(a.episode_dir).resolve()
    if not ep.exists() or not ep.is_dir():
        fail(f"Episode folder not found: {ep}")

    q = "final" if a.final else "preview"
    if a.only:
        stages = [s.strip() for s in a.only.split(",") if s.strip()]
    else:
        stages = ["validate", "voice"]
        if a.direct:
            stages += ["direct", "compile"]
        stages += ["build", "sheet"]
        if a.motion_qa:
            stages += ["motion_qa"]
        stages += ["raw", "edit"]
        if a.final:
            stages += ["thumb", "publish"]
        if a.start:
            if a.start not in STAGES:
                fail(f"Unknown --from stage {a.start!r}; valid stages: {STAGES}")
            if a.start not in stages:
                # Build full stage sequence starting from a.start
                idx = STAGES.index(a.start)
                tail = [s for s in STAGES[idx:] if s not in ("direct", "compile", "motion_qa") or s == a.start
                        or (s in ("direct", "compile") and a.direct) or (s == "motion_qa" and a.motion_qa)]
                if not a.final:
                    tail = [s for s in tail if s not in ("thumb", "publish") or s == a.start]
                stages = tail
            else:
                stages = stages[stages.index(a.start):]

    bad = [s for s in stages if s not in STAGES]
    if bad:
        fail(f"Unknown stage(s) {bad}; valid stages: {STAGES}")

    # Only resolve Blender when at least one Blender stage is scheduled
    B = blender_exe() if any(s in BLENDER_STAGES for s in stages) else None

    logs = ep / "render" / "logs"
    py = sys.executable
    t0 = time.time()

    for st in stages:
        check_stage_inputs(st, ep, q)
        data = load_json(ep / "shots.json", "shots.json") if (ep / "shots.json").exists() else {}
        fp = ROOT / "formats" / data.get("format", "_") / "format.json"
        fmt = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
        blend = ep / f"{data.get('episode', ep.name)}.blend"

        if st == "validate":
            run([py, str(PIPE / "validate.py"), str(ep)], label="validate")
        elif st == "voice":
            run([py, str(PIPE / "voiceover.py"), str(ep)], label="voice", expect_file=ep / "timing.json")
        elif st == "direct":
            run([py, str(PIPE / "director.py"), str(ep)], label="direct", expect_file=ep / "storyboard.json")
        elif st == "compile":
            run([py, str(PIPE / "compiler.py"), str(ep)], label="compile", expect_file=ep / "shots.json")
        elif st == "build":
            run([B, "-b", "--factory-startup", "--python", str(PIPE / "episode.py"), "--", str(ep)],
                logs / "build.log", "build", expect_token="BUILT", expect_file=blend)
        elif st == "sheet":
            run([B, "-b", str(blend), "--python", str(PIPE / "render.py"), "--", "sheet"],
                logs / "sheet.log", "sheet", expect_token="DONE sheet", expect_file=ep / "render" / "sheet" / "sheet.json")
            contact_sheet(ep, data)
            run([py, str(PIPE / "visual_qa.py"), str(ep)], label="visual_qa", expect_file=ep / "render" / "visual_qa.json")
        elif st == "motion_qa":
            run([B, "-b", str(blend), "-t", "2", "--python", str(PIPE / "render.py"), "--", "motion_sheet"],
                logs / "motion_qa.log", "motion_qa", expect_token="DONE motion_sheet",
                expect_file=ep / "render" / "motion_sheet" / "motion_sheet.json")
            run([py, str(PIPE / "visual_qa.py"), str(ep)], label="visual_qa", expect_file=ep / "render" / "visual_qa.json")
        elif st == "raw":
            run([B, "-b", str(blend), "--python", str(PIPE / "render.py"), "--", "raw", q],
                logs / f"raw_{q}.log", f"raw {q}", expect_token="DONE", expect_file=ep / "render" / f"raw_{q}.mp4")
        elif st == "edit":
            out_mp4 = ep / "out" / f"{data['episode']}_{q}.mp4"
            run([B, "-b", "--factory-startup", "--python", str(PIPE / "edit.py"), "--", str(ep), q],
                logs / f"edit_{q}.log", f"edit {q}", expect_token="DONE", expect_file=out_mp4)
            if q == "final":
                out_nomusic = ep / "out" / f"{data['episode']}_nomusic_{q}.mp4"
                run([B, "-b", "--factory-startup", "--python", str(PIPE / "edit.py"), "--", str(ep), q, "--no-music"],
                    logs / "edit_final_nomusic.log", "edit final (no music)", expect_token="DONE", expect_file=out_nomusic)
        elif st == "thumb":
            timing = load_json(ep / "timing.json", "timing.json")
            th = data.get("thumbnail", {})
            T = {s["id"]: s for s in timing["shots"]}
            sid = th.get("shot") or data["shots"][min(1, len(data["shots"]) - 1)]["id"]
            fr = T[sid]["start_frame"] + int(round(th.get("at", T[sid]["duration"] / 2) * data.get("fps", 30)))
            run([B, "-b", str(blend), "--python", str(PIPE / "render.py"), "--", "thumb", str(fr)],
                logs / "thumb.log", "thumb", expect_token="DONE thumb", expect_file=ep / "render" / "thumb.png")
            thumbnail(ep, data, fmt)
        elif st == "publish":
            publish(ep, data, fmt, q=q)

    outs = sorted((ep / "out").glob(f"*_{q}.mp4")) if (ep / "out").exists() else []
    print(f"\nfinished in {(time.time() - t0) / 60:.1f} min")
    for o in outs:
        print("video:", o)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
