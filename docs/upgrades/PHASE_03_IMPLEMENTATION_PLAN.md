# Phase 03 Implementation Plan: Roblox Animation Intelligence & Motion System

> **Target Version:** Blender 5.2.3 LTS (`D:\blender.exe`) / Python 3.13 & 3.14  
> **Repository:** `d:\ai-video\ROBLOX ANIMATION`  
> **Date:** 2026-11-11  
> **Prerequisites:** Phase 01 (`pipeline/assets/`, `environment_composer.py`), Phase 02 (`pipeline/characters/`, `character_identities.json`)

---

## 1. System Audit & Baseline Capabilities

### Existing Capabilities
1. **R6 Rigid Skeleton:** Single-bone arms (`upper_arm.L`, `upper_arm.R`) and legs (`upper_leg.L`, `upper_leg.R`). No elbows or knees; joints are shoulders, hips, waist (`spine`), and `neck`/`head`.
2. **Current Locomotion:** `walk` and `run` in [`pipeline/roblox_motions.py`](file:///d:/ai-video/ROBLOX%20ANIMATION/pipeline/roblox_motions.py) linearly interpolate root position between start and end. Limbs swing with quarter-phase sinusoidal rotation. No acceleration/deceleration, no turning anticipation/lean, and no ground-relative foot planting verification (moonwalking occurs on non-standard speeds).
3. **Current Poses & Transitions:** Poses are keyed instantaneously or with naive 4-frame linear ramps (`pose(rig, prev, fs - 4); pose(rig, p, fs)`). No ease-in/ease-out curves, no action priority system, and no recovery phases.
4. **Current Props:** Built via [`pipeline/props.py`](file:///d:/ai-video/ROBLOX%20ANIMATION/pipeline/props.py), statically parented to `upper_arm.R` or placed in world coordinates. No dynamic parent switching (e.g. World $\to$ Hand, Hand $\to$ World, or Hand A $\to$ Hand B).
5. **Current Camera System:** Fixed framing heights (`FRAME_H = 1.9 .. 40.0`), static target offsets, ray-cast occlusion unblocking via `scene.ray_cast()`. No vertical social media UI safe-area accounting (TikTok/Shorts top 15% / bottom 22%), and no dynamic dual-character framing during physical handoffs or hugs.
6. **Current QA:** 3-point motion evaluation in [`pipeline/visual_qa.py`](file:///d:/ai-video/ROBLOX%20ANIMATION/pipeline/visual_qa.py) computes pixel MAD, camera displacement, and character root/bone deltas. Does not measure foot sliding, hand-to-prop alignment distance, character interaction proximity, or action continuity.

### Core Constraints
- **Preserve the R6 Skeleton:** Never add bones, elbows, or knees. R6 rigid character geometry is the core aesthetic.
- **Backwards Compatibility:** Every existing episode (`test_engine`, `wi_sounds_from_future`, etc.) and preset must build and validate with 0 errors.
- **Thermal-Safe Headless Rendering:** Maintain render batch throttling (`if count % 15 == 0: time.sleep(2.0)`).
- **Deterministic & Code-Driven:** All motions, kinematics, and interactions must be purely programmatic and reproducible.

---

## 2. Architecture of Phase 03: `pipeline/motion/`

To maintain clean modularity (matching `pipeline/assets/` and `pipeline/characters/`), all motion intelligence is isolated in a new package:

```
pipeline/motion/
├── __init__.py          # Unified entry points, action/pose schemas, version metadata
├── blending.py          # Ease curves, pose slerp/lerp, action priority & recovery phases
├── kinematics.py        # Analytical R6 single-bone IK (aiming shoulder/hip toward target 3D points)
├── locomotion.py        # Accelerated/decelerated locomotion, direction-aware turning, foot planting
├── interactions.py      # Prop pickup, drop, pass, catch, doors, push/pull
├── choreography.py      # Multi-character sequences (approach, greet, hug, handoff, group celebrate)
└── navigation.py        # Graph-based waypoint pathfinding around asset_catalog.json obstacles
```

---

## 3. Step-by-Step Implementation Roadmap

### Step 1: Motion Blending & Transition Core (`pipeline/motion/blending.py`)
- Implement easing functions: `linear`, `ease_in_quad`, `ease_out_quad`, `ease_in_out_cubic`, `smoothstep`.
- Implement R6 Euler angle interpolation with shortest-arc unwrapping (preventing 360° flip spins).
- Implement an **Action Priority Matrix**:
  - `EMERGENCY / CUTSCENE` (priority 100): `fall_back`, `poof`, `pop_in` (non-interruptible).
  - `REACTION` (priority 75): `surprise_hop`, `jump`, `shiver` (interrupts locomotion/gestures).
  - `INTERACTION` (priority 60): `pickup`, `pass_prop`, `handshake`, `hug` (synchronized, non-interruptible during contact).
  - `LOCOMOTION` (priority 50): `walk_to`, `run_to`, `turn`.
  - `GESTURE` (priority 25): `wave`, `nod`, `talk`, `celebrate`.
  - `IDLE` (priority 0): `idle`, `relaxed`.
- Add recovery phase generation: smooth return to base pose over $4\text{--}8$ frames after one-shot completion.

### Step 2: Analytical R6 Kinematics (`pipeline/motion/kinematics.py`)
- Single-bone spherical forward/inverse kinematics for R6 arms:
  - Given shoulder pivot $S$ and target point $P$ in character local space, solve for Euler rotation $(rx, ry, rz)$ that directs the arm axis from $S$ to $P$.
  - Constrain rotations within anatomical R6 limits:
    - Arm elevation $rx \in [-180^\circ, +45^\circ]$;
    - Arm abduction/adduction $rz \in [-90^\circ, +90^\circ]$.
- Head look-at kinematics: solve head pitch and yaw to track target characters or props within realistic neck limits ($|\text{pitch}| \le 35^\circ, |\text{yaw}| \le 60^\circ$).

### Step 3: Natural Locomotion & Foot Planting (`pipeline/motion/locomotion.py`)
- Replace sudden linear root motion with an S-curve profile:
  - Phase 1: Acceleration / start-step ($0 \to v_{\max}$ over 6 frames).
  - Phase 2: Steady-state cruise with stride frequency matching linear velocity ($v = \text{stride} \times f$).
  - Phase 3: Deceleration / stop-plant ($v_{\max} \to 0$ over 6 frames).
- Foot planting calculation:
  - Calculate instantaneous ground velocity of the stance foot during swing phase.
  - Modulate root Z bobbing and spine lean proportionally to speed.
- Natural turning:
  - Pre-turn torso/head anticipation (head leads by 2 frames).
  - Bank/lean into turns ($2^\circ\text{--}5^\circ$).

### Step 4: Reusable Interactions & Dynamic Props (`pipeline/motion/interactions.py`)
- Dynamic prop parenting:
  - Support prop state machine: `WORLD` $\leftrightarrow$ `HAND_R(A)` $\leftrightarrow$ `HAND_R(B)` $\leftrightarrow$ `WORLD`.
  - Create Blender constraint or matrix baking helper for seamless hand-off without positional jumping.
- Core interaction behaviors:
  - `pickup_object`: Character bends waist, reaches arm to prop, snaps parent to hand, returns to upright hold.
  - `drop_object`: Releases prop at current hand position with gravity drop to ground contact.
  - `pass_and_catch`: Character A extends arm with prop toward Character B; Character B extends receiving arm; prop swaps parent at contact frame; both recover to hold/relaxed.
  - `handshake`: Mutual arm extension to shared midpoint, 3-cycle shake rhythm, release and recovery.
  - `hug`: Mutual approach to $1.8\text{--}2.0$ studs, coordinated arm wrap, hold, release.
  - `open_door`: Hand reaches to door handle, door rotates open on hinge, character steps through.

### Step 5: Multi-Character Choreography (`pipeline/motion/choreography.py`)
- High-level coordinator that accepts paired commands in shot definitions:
  - `choreography: "pass_prop"` with `{giver: "A", receiver: "B", prop: "cookie", at: 1.5}`.
  - `choreography: "handshake"` with `{char_a: "A", char_b: "B", at: 2.0}`.
  - `choreography: "hug"` with `{char_a: "A", char_b: "B", at: 1.0}`.
- Automatically calculates facing angles, mutual approach distances, and synchronized contact frames.

### Step 6: Obstacle-Aware Navigation & Environment Integration (`pipeline/motion/navigation.py`)
- Integrate with `pipeline/environment_composer.py` and `asset_catalog.json`.
- Construct a 2D navigation visibility graph connecting stage marks around solid obstacle AABB footprints.
- Support multi-waypoint walking paths for characters moving around buildings, fountains, or walls.

### Step 7: Dynamic Camera Improvements (`pipeline/episode.py`)
- Vertical social media safe-area compliance:
  - Keep primary actor faces within vertical bounds $y \in [0.22, 0.85]$ (avoiding TikTok bottom caption box and top overlay).
- Multi-character framing:
  - When characters interact (handshake, pass, hug), camera smoothly focuses on the mutual interaction bounding box and ensures the held prop remains visible.
- Dynamic tracking:
  - Smooth camera follow with damping during actor locomotion.

### Step 8: QA Telemetry & Test Suite (`pipeline/visual_qa.py`, `pipeline/test_motion.py`)
- Extend `_sample_scene_telemetry()`:
  - Hand-to-prop contact distance.
  - Actor-to-actor interaction distance.
  - Foot sliding index (delta between foot stance position and root displacement).
  - Action transition smoothness score.
- Unit and integration tests covering:
  - Blending easing math and priority resolution.
  - Kinematic shoulder aiming accuracy.
  - Locomotion speed/foot-plant consistency.
  - Navigation path obstacle avoidance.
  - Compatibility with legacy presets and existing episodes.

### Step 9: Showcase Benchmark (`runs/upgrades/phase_03_motion_showcase/`)
- Build complete test episode script demonstrating:
  1. Aiko and Zephyr approach each other along natural acceleration paths.
  2. Natural stop and face-to-face turn.
  3. Aiko picks up a prop (`gem` or `gift`) from a pedestal.
  4. Aiko passes the object to Zephyr.
  5. Zephyr catches the object with synchronized contact.
  6. Zephyr reacts with celebratory emotion.
  7. Warm handshake or hug interaction.
  8. Dynamic camera tracking maintaining safe-area composition.
- Render: Contact sheet, motion sheet, technical QA report, preview MP4.

### Step 10: Performance Profiling & Documentation
- Profile scene assembly and rendering times before and after Phase 03.
- Document all deliverables in `docs/upgrades/PHASE_03_ROBLOX_ANIMATION.md`.

---

## 4. Verification Criteria
1. `python pipeline/test_motion.py` passes 100% of tests.
2. All existing episodes (`test_engine`, `wi_sounds_from_future`) validate with 0 errors and 0 regressions.
3. Showcase scene renders cleanly with verified thermal-safe throttling.
4. Visual QA report demonstrates measured foot planting, prop contact accuracy, and smooth bone interpolation.
