# Format: What if

**Premise:** "What if <one impossible change to the world>?" The Roblox cast lives through it. Each
beat escalates the consequence. Audience is teens and adults, so the humour is clever-absurd, not toddler.
Narrator = Theo, first person or calm explainer ("you", "everyone").

## Structure (45–75 s, 16–28 shots)
1. **Hook (0–3 s, 1–2 shots).** The question itself, over the most striking visual of the premise.
   `hook_title` = the question in CAPS, max ~30 characters ("WHAT IF GRAVITY TURNED OFF?").
2. **First consequence (3–10 s).** The obvious, relatable effect. Gets the viewer nodding.
3. **Escalation (10–45 s), 4–6 beats.** Each beat is bigger, weirder or more personal than the last.
   Mix scales: one home beat, one town beat, one authority beat (King / Officer), one tiny absurd detail.
4. **Twist (last 8–12 s).** A clever consequence nobody saw coming, or the premise turned on the narrator.
5. **Button (last 2 s).** One-line punch, or a question that makes people comment ("Would you survive?").

## Writing rules
- One idea per shot, **6–14 words per line**. A cut every 1.5–3 s.
- Concrete and visual: every line must be filmable with the engine's poses, actions, props and FX.
  Open with `python pipeline/vocab.py` and build each joke from what is in it.
- Numbers and specifics sell it ("in 4 minutes", "37 people", "the King's crown").
- No dark or gore beats. Absurd yes, cruel no. Keep it advertiser-friendly.
- The first word on screen must already be the hook. No intros, no "hey guys".

## Visual language
- Premise visual = an FX or action: `float` (gravity), `scale` (giants/tiny), `tint` (colors),
  `poof`/`pop_in` (vanishing), `sign:<TEXT>` prop (new laws), `dance`/`spin` (compulsions).
- Authority beats: King or Officer holding a `sign:` with a NEW RULE.
- Reaction shots: `close_up` + face `shocked`/`nervous` + `surprise_hop`.
- Big moments: `crash_zoom` (on a character who is standing still) + fx `shake` or `punch`.
- Transitions: mostly `cut`, a `whip` between locations, a `flash` on the twist.

## Titles and captions
- `title`: "What If <Premise>?" (YouTube Title Case).
- `publish.tiktok_caption`: the question + one emoji + a challenge ("would you survive this? 🤯").
- `publish.youtube_title`: under 60 characters, ends with `#shorts` for Shorts uploads.
