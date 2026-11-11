# PHASE 04 — ROBLOX CINEMATIC CAMERA, LIGHTING & VFX ENGINE
## Technical Architecture, Mathematical Specification & Implementation Plan

**Author:** Lead Technical Director, Cinematographer & Procedural VFX Engineer  
**Date:** November 2026  
**Status:** Approved for Implementation  
**Target Codebase:** `D:\ai-video\ROBLOX ANIMATION`  

---

## 1. Executive Summary & Objective

Phase 01 introduced the modular procedural asset and environment library (`town_square`, architectural assets, catalog metadata). Phase 02 introduced the persistent character identity system with unique R6 character signatures, hair, accessories, and proportion scaling. Phase 03 implemented comprehensive animation intelligence, including easing-curve blending, analytical R6 inverse kinematics, foot-planting locomotion, multi-character choreography, and 2D collision-aware navigation.

**Phase 04** elevates the engine from procedural character choreography to high-end **cinematic Roblox storytelling animation**. It introduces four interconnected subsystems:
1. **Subsystem A (Cinematic Camera Intelligence):** Multi-subject framing, 180-degree conversational axis tracking, safe-area headroom calculation, smooth quintic/Bezier camera motion, character POV, OTS, and ray-tested collision/obstruction avoidance.
2. **Subsystem B (Cinematic Lighting Engine):** 12 distinct atmospheric lighting environments, a dynamic three-point character lighting rig (key, fill, rim/kicker), environment-aware interior/exterior transitions, and view-transform color management with mood grading.
3. **Subsystem C (Atmospheric & Environmental VFX):** Deterministic, headless-compatible procedural volumetric fog/haze/god-rays, animated weather systems (rain, snow, wind-blown falling leaves), and story-driven procedural VFX (sparks/embers, magical portals, energy bursts, impact dust).
4. **Subsystem D (Scene-Level Visual Composition & Pipeline Integration):** A narrative composition binder linking camera language, lighting mood, weather, and VFX across multi-shot arcs, integrated seamlessly into `pipeline/episode.py`, `pipeline/director.py`, `pipeline/compiler.py`, `pipeline/vocab.py`, and `pipeline/validate.py`.

All systems adhere strictly to the authentic **Roblox R6 storytelling aesthetic** (chunky silhouettes, vibrant saturated tones, classic face decals, blocky props) while operating 100% reliably in Blender 5.x headless mode (`blender -b`) with thermal rendering safeguards.

---

## 2. Audit of Existing Camera, Lighting, and Visual Code

A rigorous audit of the existing codebase (`pipeline/episode.py`, `pipeline/roblox_sets.py`, `pipeline/render.py`, `pipeline/validate.py`, `pipeline/vocab.py`) reveals the baseline architecture:

### 2.1 Existing Camera System (`pipeline/episode.py`, lines 679–852)
- **Framing & FoV:** Uses a fixed 35mm lens (`LENS = 35.0`, portrait sensor half-angle `TAN_HALF = 18.0 / 35.0`). Frame height is looked up from `FRAME_H = {"extreme_close_up": 1.9, "close_up": 3.1, "medium_close": 4.4, "medium": 6.6, "two_shot": 7.2, "group": 7.2, "over_shoulder": 6.0, "insert": 2.4, "wide": 15.0, "extreme_wide": 40.0}`.
- **Framing Logic:** Evaluates targets in `pos` (character root), `marks` (set marks), or `PLACED` (placed props). Basic two-shot/group math computes the centroid and x-span.
- **Vertical Safe-Area:** Phase 03 added basic headroom scaling for 9:16 vertical video (`H = max(H, (max_head_z - min_feet_z) / 0.63)`).
- **Obstruction Handling:** `unblock(p, L)` calls `first_blocker(start, p)` using `bpy.context.scene.ray_cast(dg, o, d, distance=L - travelled)`. If blocked, it tests vertical lifts (`[1.5, 3.0, 5.0]`), then azimuthal rotations (`[20, -20, 35, -35]` degrees), or pulls in front of the blocker.
- **Movements:** Supports hardcoded camera keys: `push_in`, `pull_out`, `pan_left`, `pan_right`, `orbit_left`, `orbit_right`, `track`, `whip_in`, `crash_zoom`, and `shake`.
- **Gaps:**
  - Lacks character POV, bird's-eye/top-down, low hero angles, high dramatic angles, and dynamic OTS tracking.
  - Lacks conversational 180-degree axis tracking: consecutive shots can easily cause disorienting axis jumps when cutting between speakers.
  - Camera movement between keyframes is linear or single-step, lacking smooth quintic/S-curve acceleration or curved dolly paths.
  - Camera obstruction testing only tests line-of-sight between camera and look target; it does not test camera near-plane sphere clearance against walls behind the camera.

### 2.2 Existing Lighting System (`pipeline/episode.py` lines 197–259 & 591–605)
- **World Lighting:** `WORLDS` in `pipeline/roblox_sets.py` contains only 3 static presets:
  - `"day"`: Sky `(0.42, 0.72, 1.0)`, Light `(0.85, 0.92, 1.0)`, Strength `0.55`
  - `"sunset"`: Sky `(1.0, 0.62, 0.42)`, Light `(1.0, 0.8, 0.65)`, Strength `0.45`
  - `"night"`: Sky `(0.06, 0.08, 0.2)`, Light `(0.3, 0.36, 0.65)`, Strength `0.35`
- **Character Lighting:** `key_light_follow` places a single Area light (`EP_KeyLight`, energy 110 interior / 160 exterior, color `(1.0, 0.94, 0.86)`) positioned slightly right and above the camera.
- **Gaps:**
  - No 3-point lighting: no fill light to soften eye sockets, and no rim/kicker light behind actors to separate dark hair/accessories from dark or complex backgrounds.
  - No cinematic moods: completely missing golden hour, blue hour, moonlit night, warm bedroom, school/office fluorescent, horror/under-lit, and fantasy/magical palettes.
  - Hard cuts in lighting without smooth color/intensity transition interpolation.
  - No color management configuration (exposure, contrast curves, saturation).

### 2.3 Existing VFX & Atmosphere
- **Gaps:**
  - Completely non-existent in the current pipeline.
  - Zero volumetric fog, distance haze, dust motes, weather (rain, snow, falling leaves), or story VFX (sparks, magic portals, energy bursts, impact puffs).

### 2.4 Thermal & Performance Safeguards Audit
- In `pipeline/render.py`:
  - `motion_sheet`: Implements `if rendered_count % 15 == 0: time.sleep(2.0)` to mitigate GPU/CPU thermal throttling.
  - `raw` video render: Dispatches Blender headless animation render via EEVEE.
  - Note: Older documentation referenced a 150-frame/10-second setting; the actual codebase source of truth uses the 15-frame/2-second pause in `motion_sheet`. Phase 04 preserves this mechanism and ensures all procedural VFX are lightweight geometry instances or efficient shaders that render under EEVEE in <0.2s per frame.

---

## 3. Architecture of the Cinematography Package (`pipeline/cinematography/`)

To prevent further monolith bloating of `pipeline/episode.py` (already 1068 lines), all cinematic intelligence will be organized into a dedicated, modular package:

```
pipeline/cinematography/
├── __init__.py           # Public unified API
├── camera.py             # Shot framing, 180-deg axis tracking, raycast clearance, quintic motion
├── lighting.py           # 12 lighting setups, 3-point character rig (key, fill, rim), color grading
├── vfx.py                # Procedural headless volumetric fog, weather (rain/snow/leaves), story VFX
└── composition.py        # Scene-level visual narrative binder, continuity validator
```

### Module Responsibilities:

| Module | Primary Role | Key Classes / Functions |
|---|---|---|
| `camera.py` | Compute camera position, orientation, DoF, tracking paths, and safe-area framing | `CinematicCamera`, `compute_shot_framing`, `track_conversational_axis`, `smooth_camera_path`, `resolve_camera_collision` |
| `lighting.py` | Configure Blender world, environment lights, 3-point dynamic character rigs, color grading | `LightingEngine`, `LIGHTING_PRESETS`, `setup_world_lighting`, `setup_three_point_rig`, `apply_color_grading` |
| `vfx.py` | Procedural particle and shader generation for atmosphere, weather, and magic | `VFXEngine`, `create_volumetric_fog`, `create_weather_system`, `create_story_vfx`, `animate_environmental_motion` |
| `composition.py` | Coordinate camera, lighting, and VFX across shots into unified narrative sequences | `CinematicComposition`, `bind_shot_cinematography`, `validate_continuity` |

---

## 4. Mathematical and Algorithmic Specifications

### 4.1 Subsystem A — Cinematic Camera Intelligence

#### 4.1.1 Shot Composition & Framing Math
The vertical sensor dimension and portrait 9:16 aspect ratio dictate vertical half-angle $\theta = \arctan(18.0 / L_{\text{lens}})$.
For a desired subject framing height $H_{\text{frame}}$, the camera distance $D$ is:
$$D = \frac{H_{\text{frame}}}{2 \cdot \tan\theta}$$

For multi-character compositions with $N$ characters at positions $\{ \mathbf{P}_i \}$:
$$\mathbf{P}_{\text{centroid}} = \frac{1}{N} \sum_{i=1}^N \mathbf{P}_i$$
$$\Delta X = \max_{i} |\mathbf{P}_i \cdot \mathbf{u}_{\text{cam\_right}} - \mathbf{P}_{\text{centroid}} \cdot \mathbf{u}_{\text{cam\_right}}|$$
$$\Delta Z = \max_i (\mathbf{P}_{i,\text{head}}.z) - \min_i (\mathbf{P}_{i,\text{feet}}.z)$$
$$H_{\text{frame}} = \max\left(H_{\text{preset}}, \frac{\Delta X \cdot 16/9}{1 - 2\delta_{\text{margin}}}, \frac{\Delta Z}{0.63}\right)$$
where $\delta_{\text{margin}} = 0.12$ guarantees horizontal padding and $0.63$ maintains vertical safe-area headroom (leaving 22% bottom margin for captions and 15% top margin for UI).

#### 4.1.2 Conversational Axis & 180-Degree Rule Tracking
For characters $A$ and $B$, the vector defining the conversation line (Line of Action) is:
$$\mathbf{L}_{AB} = \frac{\mathbf{P}_B - \mathbf{P}_A}{\|\mathbf{P}_B - \mathbf{P}_A\|}$$
The camera orientation normal vector $\mathbf{N}_{\text{axis}} = \mathbf{L}_{AB} \times \hat{\mathbf{z}}$ defines the active half-space.
When cutting from a two-shot to single-character close-ups or over-the-shoulder (OTS) shots:
$$\text{sgn}\left((\mathbf{P}_{\text{cam}} - \mathbf{P}_{\text{centroid}}) \cdot \mathbf{N}_{\text{axis}}\right) = \text{const}$$
This guarantees that Character $A$ consistently looks screen-right ($\mathbf{u}_{\text{look}} \cdot \mathbf{u}_{\text{cam\_right}} > 0$) and Character $B$ consistently looks screen-left ($\mathbf{u}_{\text{look}} \cdot \mathbf{u}_{\text{cam\_right}} < 0$).

#### 4.1.3 Raycast Obstruction & Near-Plane Clearance Cone
To avoid camera clipping through set walls or foliage, a raycast cone of 5 rays is cast from look-target $\mathbf{L}$ toward candidate camera position $\mathbf{P}$:
1. Center ray: $\mathbf{L} \to \mathbf{P}$
2. Top-left, top-right, bottom-left, bottom-right near-plane corner rays offset by near-clip radius $r_{\text{near}} = 0.4$ studs.
If any ray hits non-actor set geometry at distance $d_{\text{hit}} < \|\mathbf{P} - \mathbf{L}\|$:
1. **Vertical Elevation Elevation:** Test $\mathbf{P}' = \mathbf{P} + z_{\text{lift}} \hat{\mathbf{z}}$ for $z_{\text{lift}} \in [1.2, 2.5, 4.0]$.
2. **Azimuthal Step:** Rotate $\mathbf{P}$ around $\mathbf{L}$ within the 180-degree safe half-space by angles $\alpha \in [\pm 15^\circ, \pm 30^\circ, \pm 45^\circ]$.
3. **Pull-In (Push Dolly):** Scale distance to $d_{\text{safe}} = d_{\text{hit}} - 0.45$ studs.

#### 4.1.4 Quintic Smoothstep Trajectory Interpolation
For camera moves between waypoint $\mathbf{P}_0$ and $\mathbf{P}_1$ over normalized time $\tau = t / T \in [0, 1]$:
$$s(\tau) = 6\tau^5 - 15\tau^4 + 10\tau^3$$
This ensures zero first and second derivatives at endpoints ($\dot{s}(0) = \dot{s}(1) = 0$, $\ddot{s}(0) = \ddot{s}(1) = 0$), completely eliminating mechanical jerk at shot boundaries.

---

### 4.2 Subsystem B — Cinematic Lighting Engine

#### 4.2.1 12 Configurable Lighting Environments
Each preset defines sky color, irradiance tint, ambient intensity, sun elevation/azimuth, sun color, and exposure compensation:

| ID | Mood Name | Sun Elev / Azimuth | Sky RGB (sRGB) | Sun/Dir RGB | Energy | Character Ambient |
|---|---|---|---|---|---|---|
| 1 | `bright_day` | $65^\circ / 135^\circ$ | `(0.42, 0.72, 1.00)` | `(1.00, 0.98, 0.92)` | 180W | `(0.85, 0.92, 1.00)` |
| 2 | `soft_afternoon`| $40^\circ / 150^\circ$ | `(0.50, 0.70, 0.95)` | `(1.00, 0.92, 0.80)` | 150W | `(0.90, 0.88, 0.82)` |
| 3 | `golden_hour` | $14^\circ / 170^\circ$ | `(0.82, 0.58, 0.40)` | `(1.00, 0.72, 0.35)` | 160W | `(1.00, 0.80, 0.55)` |
| 4 | `sunset` | $4^\circ / 185^\circ$ | `(1.00, 0.45, 0.28)` | `(1.00, 0.50, 0.20)` | 120W | `(0.95, 0.60, 0.45)` |
| 5 | `blue_hour` | $-6^\circ / 195^\circ$ | `(0.12, 0.18, 0.45)` | `(0.40, 0.50, 0.85)` | 40W | `(0.25, 0.35, 0.65)` |
| 6 | `nighttime` | $-30^\circ / 210^\circ$| `(0.04, 0.06, 0.14)` | `(0.20, 0.25, 0.45)` | 20W | `(0.15, 0.20, 0.35)` |
| 7 | `moonlit_night`| $55^\circ / 45^\circ$ | `(0.05, 0.08, 0.18)` | `(0.65, 0.80, 1.00)` | 75W | `(0.20, 0.30, 0.50)` |
| 8 | `indoor_daylight`| $50^\circ / 90^\circ$ | `(0.60, 0.75, 0.95)` | `(1.00, 0.96, 0.90)` | 130W | `(0.90, 0.92, 0.95)` |
| 9 | `warm_bedroom`| $25^\circ / 120^\circ$ | `(0.20, 0.15, 0.10)` | `(1.00, 0.78, 0.45)` | 90W | `(1.00, 0.85, 0.60)` |
| 10| `school_office`| $80^\circ / 0^\circ$ | `(0.70, 0.75, 0.80)` | `(0.92, 0.95, 1.00)` | 110W | `(0.85, 0.88, 0.92)` |
| 11| `horror` | $-10^\circ / 180^\circ$| `(0.03, 0.08, 0.06)` | `(0.20, 0.65, 0.40)` | 45W | `(0.10, 0.25, 0.18)` |
| 12| `fantasy_magical`|$35^\circ / 225^\circ$ | `(0.35, 0.15, 0.50)` | `(0.85, 0.40, 1.00)` | 120W | `(0.60, 0.30, 0.80)` |

#### 4.2.2 Dynamic 3-Point Character Rig
To ensure facial readability and edge separation across all camera shots without manual per-shot lamp tweaking:
- **Key Light:** Positioned at azimuthal angle $\phi_{\text{key}} = \phi_{\text{cam}} + 42^\circ$ and elevation $\theta_{\text{key}} = 35^\circ$ relative to the subject's head. Energy $E_{\text{key}} = 1.0 \times E_{\text{base}}$.
- **Fill Light:** Positioned at $\phi_{\text{fill}} = \phi_{\text{cam}} - 35^\circ$ and elevation $\theta_{\text{fill}} = 15^\circ$. Energy $E_{\text{fill}} = 0.38 \times E_{\text{key}}$, tinted slightly cooler or with ambient bounce.
- **Rim / Kicker Light:** Positioned behind subject at $\phi_{\text{rim}} = \phi_{\text{cam}} + 155^\circ$ and elevation $\theta_{\text{rim}} = 45^\circ$. Energy $E_{\text{rim}} = 1.25 \times E_{\text{key}}$, creating crisp specular highlights on Roblox head meshes and hair boundaries.

#### 4.2.3 Color Management & Grading
- View Transform: `AgX` (or `Filmic` for older Blender versions) with `Look = "Medium High Contrast"` for comedy/daytime, or `High Contrast` for horror/night.
- Exposure & Gamma: Controlled dynamically per shot mood.

---

### 4.3 Subsystem C — Atmospheric and Environmental VFX

#### 4.3.1 Headless Procedural Volumetric Fog
Implemented as an evaluated domain cube enclosing the set.
Shader node tree:
`ShaderNodeVolumePrincipled` connected to `MaterialOutput.Volume`:
- Density: $\rho \in [0.004, 0.025]$ (day haze: $0.005$, horror mist: $0.022$, fantasy: $0.015$).
- Anisotropy (Henyey-Greenstein phase function): $g = 0.65$ (produces pronounced forward-scattered god-rays when looking toward sun/moonlight).
- Color: Matched to ambient sky light.

#### 4.3.2 Procedural Weather Particles
1. **Rain:** Instanced elongated drop segments (length $0.4$ studs, velocity $\mathbf{v} = (0.2, -0.4, -18.0)$ studs/sec). Bounded emitter volume around active camera frustum.
2. **Snow:** Instanced tumbling hexagonal flakes with procedural sinusoidal turbulence ($\Delta x = 0.3 \sin(2.5 t)$, descent velocity $-2.8$ studs/sec).
3. **Falling Leaves:** Instanced blocky Roblox-proportional leaf planes (orange/amber/red) with gentle helical drift.

#### 4.3.3 Story-Driven Procedural VFX
1. **Sparks / Embers:** Rising glowing particles with exponential decay and turbulent upward drift ($\mathbf{v} = (\text{noise}_x, \text{noise}_y, +4.5)$ studs/sec), high emission strength ($8.0$).
2. **Magical Portal:** Swirling concentric toroid mesh with emissive rotating UV coordinates and procedural particle vortex.
3. **Energy Burst / Shockwave:** Expanding spherical wavefront with Fresnel rim emission and sudden radial particle expulsion.
4. **Impact Dust:** Hemispherical cloud puff expanding at actor feet on impact/jump landing.

---

## 5. Integration Plan with Existing Pipeline Modules

### 5.1 `pipeline/vocab.py`
Extend vocabulary sets to include:
```python
CAMERA_SHOTS = [
    "extreme_wide", "wide", "establishing", "full_body", "medium", "medium_close",
    "close_up", "extreme_close_up", "two_shot", "group", "over_shoulder", "pov", "insert"
]
CAMERA_ANGLES = ["eye", "low", "high", "top", "birds_eye", "dutch"]
CAMERA_MOVES = [
    "static", "push_in", "pull_out", "dolly_in", "dolly_out", "pan_left", "pan_right",
    "truck_left", "truck_right", "tilt_up", "tilt_down", "orbit_left", "orbit_right",
    "crane_up", "crane_down", "track", "follow", "establishing_pan", "whip_in", "crash_zoom", "shake", "handheld"
]
LIGHTING_MOODS = [
    "bright_day", "soft_afternoon", "golden_hour", "sunset", "blue_hour", "nighttime",
    "moonlit_night", "indoor_daylight", "warm_bedroom", "school_office", "horror", "fantasy_magical"
]
WEATHER_TYPES = ["clear", "rain", "snow", "falling_leaves", "windy"]
VFX_TYPES = ["fog", "haze", "sparks", "portal", "energy_burst", "smoke_puff", "light_beams"]
```

### 5.2 `pipeline/validate.py`
Add non-breaking schema validation:
- Validate `lighting.mood` if provided (defaults to `bright_day` / `sunset` / `nighttime` mapped from `dressing`).
- Validate `weather` and `vfx` tokens against supported lists.
- Cinematic Check: Verify that over-the-shoulder (OTS) and POV shots specify valid targets.
- Validate conversational line consistency between consecutive dialogue shots.

### 5.3 `pipeline/episode.py`
1. Hook `pipeline.cinematography.camera` into `shot_camera` for extended shot types, 180-degree axis handling, and raycast near-plane safety.
2. Hook `pipeline.cinematography.lighting` into `make_world` and `key_dressing` to instantiate the 12 lighting setups and 3-point character rig.
3. Hook `pipeline.cinematography.vfx` into shot initialization to build and keyframe procedural fog, weather, and story particles.

### 5.4 `pipeline/compiler.py` and `pipeline/director.py`
- Update Director system prompts with cinematography guidelines (establishing wide shots, shot reverse shot dialogue, mood lighting selection).
- Support optional structured `cinematography` block in `storyboard.json` / `shots.json` while maintaining complete backward compatibility with plain shots.

---

## 6. Performance and Thermal Safeguard Strategy

Rendering headless in Blender 5.x on production hardware requires strict controls against thermal throttling and memory leaks:
1. **Preserve Thermal Throttles:** Retain `if rendered_count % 15 == 0: time.sleep(2.0)` in `pipeline/render.py` during `motion_sheet` generation.
2. **VFX Particle Limits:**
   - Weather particles are capped at 250 instances maximum per shot.
   - Instances are created as linked duplicated mesh blocks (single mesh datablock, shared materials).
   - Emitters are local to camera view frustum rather than whole world space.
3. **Volume Shader Optimization:**
   - Use single bounding cube domains per shot.
   - Volume step rate set to 0.5 under EEVEE to maintain rapid 30-fps rendering without freezing.
4. **Memory Cleanup:** Explicit garbage collection of camera and VFX datablocks after episode compilation.

---

## 7. Automated Testing Strategy (`pipeline/test_cinematography.py`)

A comprehensive standalone test suite will validate all Phase 04 systems across 7 test domains:
1. **Shot Framing & FoV Math:** Verify distances, framing heights, safe-area headroom, and multi-character bounding spans.
2. **Conversational Axis & 180-Degree Continuity:** Verify consistent screen-space eyelines across alternating character cuts.
3. **Raycast Clearance & Obstruction Resolution:** Verify camera near-plane clearance and fallback lifts/orbits against obstacle meshes.
4. **12 Lighting Presets & 3-Point Rig:** Verify RGB colors, energy values, vector trigonometry for key/fill/rim placement, and color management.
5. **Procedural VFX & Weather Systems:** Verify deterministic particle generation, seed stability, velocity vectors, and volume shader configurations.
6. **Vocabulary & Schema Validation:** Verify all new tokens parse cleanly and validate without warnings.
7. **Backward Compatibility:** Verify that legacy shots lacking Phase 04 fields compile cleanly and yield identical baseline behavior.

---

## 8. Showcase Benchmark Scenario (`runs/upgrades/phase_04_cinematics_showcase/`)

An original, isolated showcase episode will be created and rendered to demonstrate all 10 required cinematic beats:

| Shot | ID | Shot Type | Camera Move | Lighting Mood | Weather / VFX | Narrative Action / Cinematography Beat |
|---|---|---|---|---|---|---|
| 1 | `sh01_town_establishing` | `establishing` | `establishing_pan` | `golden_hour` | `fog`, `light_beams` | **Beat 1: Establishing Wide.** Town square sunset with volumetric haze and long amber shadows. |
| 2 | `sh02_hero_arrival` | `full_body` | `track` | `golden_hour` | `falling_leaves` | **Beat 2: Medium Tracking Shot.** Theo walks in along sidewalk as leaves drift across frame. |
| 3 | `sh03_two_shot_encounter` | `two_shot` | `dolly_in` | `golden_hour` | `falling_leaves` | **Beat 3: Two-Shot Conversation.** Theo meets Chloe; establishing 180-degree dialogue line of action. |
| 4 | `sh04_ots_dialogue` | `over_shoulder` | `static` | `soft_afternoon` | `clear` | **Beat 4: Over-The-Shoulder (OTS).** Looking past Theo's shoulder at Chloe with shallow depth-of-field. |
| 5 | `sh05_closeup_reaction` | `close_up` | `push_in` | `soft_afternoon` | `clear` | **Beat 5: Close-Up Emotional Reaction.** Chloe expresses surprise; 3-point key, fill, and rim catchlights. |
| 6 | `sh06_low_angle_hero` | `low` | `tilt_up` | `blue_hour` | `haze` | **Beat 6: Low-Angle Hero Shot.** Low dramatic angle looking up at hero standing resolutely. |
| 7 | `sh07_dynamic_action` | `medium` | `crash_zoom` | `nighttime` | `sparks` | **Beat 7: Dynamic Action Push.** Fast camera punch into sudden obstacle encounter. |
| 8 | `sh08_weather_atmosphere`| `wide` | `truck_right` | `moonlit_night` | `rain` | **Beat 8: Weather Atmosphere.** Moonlit night with procedural falling rain streaks and reflections. |
| 9 | `sh09_magical_event` | `medium_close` | `orbit_left` | `fantasy_magical` | `portal`, `sparks` | **Beat 9: Story VFX Event.** Vibrant purple/cyan magical portal swirls into existence with spark bursts. |
| 10| `sh10_horror_climax` | `dutch` | `handheld` | `horror` | `fog` | **Beat 10: Horror / Mystery Mood.** Sickly green under-lit shadows, tilted Dutch angle, unsettling handheld drift. |

---

## 9. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| EEVEE Volumetric Overhead | Headless render slowdown or GPU timeout | Restrict volume domains to local bounding boxes; use optimized step rates ($0.5$); disable secondary volumetric bounces. |
| Particle Instancing in Blender 5.x Headless | Script crash if geometry nodes/particles fail in `-b` mode | Implement robust pure-Python mesh instancing with shared linked datablocks; no reliance on GUI operators or cached physics bake files. |
| Breaking Legacy Episodes | Older scripts fail schema validation | All new fields in `shots.json` (`lighting`, `weather`, `vfx`) are 100% optional; missing fields gracefully fallback to legacy dressing and baseline camera math. |
| Thermal Throttling on Long Renders | Hardware thermal throttle or render stutter | Maintain existing `render.py` throttle (`time.sleep(2.0)` every 15 frames) in motion QA; cap showcase episode to focused 10-shot demonstration. |

---
*End of Technical Specification. Implementation proceeding immediately.*
