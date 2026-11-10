# Format: In this town (absurd / cringe)

**Premise:** "In this town, <absurd rule>." First-person story narrated by Theo. The rule is played
dead straight while everything around it gets more ridiculous. Cringe comedy: awkward situations,
over-the-top reactions, a twist that makes the rule even dumber. Reference look: @kr.editzx0.

## Structure (50–90 s, 18–32 shots)
1. **Hook (0–3 s).** "In this town, <rule>." Shown in action right away.
   `hook_title` = the rule in CAPS, short ("IN THIS TOWN, SNEEZING IS ILLEGAL").
2. **How the town lives with it (3–15 s), 2–3 quick examples.** Mom, Dad, the King, the Officer.
3. **The incident (15–40 s).** Theo (or a friend) breaks the rule, by accident or on purpose. It escalates.
4. **Consequence (40–70 s).** The town reacts way too seriously: trial by the King, Officer with a sign, crowd.
5. **Twist + cliffhanger (last 10 s).** The rule turns out to have a dumb origin, or the twist hits the narrator.
   End on a question or "Part 2?". The end card is on by default for this format.

## Writing rules
- Present tense or simple past, first person: "In this town…", "So I…", "And then my mom…".
- **6–14 words per line**, a cut every 1.5–3 s, every line filmable (check `python pipeline/vocab.py`).
- Cringe = awkward silence beats (`hold`: 0.4–0.8 s on a reaction close-up), over-reactions
  (`surprise_hop`, `fall_back`, `cry`), deadpan authority (Officer `sleep` face, King `confident`).
- Recurring cast keeps the channel recognisable: Theo (me), Max (best friend), Lily (sister),
  Mom, Dad, King, Officer, Noob (the town's unlucky guy).
- Absurd yes, mean no: nobody is humiliated for who they are. Advertiser-friendly.

## Visual language
- Captions: one word, lowercase, white, the key word in yellow (`emphasis`).
- Bright daytime by default. Bedroom `night` for "that night…" beats, street `sunset` for endings.
- Rule-enforcement beats: Officer/King + `sign:<RULE>` prop, `crash_zoom` + `boom` sfx.
- Reaction close-ups: `close_up` + `shocked`/`nervous`/`cry`, `push_in`.

## Titles and captions
- `title`: "In This Town, <Rule>".
- `publish.tiktok_caption`: the rule + "(part 1)" + emoji.
- Series: name the folder `itt_<slug>_p1`, `_p2`… and keep the cast and set the same between parts.
