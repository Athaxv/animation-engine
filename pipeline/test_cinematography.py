"""
Comprehensive Automated Test Suite for Phase 04 Cinematography Engine.

Verifies:
1. Camera framing vocabulary, distances, safe-area headroom, OTS, POV
2. Conversational axis tracking (180-degree rule)
3. Obstacle collision detection and clearance resolution
4. Quintic S-curve smooth camera movement trajectories
5. 12 cinematic lighting environments & 3-point character rig math
6. Procedural atmospheric, weather, and story VFX kinematics
7. Vocabulary, schema validation, and 100% backward compatibility
"""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

import cinematography
from cinematography import (
    FRAME_H,
    LOOK_Z,
    FSTOP,
    AXIS_TRACKER,
    calculate_framing,
    generate_camera_trajectory,
    resolve_camera_obstruction,
    test_obstruction_pure,
    quintic_ease,
    ConversationalAxisTracker,
    Vector,
    LIGHTING_PRESETS,
    resolve_lighting_mood,
    calculate_three_point_rig,
    simulate_particle_step,
    generate_weather_particles_kinematics,
    resolve_shot_cinematography,
    validate_cinematic_continuity,
)
import vocab as V
import validate as VAL


class TestCameraIntelligence(unittest.TestCase):
    """Domain 1: Shot composition, FoV math, safe-area headroom, OTS, POV."""

    def test_shot_types_coverage(self):
        required = [
            "extreme_wide", "wide", "establishing", "full_body", "medium",
            "medium_close", "close_up", "extreme_close_up", "two_shot", "group",
            "over_shoulder", "pov", "insert"
        ]
        for st in required:
            self.assertIn(st, FRAME_H, f"Missing frame height for {st}")
            self.assertIn(st, LOOK_Z, f"Missing look height for {st}")

    def test_framing_distance_monotonically_scales(self):
        target = Vector((0.0, 0.0, 0.0))
        # Distance should decrease as we go from wide to close-up
        cam_wide, _, _ = calculate_framing("wide", target, 0.0)
        cam_med, _, _ = calculate_framing("medium", target, 0.0)
        cam_close, _, _ = calculate_framing("close_up", target, 0.0)
        cam_ecu, _, _ = calculate_framing("extreme_close_up", target, 0.0)

        dist_wide = (cam_wide - target).length
        dist_med = (cam_med - target).length
        dist_close = (cam_close - target).length
        dist_ecu = (cam_ecu - target).length

        self.assertGreater(dist_wide, dist_med)
        self.assertGreater(dist_med, dist_close)
        self.assertGreater(dist_close, dist_ecu)

    def test_two_shot_and_group_bounding(self):
        target_a = Vector((-3.0, 0.0, 0.0))
        target_b = Vector((3.0, 0.0, 0.0))
        pts = [target_a, target_b]

        cam_pos, look_pos, _ = calculate_framing(
            "two_shot", target_a, 0.0, group_positions=pts
        )
        # Look point should be centered between the two characters
        self.assertAlmostEqual(look_pos.x, 0.0, delta=0.2)
        # Camera distance should accommodate the 6-stud span
        self.assertGreater((cam_pos - look_pos).length, 8.0)

    def test_over_the_shoulder_positioning(self):
        # Actor A talking to Actor B
        pos_a = Vector((0.0, 0.0, 0.0))
        pos_b = Vector((0.0, 6.0, 0.0))

        cam_pos, look_pos, _ = calculate_framing(
            "over_shoulder", pos_a, 0.0, secondary_target_pos=pos_b
        )
        # Camera should be placed behind Actor A (y < 0) and elevated
        self.assertLess(cam_pos.y, pos_a.y)
        self.assertGreater(cam_pos.z, 4.0)
        # Look point should be near Actor B
        self.assertAlmostEqual(look_pos.y, pos_b.y, delta=0.5)

    def test_character_pov_positioning(self):
        pos_actor = Vector((2.0, 3.0, 0.0))
        yaw = 0.0  # Facing -Y in Blender engine convention

        cam_pos, look_pos, _ = calculate_framing("pov", pos_actor, yaw)
        # Camera must be at eye level (Z ~ 4.3)
        self.assertAlmostEqual(cam_pos.z, 4.3, delta=0.2)
        self.assertAlmostEqual(cam_pos.x, pos_actor.x, delta=0.2)
        # Look point should be ahead of camera in facing direction
        self.assertLess(look_pos.y, cam_pos.y)

    def test_camera_angles(self):
        target = Vector((0.0, 0.0, 0.0))
        cam_low, _, _ = calculate_framing("medium", target, 0.0, angle="low")
        cam_eye, _, _ = calculate_framing("medium", target, 0.0, angle="eye")
        cam_high, _, _ = calculate_framing("medium", target, 0.0, angle="high")
        cam_top, _, _ = calculate_framing("medium", target, 0.0, angle="birds_eye")

        self.assertLess(cam_low.z, cam_eye.z)
        self.assertGreater(cam_high.z, cam_eye.z)
        self.assertGreater(cam_top.z, cam_high.z)

    def test_dutch_angle_roll(self):
        target = Vector((0.0, 0.0, 0.0))
        _, _, roll_eye = calculate_framing("medium", target, 0.0, angle="eye")
        _, _, roll_dutch = calculate_framing("medium", target, 0.0, angle="dutch")

        self.assertEqual(roll_eye, 0.0)
        self.assertAlmostEqual(roll_dutch, math.radians(10.0), delta=0.01)


class TestConversationalAxis(unittest.TestCase):
    """Domain 2: Conversational axis & 180-degree rule tracking."""

    def test_axis_side_consistency(self):
        tracker = ConversationalAxisTracker()
        pos_a = Vector((-2.0, 0.0, 0.0))
        pos_b = Vector((2.0, 0.0, 0.0))
        cam_pos = Vector((0.0, -8.0, 3.5))

        side1 = tracker.get_or_set_axis_side("Theo", "Chloe", pos_a, pos_b, cam_pos)
        # Swapping order should return the same consistent half-space side
        side2 = tracker.get_or_set_axis_side("Chloe", "Theo", pos_b, pos_a)
        self.assertEqual(side1, side2)


class TestObstacleCollisionResolution(unittest.TestCase):
    """Domain 3: Raycast obstruction & clearance cone."""

    def test_unobstructed_path(self):
        cam = Vector((0.0, -10.0, 4.0))
        look = Vector((0.0, 0.0, 3.5))
        dist = test_obstruction_pure(cam, look, obstacles=[])
        self.assertIsNone(dist)

    def test_obstacle_hit_detection(self):
        cam = Vector((0.0, -10.0, 3.5))
        look = Vector((0.0, 0.0, 3.5))
        # Obstacle cube blocking line of sight at y = -5
        obstacle = {"min": (-2.0, -6.0, 0.0), "max": (2.0, -4.0, 8.0)}
        dist = test_obstruction_pure(cam, look, obstacles=[obstacle])
        self.assertIsNotNone(dist)
        self.assertAlmostEqual(dist, 4.0, delta=0.5)

    def test_clearance_resolution_pull_forward(self):
        cam = Vector((0.0, -10.0, 3.5))
        look = Vector((0.0, 0.0, 3.5))
        obstacle = {"min": (-20.0, -6.0, 0.0), "max": (20.0, -4.0, 20.0)}

        def mock_ray_test(a, b):
            return test_obstruction_pure(b, a, obstacles=[obstacle])

        resolved_pos = resolve_camera_obstruction(cam, look, ray_test_fn=mock_ray_test)
        # Since vertical and lateral orbits are blocked by the wide wall, camera must pull in front of blocker
        self.assertGreater(resolved_pos.y, -4.5)


class TestCameraMovementCurves(unittest.TestCase):
    """Domain 4: Quintic smoothstep easing and camera trajectories."""

    def test_quintic_ease_endpoints_and_monotonicity(self):
        self.assertEqual(quintic_ease(0.0), 0.0)
        self.assertEqual(quintic_ease(1.0), 1.0)
        self.assertEqual(quintic_ease(0.5), 0.5)

        # Monotonically advancing
        prev = -1.0
        for i in range(21):
            val = quintic_ease(i / 20.0)
            self.assertGreaterEqual(val, prev)
            prev = val

    def test_trajectory_push_in_and_pull_out(self):
        cam = Vector((0.0, -10.0, 3.5))
        look = Vector((0.0, 0.0, 3.5))
        dur = 3.0

        push_keys = generate_camera_trajectory("push_in", cam, look, dur, num_samples=5)
        self.assertEqual(len(push_keys), 5)
        dist_start = (push_keys[0][1] - look).length
        dist_end = (push_keys[-1][1] - look).length
        self.assertLess(dist_end, dist_start)

        pull_keys = generate_camera_trajectory("pull_out", cam, look, dur, num_samples=5)
        dist_pull_start = (pull_keys[0][1] - look).length
        dist_pull_end = (pull_keys[-1][1] - look).length
        self.assertGreater(dist_pull_end, dist_pull_start)

    def test_trajectory_crane_up_and_down(self):
        cam = Vector((0.0, -10.0, 3.5))
        look = Vector((0.0, 0.0, 3.5))
        dur = 2.5

        crane_keys = generate_camera_trajectory("crane_up", cam, look, dur, num_samples=5)
        self.assertGreater(crane_keys[-1][1].z, crane_keys[0][1].z)

        crane_down = generate_camera_trajectory("crane_down", cam, look, dur, num_samples=5)
        self.assertLess(crane_down[-1][1].z, crane_down[0][1].z)


class TestLightingEngine(unittest.TestCase):
    """Domain 5: 12 lighting setups & 3-point character rig math."""

    def test_all_12_presets_defined(self):
        expected_presets = [
            "bright_day", "soft_afternoon", "golden_hour", "sunset", "blue_hour", "nighttime",
            "moonlit_night", "indoor_daylight", "warm_bedroom", "school_office", "horror", "fantasy_magical"
        ]
        self.assertEqual(len(LIGHTING_PRESETS), 12)
        for p in expected_presets:
            self.assertIn(p, LIGHTING_PRESETS)
            cfg = LIGHTING_PRESETS[p]
            self.assertEqual(len(cfg["sky_rgb"]), 3)
            self.assertEqual(len(cfg["light_rgb"]), 3)
            self.assertGreater(cfg["sun_energy"], 0.0)

    def test_legacy_dressing_resolution(self):
        self.assertEqual(resolve_lighting_mood("day"), "bright_day")
        self.assertEqual(resolve_lighting_mood("sunset"), "sunset")
        self.assertEqual(resolve_lighting_mood("night"), "nighttime")
        self.assertEqual(resolve_lighting_mood(None), "bright_day")

    def test_three_point_rig_trigonometry(self):
        cam = Vector((0.0, -10.0, 4.0))
        look = Vector((0.0, 0.0, 3.5))

        rig = calculate_three_point_rig(cam, look, mood_name="golden_hour")
        self.assertIn("key", rig)
        self.assertIn("fill", rig)
        self.assertIn("rim", rig)

        key = rig["key"]
        fill = rig["fill"]
        rim = rig["rim"]

        # Key should be to subject's right (positive x relative to camera-to-look vector)
        self.assertGreater(key["pos"].x, 0.0)
        # Fill should be to subject's left (negative x)
        self.assertLess(fill["pos"].x, 0.0)
        # Rim should be behind subject (positive y)
        self.assertGreater(rim["pos"].y, 0.0)

        # Energy ratios: Fill ~38% of key, Rim ~125% of key
        self.assertAlmostEqual(fill["energy"] / key["energy"], 0.38, delta=0.05)
        self.assertAlmostEqual(rim["energy"] / key["energy"], 1.25, delta=0.05)


class TestProceduralVFXKinematics(unittest.TestCase):
    """Domain 6: Procedural weather & atmospheric particle simulation."""

    def test_deterministic_simulation(self):
        pos = (1.0, 2.0, 10.0)
        vel = (0.2, -0.4, -20.0)
        t = 1.5
        seed = 12345

        res1 = simulate_particle_step(pos, vel, t, seed, turbulence=0.5)
        res2 = simulate_particle_step(pos, vel, t, seed, turbulence=0.5)
        self.assertEqual(res1, res2)

    def test_weather_particle_generation(self):
        bounds = ((-20.0, -20.0, 0.0), (20.0, 20.0, 15.0))
        count = 30
        dur = 2.0

        rain = generate_weather_particles_kinematics("rain", bounds, count, dur, seed=42)
        self.assertEqual(len(rain), count)
        for p in rain:
            # Rain must fall steeply down (vz < -15)
            self.assertLess(p["velocity"][2], -15.0)

        snow = generate_weather_particles_kinematics("snow", bounds, count, dur, seed=42)
        self.assertEqual(len(snow), count)
        for p in snow:
            # Snow falls gently (vz between -1 and -4)
            self.assertGreater(p["velocity"][2], -5.0)
            self.assertLess(p["velocity"][2], -1.0)


class TestVocabularyAndSchema(unittest.TestCase):
    """Domain 7: Engine vocabulary, validate.py integration, and backward compatibility."""

    def test_vocab_cinematography_tokens(self):
        self.assertIn("establishing", V.CAMERA_SHOTS)
        self.assertIn("full_body", V.CAMERA_SHOTS)
        self.assertIn("pov", V.CAMERA_SHOTS)
        self.assertIn("birds_eye", V.CAMERA_ANGLES)
        self.assertIn("dolly_in", V.CAMERA_MOVES)
        self.assertIn("truck_left", V.CAMERA_MOVES)
        self.assertIn("crane_up", V.CAMERA_MOVES)
        self.assertIn("golden_hour", V.LIGHTING_MOODS)
        self.assertIn("horror", V.LIGHTING_MOODS)
        self.assertIn("rain", V.WEATHER_TYPES)
        self.assertIn("portal", V.VFX_TYPES)

    def test_legacy_episode_validation_zero_errors(self):
        ep_path = ROOT / "episodes" / "test_engine"
        res = VAL.validate_detailed(ep_path)
        self.assertEqual(len(res["errors"]), 0, f"Errors found in test_engine: {res['errors']}")

    def test_phase_03_showcase_validation_zero_errors(self):
        ep_path = ROOT / "runs" / "upgrades" / "phase_03_motion_showcase"
        res = VAL.validate_detailed(ep_path)
        self.assertEqual(len(res["errors"]), 0, f"Errors found in phase 03 showcase: {res['errors']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
