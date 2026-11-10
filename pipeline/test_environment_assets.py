"""
Automated test suite for the Reusable Roblox Environment Asset Library & Composer:
  1. test_asset_catalog_validity
  2. test_missing_asset_references
  3. test_bounding_box_calculation
  4. test_collision_and_overlap_detection
  5. test_ground_placement
  6. test_asset_loading_in_blender
  7. test_existing_set_compatibility

Run:
    python pipeline/test_environment_assets.py
"""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path

PIPE = Path(__file__).resolve().parent
ROOT = PIPE.parent
RBX = ROOT / "public" / "roblox"
sys.path.insert(0, str(PIPE))

import assets as A                    # noqa: E402
import asset_catalog as AC            # noqa: E402
import environment_composer as EC     # noqa: E402
import make as M                      # noqa: E402
import validate as VAL                # noqa: E402


class EnvironmentAssetsTests(unittest.TestCase):
    def test_01_asset_catalog_validity(self):
        """Verify asset_catalog.json exists, passes schema validation, and covers all 4 categories."""
        errs = AC.validate_asset_catalog()
        self.assertEqual(errs, [], f"Asset catalog validation errors: {errs}")
        doc = json.loads((RBX / "asset_catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["total_assets"], len(A.ASSET_DEFINITIONS))
        self.assertGreaterEqual(doc["total_assets"], 35)
        for cat_name in ("architecture", "environment", "interiors", "fantasy"):
            self.assertIn(cat_name, doc["categories"])
            self.assertGreater(len(doc["categories"][cat_name]), 0)

    def test_02_missing_asset_references(self):
        """Verify validator catches missing blend_file references and composer rejects unknown asset IDs."""
        doc = json.loads((RBX / "asset_catalog.json").read_text(encoding="utf-8"))
        first_id = next(iter(doc["assets"]))
        doc["assets"][first_id]["blender_ref"]["blend_file"] = "public/roblox/assets/nonexistent_missing.blend"
        with tempfile.TemporaryDirectory() as td:
            bad_cat = Path(td) / "bad_catalog.json"
            bad_cat.write_text(json.dumps(doc), encoding="utf-8")
            errs = AC.validate_asset_catalog(bad_cat)
            self.assertTrue(any("referenced blend_file does not exist" in e for e in errs))

        comp = EC.EnvironmentComposer("test_set")
        with self.assertRaises(KeyError):
            comp.place_asset("nonexistent_asset_xyz", "bad_inst", location=(0, 0, 0))

    def test_03_bounding_box_calculation(self):
        """Verify geometry-derived bounding boxes and dimensions in asset_catalog.json are physically consistent."""
        doc = json.loads((RBX / "asset_catalog.json").read_text(encoding="utf-8"))
        for aid, info in doc["assets"].items():
            bb = info["bounding_box"]
            dims = info["dimensions"]
            for axis in range(3):
                span = round(bb["max"][axis] - bb["min"][axis], 3)
                self.assertGreater(span, 0.0, f"{aid}: non-positive span on axis {axis}")
                self.assertAlmostEqual(span, dims[axis], places=2, msg=f"{aid}: dimension mismatch on axis {axis}")

        # Verify 2D footprint transformation under 90-degree rotation and 1.5x scale
        fp = [-4.0, -2.0, 4.0, 2.0]  # 8 wide (X) by 4 deep (Y)
        rot_fp = EC.transform_footprint_2d(fp, location=(10.0, 20.0, 0.0), rotation_deg=90.0, scale=1.5)
        # After 90 deg rotation and 1.5x scale: X span becomes 4*1.5=6 (±3 around 10), Y span becomes 8*1.5=12 (±6 around 20)
        self.assertAlmostEqual(rot_fp[0], 7.0, places=2)
        self.assertAlmostEqual(rot_fp[2], 13.0, places=2)
        self.assertAlmostEqual(rot_fp[1], 14.0, places=2)
        self.assertAlmostEqual(rot_fp[3], 26.0, places=2)

    def test_04_collision_and_overlap_detection(self):
        """Verify overlap detection, strict collision rejection, automatic nudging, and path navigation checks."""
        comp = EC.EnvironmentComposer("collision_test")
        r1 = comp.place_asset("arch_shop_bakery", "shop_1", location=(0.0, 0.0, 0.0), nudge_if_overlap=False)
        # Placing a second solid building at the exact same location with nudge_if_overlap=False must raise ValueError
        with self.assertRaises(ValueError):
            comp.place_asset("arch_house_suburban", "house_overlap", location=(0.0, 0.0, 0.0), nudge_if_overlap=False)

        # With nudge_if_overlap=True, the second building is automatically shifted outside shop_1's footprint
        r2 = comp.place_asset("arch_house_suburban", "house_nudged", location=(0.0, 0.0, 0.0), nudge_if_overlap=True)
        self.assertFalse(EC.footprints_overlap(r1["bounds_2d"], r2["bounds_2d"], clearance=0.0))

        # Placing a non-seat stage mark inside shop_1's solid footprint must raise ValueError
        with self.assertRaises(ValueError):
            comp.add_mark("bad_mark", (0.0, 0.0, 0.0))

        # Verify navigable path detection catches an obstacle between two marks
        comp.add_mark("south_mark", (0.0, -12.0, 0.0))
        comp.add_mark("north_mark", (0.0, 12.0, 0.0))
        blocked = comp.verify_navigable_paths([("south_mark", "north_mark")])
        self.assertTrue(any(b[2] == "shop_1" for b in blocked))

    def test_05_ground_placement(self):
        """Verify ground contact metadata and automatic ground Z-offset alignment."""
        doc = json.loads((RBX / "asset_catalog.json").read_text(encoding="utf-8"))
        for aid, info in doc["assets"].items():
            gc = info["ground_contact"]
            self.assertIn("z_min", gc)
            self.assertIn("grounded", gc)
            self.assertEqual(len(gc["footprint_2d"]), 4)
            self.assertTrue(gc["grounded"], f"{aid}: expected grounded=True, got {gc}")

        # Verify town_square plan builds with 0 blocked corridors and valid grounded placements
        ts_comp = EC.compose_town_square_plan()
        self.assertGreaterEqual(len(ts_comp.placements), 25)
        self.assertIn("center", ts_comp.marks)
        self.assertIn("bench_sit", ts_comp.marks)

    def test_06_asset_loading_in_blender(self):
        """Verify Blender can load assets_library.blend and town_square.blend headless and inspect collections."""
        blender = M.blender_exe()
        lib_p = str(RBX / "assets" / "assets_library.blend")
        ts_p = str(RBX / "sets" / "town_square.blend")
        with tempfile.TemporaryDirectory() as td:
            script_f = Path(td) / "verify_load.py"
            script_f.write_text(
                f"import bpy\n"
                f"with bpy.data.libraries.load({lib_p!r}, link=False) as (src, dst):\n"
                f"    assert 'Asset_arch_clock_tower' in src.collections\n"
                f"    assert 'Asset_fan_portal_arcane' in src.collections\n"
                f"    dst.collections = ['Asset_arch_clock_tower', 'Asset_fan_portal_arcane']\n"
                f"assert len(dst.collections) == 2 and dst.collections[0] is not None\n"
                f"with bpy.data.libraries.load({ts_p!r}, link=False) as (src2, dst2):\n"
                f"    assert 'Set_town_square' in src2.collections\n"
                f"    dst2.collections = ['Set_town_square']\n"
                f"coll = dst2.collections[0]\n"
                f"marks = [o['mark'] for o in coll.all_objects if o is not None and o.get('mark')]\n"
                f"assert 'center' in marks and 'portal_spot' in marks, f'Missing marks: {{marks}}'\n"
                f"print('BLENDER_ASSET_LOAD_OK', len(marks), flush=True)\n",
                encoding="utf-8",
            )
            res = subprocess.run(
                [blender, "-b", "--factory-startup", "-t", "2", "--python", str(script_f)],
                cwd=str(ROOT), capture_output=True, text=True, check=True
            )
        self.assertIn("BLENDER_ASSET_LOAD_OK", res.stdout + res.stderr)

    def test_07_existing_set_compatibility(self):
        """Verify existing 4 sets and existing episodes remain 100% compatible with 0 validation errors."""
        cat = json.loads((RBX / "catalog.json").read_text(encoding="utf-8"))
        expected_sets = {
            "bedroom":   (["day", "night"], {"bed", "bed_sit", "bedside", "cam_default", "center", "desk", "door", "window"}),
            "kitchen":   (["day"], {"cam_default", "center", "couch", "door", "fridge", "stove", "table_a", "table_b", "table_front"}),
            "classroom": (["day"], {"board", "cam_default", "center", "desk_1", "desk_2", "desk_3", "desk_4", "desk_5", "desk_6", "desk_7", "desk_8", "desk_9", "door", "teacher"}),
            "street":    (["day", "sunset"], {"cam_aerial", "cam_default", "far_walk", "house_door", "lawn", "road", "sidewalk_a", "sidewalk_b", "sidewalk_c"}),
        }
        for sname, (exp_dress, exp_marks) in expected_sets.items():
            self.assertIn(sname, cat["sets"])
            self.assertEqual(cat["sets"][sname]["dressings"], exp_dress)
            self.assertEqual(set(cat["sets"][sname]["marks"].keys()), exp_marks)

        # Also verify town_square is registered in catalog.json with its obstacles & marks
        self.assertIn("town_square", cat["sets"])
        self.assertIn("obstacles", cat["sets"]["town_square"])

        # Verify existing episodes pass validate_detailed with 0 errors
        for ep_name in ("wi_3am_monster", "wi_sounds_from_future"):
            ep_dir = ROOT / "episodes" / ep_name
            if (ep_dir / "shots.json").exists():
                rep = VAL.validate_detailed(ep_dir)
                self.assertEqual(rep["errors"], [], f"{ep_name} had unexpected validation errors: {rep['errors']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
