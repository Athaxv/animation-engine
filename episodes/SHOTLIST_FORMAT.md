# Shot list format (`shots.json`, engine v2: R6 Roblox cast)

One file per episode, in `episodes/<episode>/shots.json`; `episode` must equal the folder name.
Every word you may use (sets, marks, poses, faces, actions, props, sfx…) is listed by
`python pipeline/vocab.py`. `python pipeline/validate.py episodes/<ep>` checks the file.

Times inside a shot are **seconds from the shot start**. Shot lengths come from the voiceover
(word timings), so you never write durations, except for silent shots (`"text": ""` + `"duration"`).

```jsonc
{
  "episode": "wi_gravity_off",              // = folder name
  "format": "what_if",                      // formats/<name>/ (style, voice, music, hashtags)
  "title": "What If Gravity Turned Off For 10 Seconds?",
  "logline": "One sentence: premise + twist.",
  "hook_title": "WHAT IF GRAVITY TURNED OFF?",   // white box at the top for the first ~3 s
  "fps": 30, "resolution": [1080, 1920],
  "narrator": "Theo",
  "music": "curious",                       // optional: overrides the format's mood
  "end_text": "PART 2?",                    // optional: big text over the last ~1.3 s
  "tts": "elevenlabs",                      // optional: elevenlabs | edge (default: elevenlabs when a key is set)
  "eleven_voices": {"narrator": {"voice": "Liam", "style": 0.5}},   // optional ElevenLabs overrides
  "voices": {"narrator": ["en-US-AndrewNeural", "+8%", "+0Hz"]},   // optional overrides (Edge TTS fallback)
  "characters": {                           // optional custom characters = a preset + overrides
    "Grandma": {"base": "Mom", "hair": [0.85, 0.85, 0.88], "hair_style": "short", "extras": ["glasses"],
                "top": [0.55, 0.75, 0.6], "voice": ["en-US-JennyNeural", "-10%", "-6Hz"],
                "eleven_voice": {"voice": "Matilda", "stability": 0.4, "style": 0.5}}
  },
  "shots": [
    {
      "id": "s01",
      "set": "street", "dressing": "day",   // dressing optional (first one is the default)
      "speaker": "narrator",                // or a cast name: that character lip-syncs, uses its voice
      "text": "What if gravity turned off for ten seconds?",
      "hold": 0.0,                          // optional extra seconds after the last word (awkward pause!)
      "camera": {"shot": "medium", "angle": "low", "move": "push_in", "target": "Theo"},
      "cast": [
        {
          "name": "Theo", "mark": "sidewalk_b", "dx": 0, "dy": 0,   // dx/dy: nudge off the mark (studs)
          "facing": "camera",               // camera | left | right | away | <cast name> | <mark>
          "pose": "shocked", "face": "shocked",
          "action": "float",                // see vocab: idle, talk, walk_to, jump, float, poof, ...
          "scale": 1.0,                     // giant / tiny
          "tint": {"color": [0.3, 0.55, 1.0], "amount": 0.7},       // recolored skin for this shot
          "props": ["sign:NO FLYING"],      // right-hand props; shows best with pose "hold"
          "changes": [                      // timed changes inside the shot
            {"at": 1.2, "face": "laugh"},
            {"at": 1.2, "action": "walk_to", "to": "sidewalk_c"},
            {"at": 2.0, "scale": 2.5, "over": 0.4},
            {"at": 2.0, "props": []}
          ]
        }
      ],
      "place": [                            // props standing in the world (not in a hand)
        {"prop": "donut", "mark": "sidewalk_c", "id": "big_donut", "scale": 6, "rot": 15,
         "dx": 0, "dy": 0, "z": 0,          // z lifts it (onto a table ~2.0)
         "pop_at": 1.0, "poof_at": 3.5}     // optional: pops in / poofs away (sfx added automatically)
      ],                                    // camera.target may be a placed id: "target": "big_donut"
      "fx": [{"type": "shake", "at": 0.8, "dur": 0.5}],   // shake, tint, punch, flash, freeze
      "sfx": [{"at": 1.0, "name": "boom"}],               // extra sfx (many are added automatically)
      "emphasis": ["gravity"],              // caption words shown in the highlight color
      "transition": "whip"                  // into the NEXT shot: cut | whip | flash | fade_black | glitch
    }
  ],
  "thumbnail": {"shot": "s04", "at": 1.5},  // frame used for the thumbnail (hook_title is drawn on it)
  "publish": {
    "tiktok_caption": "What if gravity turned off for 10 seconds? 🤯 would you survive?",
    "youtube_title": "What If Gravity Turned Off For 10 Seconds? #shorts",
    "youtube_description": "…",
    "hashtags": ["#gravity"],               // added to the format's hashtags
    "tags": ["gravity"]                     // added to the format's YouTube tags
  }
}
```

## Automatic things (don't script them)
- Blinks, breathing, lip flaps on the real word timings (for the `speaker`, and for `talk`/`talk_still`).
- Camera framing per shot type, a soft key light that follows the camera, a nudge so no set
  object blocks the face, following a `float`ing target up, all-cast framing for two_shot/group/wide.
- SFX: `surprise_hop`→pop, `jump`/`celebrate`→boing, `fall_back`→thud, `poof`→poof, `float`/`spin`→slide_up,
  `run_*`→cartoon_run, fx `shake`→boom, `whip`→whoosh, `glitch`→glitch, `flash`→pop,
  placed prop `pop_at`→pop, `poof_at`→poof.
- Voice: ElevenLabs (with a key in `.env`) or Edge TTS, cast per character from `public/audio/eleven_voices.json`.
- Captions from the voiceover words, styled by the format. Title card from `hook_title`.

## Gotchas
- Faces from actions win at that moment: `laugh`, `cry`, `sleep`, `surprise_hop`, `fall_back` set their own face.
- `walk_in` starts off-screen at the start of the action, so frame the mark (not a crash zoom onto it).
- `sit` only looks right on marks with a seat (vocab marks them `(seat)`); `lie`/`sleep` belong on `bed`.
- A character can only be in one place per shot; split the shot if they must be in two.
- Props are in the right hand; `pose: "hold"` shows them upright in front of the belly (face stays clear),
  `sign:` is held in the middle of the chest. Frame them with `medium` or wider: `medium_close`/`close_up` crop them.
- Hand props (`props` on a cast member) are small; for a gag that must read on a phone screen use a world prop
  (`place`) with `scale` 3–8 and frame it (`target` = its id, or a medium/wide shot that includes it).
- Text props: `sign:TEXT` (chest placard), `paper:TEXT`, `flag:TEXT`; keep TEXT to 1–3 short words.
- All props at a glance: `public/roblox/props_lineup.png`.
- Pausing in a line: ElevenLabs reads punctuation, so "Wait... what?" gets a real pause; `hold` adds silence after.
