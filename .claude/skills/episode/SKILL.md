---
name: episode
description: Turn a one-line video idea into a finished vertical video with the Blender Roblox engine - writes the story (script.md + shots.json) in the right format, validates it, renders a contact sheet, checks it visually, fixes problems, then renders the preview/final mp4 with voice, music, captions and a publish package. Use whenever the user gives an idea for a video/episode ("what if…", "in this town…", "сделай ролик про…", "идея: …") or asks to make/render/remake an episode.
---

# /episode: idea -> video

The user writes an idea (often in Russian, often one line). You write the story **in English** (US audience)
and drive the pipeline to a finished video. Talk to the user in Russian.

## 0. Pick the format
- Given explicitly (`/episode what_if …`) → use it.
- Otherwise infer: "what if / что если / а что если" → `what_if`; "in this town / в этом городе" → `in_this_town`;
  anything else → `what_if` (the channel's main format). Say which one you picked in one line.
- Formats live in `formats/<name>/` (`FORMAT.md` = how to write it, `format.json` = engine style).

## 1. Load the rules (every time, they change)
Read, in this order:
1. `formats/<format>/FORMAT.md`: structure, hook, writing rules.
2. `python pipeline/vocab.py`: the ONLY words the engine understands (cast, sets, marks, poses, faces,
   actions, props, fx, sfx, music). Never invent a pose/mark/prop; build the joke from what exists.
3. `episodes/SHOTLIST_FORMAT.md`: the shots.json schema + gotchas.
4. When a gag depends on an object, look at `public/roblox/props_lineup.png` (all props rendered) to pick one.

## 2. Write the episode
- Folder: `episodes/<prefix>_<slug>` where prefix is `wi` (what_if) or `itt` (in_this_town), slug is 2–4 snake_case
  words; series add `_p1`, `_p2`. Never overwrite an existing episode folder: pick a new slug or ask.
- `script.md`: title, logline, cast table, and the narration as a numbered beat table (line | speaker | what we see).
  Hit the format's length and shot count. 6–14 words per line, a cut every 1.5–3 s.
- `shots.json`: one shot per line. Directing rules that make it look good:
  - Vary shot sizes: close_up / medium_close for reactions and punchlines, medium for actions, wide or
    `cam_aerial` (street) for establishing. Never 3 identical framings in a row.
  - The hook shot gets motion: `push_in` / `whip_in` / `crash_zoom` and a striking action.
  - Every character on screen does something (an action or a face change); the speaker of a dialogue line
    is in the shot. For dialogue use `"speaker": "<Name>"`.
  - `emphasis`: 1 key word per punchline. `transition`: mostly `cut`, `whip` between locations, `flash` on the twist.
  - Props sell the absurd: hand props (`props` + pose `hold`) for small things, `place` with a big `scale` and
    `pop_at` for "suddenly a giant donut" moments. Text props (`sign:`/`paper:`/`flag:`) for written punchlines.
  - Write lines for the voice: ElevenLabs acts out punctuation ("Wait... WHAT?!", "Okay. So."). Use it for timing
    and emotion instead of extra words.
  - SFX are a big part of the comedy: add 1–3 per shot from the vocab list (crickets after a cringe line,
    sad_trombone on a fail, dun_dun_dun on a reveal, crowd_gasp/crowd_laugh as reactions). Don't stack many at once.
    Only names printed by vocab.py exist; the comedy set (crickets, sad_trombone, …) appears after
    `python pipeline/eleven_sfx.py` has been run once.
  - Fill `hook_title`, `thumbnail` (the most expressive shot) and `publish` (tiktok caption, youtube title).

## 3. Validate & Direct
- `python pipeline/validate.py episodes/<ep>` → fix every ERROR, consider each cinematic WARN. Repeat until 0 errors.
- Optional Cinematic Director pass (after voiceover `timing.json` is generated):
  - `python pipeline/director.py episodes/<ep> --compile` (or `python pipeline/make.py episodes/<ep> --only voice,direct,compile`)
    generates `storyboard.json` and compiles `shots.json` with R6 shoulder de-overlapping, reachable locomotion destinations, varied camera compositions, and anti-idle reaction beats without altering narration or regenerating voiceover.

Voice: ElevenLabs is used automatically when `.env` has `ELEVENLABS_API_KEY`; otherwise Edge TTS (warn the user that
the voice is the cheap one). Never ask the user to paste the key into the chat.

## 4. Look before you render (mandatory)
```
python pipeline/make.py episodes/<ep> --only voice,direct,compile,build,sheet
```
(or `--only voice,build,sheet` without the director pass, and `--only motion_qa` to render start/mid/end stills into `render/motion_sheet.png` + `render/visual_qa.json`).
Then **Read `episodes/<ep>/render/contact_sheet.png`** (and `render/visual_qa.json`) and check:
- the target character is in frame and readable (face visible, not cut off, not tiny, not hidden);
- facing/staging matches the line; props visible when they matter; the location/dressing reads.
Fix the shots.json (camera shot/angle/target, dx/dy, facing, pose, mark) and re-run `--only build,sheet`.
Up to 3 rounds; if something can't be fixed with the vocabulary, simplify the beat instead.
For a specific moment: `blender -b episodes/<ep>/<ep>.blend --python pipeline/frames.py -- <out_dir> <frame> ...`.

## 5. Render
- Preview (default): `python pipeline/make.py episodes/<ep> --from raw` in the **background**
  (≈0.3 s per frame at 540×960: a 60 s episode takes ≈10 min). Result: `episodes/<ep>/out/<ep>_preview.mp4`.
- Final, only when the user asks for it (or approved the preview): `python pipeline/make.py episodes/<ep> --final --from raw`
  in the **background**. It takes much longer: tell the user the estimate from the log. Result: `publish/<ep>/`
  with `<ep>_final.mp4`, `<ep>_nomusic_final.mp4` (for adding a trending sound in TikTok), `thumbnail.png`,
  `tiktok.txt`, `youtube.txt`.
- On failure: read `episodes/<ep>/render/logs/<stage>.log`, fix, resume with `--from <stage>`.

## 6. Report (in Russian, short)
Format + title, length, shot count, what the story is in one sentence, the path to the video, what you fixed
after the contact sheet, and anything that looked weak. Offer the next step (final render / part 2 / tweaks).

## Don'ts
- Don't edit engine code (`pipeline/*.py`) to make one episode work. If the engine truly lacks something,
  say so and propose the engine change separately.
- Don't use anything from `pipeline/legacy/`, `public/characters/` or `public/sets/` (old blocky models).
- Don't upload or post anything: the user uploads manually.
