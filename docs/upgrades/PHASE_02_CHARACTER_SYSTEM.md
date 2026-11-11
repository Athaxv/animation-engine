# Phase 02: Character Identity System (appearance consistency + expanded hair / clothing / accessories)

- **Status:** Complete for the delivered scope (rendered and visually inspected)
- **Date:** 2026-11-10
- **Engine Target:** Blender 5.2.3 LTS (`D:\blender.exe`) + Python pipeline (`D:\ai-video\ROBLOX ANIMATION`)

---

## 1. What this phase is (and is not)

Phase 1 made environments modular. Phase 2 makes the **characters** reusable and
personally distinct while keeping the shipped R6 skeleton and every existing preset
byte-compatible.

What changed:

* A **persistent identity registry** — skin, hair, clothing, accessories, body scale,
  voice and animation personality live in *data*, not in per-shot code.
* **Expanded appearance libraries**: 11 new hair silhouettes (17 total), 7 garment
  overlays (8 total incl. `none`), 6 chest prints, 16 accessories in 3 clearance zones.
* A **face-atlas quality pass** on the existing 16 expressions, plus a hair-fringe fix
  that had been grazing the eye band.
* An **appearance preview tool** (5 rendered sheets) and a **33-check test suite**.

What this phase deliberately does **not** claim:

* It does not add hair simulation, cloth simulation or morphing. R6 stays blocky.
* It does not replace the six legacy hair styles — they are still the default look of
  the eight original presets, unchanged (proven by `preset/all-8-unchanged-by-defaults`).
* Accessory coverage is 16 pieces, not an exhaustive catalogue; they were chosen to
  cover the three most useful zones (head-top, face, body).
* The ten new characters are first-pass art: they read correctly in a 9-up lineup and
  in close-ups, but several silhouettes still have known weaknesses (§8).

---

## 2. Audit findings on the pre-existing characters

| Area | Finding | Action |
|---|---|---|
| Face atlas (16 expressions) | Eyes were legible but the specular catchlight was too small to survive mobile resolution (~120 px head). The `nervous` mouth read as a thin "zipper". | Catchlight enlarged (0.016×0.021 vs 0.013×0.017) and eye ovals widened (+12 % horizontally, height unchanged so the hairline stays clear); `nervous` mouth rebuilt as a proper gritted-teeth grid with a sweat bead. **All 16 expression ids preserved exactly** (`faces/match-atlas` proves the order and names are untouched). |
| Legacy hair fringes | After re-deriving the real painted-eye extents, the `long` cap rim grazed the top of the decal eye band (10 hits at z ≈ 4.89–4.91). | `_hair_cap` cut for `long` raised from `0.0` to `0.10`; all 6 legacy styles now measure **0 eye / 0 mouth hits** with the correct band. |
| Legacy fringe tips (`messy`) | Tips ended 0.10 too low and 1.12× too wide, so they dipped into the eye band. | Tip crown raised `cz+0.30 → cz+0.40`, radius `2.5 → 2.2`. |
| Legacy long-hair curtains | Curtain lengths descended straight through the brow line. | Re-tiered to `cz+0.50−0.02k`. |
| Legacy hats (`crown`, `police`, `cap`) | Never measured against the band. | Verified clear (`hair/legacy-hats-clear`). |
| The honest error I made first | My initial eye band (`z 4.71–4.86, |x|≤0.36`) was copied from a measurement note and was **too permissive** — the painted eyes really span z 4.659–4.891 and |x| ≤ 0.243. | Band corrected in `checks.py` to `z 4.63–4.91, |x| ≤ 0.30`; the stricter band immediately caught the real `long`-cap graze listed above. Tests are only useful if they measure the actual decal. |

---

## 3. Architecture

New package (mirrors Phase 1's `pipeline/assets/`, deliberately separate — this is a
*character* registry, not a second environment registry):

```
pipeline/characters/
    __init__.py      bpy-free import surface, RIG_KWARGS filter, identity_to_rig_kwargs,
                     appearance_signature, summary()
    identities.py    18 identities, schema validation, JSON export
    hair.py          10 new silhouettes + the 6 legacy names + bald
    clothing.py      7 garment overlays with second-order detail + 6 prints
    accessories.py   16 accessories, declared zones (head_top / face / body)
    checks.py        all geometry proof: painted-band hits, zone-aware clearance,
                     R6 rig report, mesh signatures

pipeline/build_characters.py      bakes every identity to public/roblox/characters/<Name>.blend
pipeline/render_character_lineup.py  renders the 5 preview sheets
pipeline/test_characters.py       33 checks, runs with or without Blender
pipeline/roblox_rig.py            hooks + fringe fixes; unknown hair styles delegate
                                  to characters/hair.py (_build_extra_hair)
```

Key design rules:

* **Appearance lives in `shots.json`-free data.** `episode.py` builds a rig from an
  identity whenever a cast entry says `"identity": "<id>"`; appearance overrides on
  that entry are *refused with a warning* instead of silently forking the look.
* **Legacy presets stay first-class.** `legacy_preset` identities build verbatim from
  `roblox_rig.PRESETS` (only `face` is set, which is what the preset does anyway).
* **`body_scale` is applied once.** It is set as `rig.scale` at build time and recorded
  on the rig; `episode.py` composes it as
  `cur_scale = scale * rig["body_scale"]`, so it never double-applies and never fights
  the scale animation (`rig/body-scale-applied-once`).
* **Clearance is measured, not hand-waved.** A vertex counts as occluding the face only
  if it is in front of the actual head cylinder (|x| ≤ 0.30, 4.63 ≤ z ≤ 4.91,
  y < −(√(0.64² − x²) + 0.02)). Accessories are *zone-aware*: `head_top` must not enter
  the eye/mouth band, `face` must own at least one vertex in front of the head surface
  (occupying the face is its job), `body` must not intersect the torso interior box.

---

## 4. Identity schema

Baked example — `public/roblox/characters/Aiko.blend` + `character_identities.json`:

```json
{
  "id": "aiko",
  "name": "Aiko",
  "legacy_preset": null,
  "proportions": { "body_scale": 1.0, "head_scale": 1.0, "arm_scale": 1.0, "leg_scale": 1.0 },
  "skin": [1.0, 0.82, 0.66],
  "head_style": "round",
  "face_style": "neutral",
  "hair":   { "style": "spiky", "color": [0.07, 0.06, 0.09], "seed": 5, "fringe_dir": -1.0 },
  "clothing": {
    "top": [0.13, 0.24, 0.52], "pants": [0.24, 0.26, 0.36], "accent": [0.96, 0.96, 0.98],
    "shoes": [0.1, 0.1, 0.12], "sleeves": "long", "bottom": "skirt",
    "outfit": "school_uniform", "print": "none", "fabric": true, "details": []
  },
  "accessories": ["satchel"],
  "voice": { "eleven_voice": "adam", "stability": 0.52, "similarity_boost": 0.78, "style": 0.5 },
  "personality": { "default_pose": "relaxed", "idle_action": "look_around", "walk_speed": 0.85, "id": "shy" }
}
```

Rules enforced by `validate_identity()` / `validate_all()` (currently **0 errors**):

* `id` must match `^[a-z][a-z0-9_]{1,31}$`; ids and display names are unique.
* Display names resolve as aliases, so `"identity": "Aiko"` also works in scripts.
* Every referenced hair / outfit / print / accessory / head style / face must exist in
  the matching registry (checked both in `validate.py` and at build time).
* `personality.default_pose` must be a key of `vocab.POSES` and `idle_action` a key of
  `vocab.ACTIONS`, so a personality can never invent words the engine cannot animate.

---

## 5. Asset counts (honest)

| Library | Registry | Count |
|---|---|---|
| Identities curated | `identities.py` | **18** (8 legacy presets + 10 new) |
| Hair silhouettes | `hair.py` | **17** (6 legacy: messy, short, under_cap, swept, long, pigtails; 10 new: spiky, layered, side_swept, bob, ponytail, buzz, curly, mohawk, braids, wavy_long; plus `bald`) |
| Outfits | `clothing.py` | **8** (`none`, hoodie, jacket, tshirt, school_uniform, suit, dress, themed) |
| Chest prints | `clothing.py` | **6** (`none`, star, heart, circle, stripe, bolt) |
| Accessories | `accessories.py` | **16** — head_top: beanie, top_hat, wizard_hat, flower_crown, headband, headphones (6); face: sunglasses, mask, monocle, eyepatch (4); body: scarf, backpack, satchel, cape, wings, amulet (6) |
| Head styles | `roblox_rig.build_head` | **2** (`round`, `square`) |
| Skin tones | `identities.py` | **5** (light, tan, brown, deep, noob) |
| Personalities | `identities.py` | **8** (curious, calm, energetic, shy, regal, sleepy, goofy, brave) |
| Faces | `roblox_rig.py` atlas | **16** (unchanged ids) |

Combination space (upper bound, not-enumerated): `17 hair × 8 outfits × 6 prints ×
2 head styles × 5 skin tones = 8,160` base looks before any accessory is added; with
accessories chosen as an arbitrary subset of 16 that becomes `× 2^16 = 534,773,760`
theoretical looks. The engine builds a rig on demand from these slots but the shipped
content is the **18 curated identities**, of which 5+ are strongly visually distinct
(Aiko vs Sable vs Zephyr vs Mira vs Tessa differ in palette, hair, silhouette and gear).

---

## 6. Files created / changed

New:

* `pipeline/characters/{__init__,identities,hair,clothing,accessories,checks}.py`
* `pipeline/build_characters.py`, `pipeline/render_character_lineup.py`, `pipeline/test_characters.py`
* `public/roblox/characters/<Name>.blend` × 18 + `build_report.json` + `sheets/raw_*.png`
  — baked mesh counts range 8 (Noob) to 56 (Dev); every identity reports `ok: true`
  (no missing R6 bones, no hair eye/mouth hits, every accessory zone-clear),
  hair vertices ranging 0 (bald) to 10,852 (`wavy_long`).
* `public/roblox/character_identities.json` (registry mirror, regenerated by the bake)
* `public/roblox/characters/characters_{hair,outfit,accessory,face}_sheet.png`, `characters_lineup.png`
  and the combined `characters_all_sheets.png`

Changed:

* `pipeline/roblox_rig.py` — face-atlas clarity, fringe fixes, `build_head(style)`,
  `build_character(outfit/print_kind/print_color/accessories/body_scale/head_style)`,
  `_build_extra_hair()` delegation, `rig_helpers()`.
* `pipeline/episode.py` — `identity` cast entry (`build_identity_rig`, appearance owned
  by the identity), `body_scale` composition already present.
* `pipeline/voiceover.py` — an identity's `voice` profile supplies the ElevenLabs cast
  entry automatically (`identity_voice()`); an explicit `eleven_voice` still wins.
* `pipeline/vocab.py` — hair/outfit/print/accessory lists now come from the registry
  (cannot drift), plus a "Cast (Phase 2 identities)" cheat-sheet section.
* `pipeline/validate.py` — identity references validated; appearance overrides on an
  identity-cast entry are errors, not silent divergences.
* `pipeline/catalog.py` output (`catalog.json`) regenerated from the baked blends, so
  `catalog.json["characters"]` now lists **18** prebuilt characters (the cheat sheet,
  the Cinematic Director and the validator all read that list).

Temporary diagnostics `pipeline/_probe_hair.py` / `pipeline/_probe_deep.py` used during
this phase were deleted after use.

---

## 7. Rendering / bake pipeline and thermal safety

* The bake (`build_characters.py`) is pure geometry — no render, so the frame cap does
  not apply; it still runs with `-t 2`.
* Preview sheets render **one frame per row** inside a single `-t 2` Blender process
  and are composited with PIL by shelling out to system `python` (Blender's bundled
  Python has no PIL).
* Accessory back-pieces are shown from behind (`__yaw__ = 180°`) so the sheet actually
  proves a cape/wings/backpack exist instead of a torso silhouette on a grey box.

Rendered lineup paths:

```
public/roblox/characters/characters_hair_sheet.png       17 hair silhouettes
public/roblox/characters/characters_outfit_sheet.png      8 outfits on a neutral body
public/roblox/characters/characters_accessory_sheet.png  16 accessories in 2 rows
public/roblox/characters/characters_face_sheet.png       16 expressions, 4x4
public/roblox/characters/characters_lineup.png           all 18 identities side by side
public/roblox/characters/characters_all_sheets.png       combined contact strip
```

---

## 8. Known visual limitations (measured, not optimistic)

1. **`mohawk` reads as a narrow crest from head-on.** Geometrically correct (a mohawk
   *is* thin across X) but it is the least recognisable of the ten new styles in a
   straight-on render; it is unambiguous in 3/4 view. Shaved sides are now explicit,
   which helps.
2. **`ponytail` tail mostly hides behind the head** in a front view. Fixed by removing
   the bangs (slicked-back hairline) so the style still reads as "pulled back", but the
   tail itself only appears from behind.
3. **`buzz` is intentionally minimal** and could be mistaken for `bald` at very small
   frame sizes; its stubble shell is deliberately kept tight so it never clipped the
   eye band.
4. **Cape / wings are flat primitives** (a solidified grid, two flattened teardrop
   halves). No motion, no cloth. Good enough for "she has wings", not for hero shots.
5. **Legacy outfits keep their flat-box silhouettes** (`skirt` bottoms, robe shoulders)
   because Phase 2 must not mutate the original presets.
6. **No animated transitions between facial expressions beyond blinks** and the
   existing `ACTION_FACE` map (`surprise_hop→shocked`, `laugh→laugh`, `cry→cry`,
   `sleep→sleep`, `celebrate→laugh`, `fall_back→shocked`); there is no in-between frame
   scrub yet — a decal swap with a 2-frame hold, which reads fine at 30 fps but is not
   a morph.
7. Accessory collisions with **hand props** (a sword held while wearing a satchel) are
   not auto-resolved; the props pass is upstream of the accessory system.

---

## 9. Tests — `pipeline/test_characters.py`

Run without Blender (registry/schema only):

```
python pipeline/test_characters.py
```

Full geometry suite:

```
blender -b --factory-startup -t 2 --python pipeline/test_characters.py
```

Result: **RESULT: 33/33 passed, 0 failed**

| Group | Checks |
|---|---|
| SCHEMA, no Blender (20 checks) | `validate_all()` clean · required keys / unique ids+names · every referenced asset resolves · accessory zones declared · hair catalogue has no duplicates and includes the legacy names · face list matches the live atlas order · personality words are in `vocab.POSES`/`ACTIONS` · `identity_to_rig_kwargs` filtered + deterministic · `appearance_signature` stable and distinct for the 10 new looks · the 8 legacy identities map 1:1 to `roblox_rig.PRESETS` · registry JSON serialises and matches disk |
| GEOMETRY, needs Blender (13 checks) | all 18 identities build an R6 rig with bones, head, decal material and face prop · `body_scale` applied exactly once · all 16 expressions have a decal with the right atlas index · bald head never occludes its own face · **no eye/mouth hit for all 17 hair styles** · legacy hats clear · all 16 accessories pass zone-aware clearance · accessory zones fully covered · all 8 outfits rebuild to identical signatures even at a different world position · no cross-character state leak · repeated identity builds are identical · the 8 legacy presets are unchanged by Phase 2 defaults · every identity has a baked `.blend` |

Note: Blender headless scripts tend to exit non-zero even on success here; judge the
run by the final `RESULT:` line.

---

## 10. How to add a character

1. Append to `CHARACTER_IDENTITIES` in `pipeline/characters/identities.py`:

```python
"nico": dict(name="Nico", legacy_preset=None,
             proportions=dict(body_scale=1.0),
             skin=(0.98, 0.74, 0.5), head_style="round", face_style="grin",
             hair=dict(style="curly", color=(0.2, 0.11, 0.05), seed=21, fringe_dir=1.0),
             clothing=dict(top=(0.9, 0.5, 0.2), pants=(0.3, 0.32, 0.4), accent=(1, 0.95, 0.45),
                           shoes=(0.9, 0.9, 0.92), sleeves="short", bottom="shorts",
                           outfit="tshirt", print="star", fabric=True, details=()),
             accessories=("headphones",),               # must exist in ACCESSORY_REGISTRY
             voice=dict(eleven_voice="Callum", stability=0.3, similarity_boost=0.8, style=0.6),
             personality=dict(default_pose="relaxed", idle_action="dance", walk_speed=1.1, id="goofy")),
```

2. `python pipeline/test_characters.py` — the schema half catches a bad reference
   before any Blender launch.
3. Bake: `blender -b --factory-startup -t 2 --python pipeline/build_characters.py -- nico`
   (writes `public/roblox/characters/Nico.blend`, refreshes the JSON and build report).
4. See it: `blender -b --factory-startup -t 2 --python pipeline/render_character_lineup.py -- identities`
   and open `public/roblox/characters/characters_lineup.png`.
5. Use it in an episode:

```json
"characters": { "Nico": { "identity": "nico" } }
```

…and reference `"Nico"` in `cast` exactly like any prebuilt character. `pipeline/validate.py`
rejects the episode if the identity does not exist or if the cast entry tries to
override the identity's appearance. Voice comes from the identity automatically; to
give Nico a different voice for one episode, add `"eleven_voice": {"voice": "Will"}`.

For a *one-off* look (not reuse), the legacy path still works:

```json
"characters": { "Stranger": { "base": "Theo", "hair_style": "mohawk", "top": [0.8, 0.1, 0.1] } }
```

---

## 11. Out of scope / next ideas

* Hair / accessory animation interferers for fast actions.
* An in-between decal cross-fade for expression changes.
* Furniture-accurate lying poses for long hair (currently the sheet only guarantees
  *static* clearance).
