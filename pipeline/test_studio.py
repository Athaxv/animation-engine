"""
Automated test suite for the upgraded AI-Directed Roblox Animation Studio pipeline.

    python pipeline/test_studio.py
"""
import copy, json, os, py_compile, subprocess, sys, tempfile, unittest
from pathlib import Path

PIPE = Path(__file__).resolve().parent
ROOT = PIPE.parent
sys.path.insert(0, str(PIPE))

import vocab as V       # noqa: E402
import validate as VA   # noqa: E402
import compiler as CO   # noqa: E402
import director as DI   # noqa: E402
import make as MK       # noqa: E402
import visual_qa as VQ  # noqa: E402


class StudioPipelineTests(unittest.TestCase):
    def test_01_py_compile_all_modules(self):
        """All pipeline/*.py files compile without syntax errors."""
        for py_file in sorted(PIPE.glob("*.py")):
            py_compile.compile(str(py_file), doraise=True)

    def test_02_blender_discovery_without_env_var(self):
        """blender_exe() discovers D:\\blender.exe via PATH / fallback when BLENDER env var is unset."""
        old = os.environ.pop("BLENDER", None)
        try:
            exe = MK.blender_exe()
            self.assertTrue(Path(exe).is_file(), f"Resolved Blender does not exist: {exe}")
            self.assertTrue(exe.lower().endswith("blender.exe"))
        finally:
            if old is not None:
                os.environ["BLENDER"] = old

    def test_03_python_only_stages_do_not_require_blender(self):
        """Running --only validate,direct,compile succeeds even if BLENDER is not invoked."""
        env = dict(os.environ)
        env.pop("BLENDER", None)
        p = subprocess.run(
            [sys.executable, str(PIPE / "make.py"), str(ROOT / "episodes" / "wi_3am_monster"), "--only", "validate,direct,compile"],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_04_missing_inputs_give_actionable_errors(self):
        """Stage dependency check fails with a clear ERROR message instead of FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "ep_missing"
            ep.mkdir()
            (ep / "shots.json").write_text(json.dumps({
                "episode": "ep_missing", "format": "what_if", "title": "Test", "shots": [
                    {"id": "s01", "set": "street", "text": "Hello world test shot.", "camera": {"shot": "medium"}, "cast": []}
                ]
            }), encoding="utf-8")
            p = subprocess.run(
                [sys.executable, str(PIPE / "make.py"), str(ep), "--only", "build"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("ERROR: Stage 'build' requires", p.stdout + p.stderr)
            self.assertNotIn("Traceback", p.stdout + p.stderr)

    def test_05_director_and_compiler_preserve_narration_and_pass_validation(self):
        """Director + Compiler preserve shot IDs, narration, and speakers while resolving all warnings."""
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            for ep_name in ("wi_3am_monster", "wi_sounds_from_future"):
                src_ep = ROOT / "episodes" / ep_name
                ep = Path(tmp) / ep_name
                ep.mkdir(parents=True, exist_ok=True)
                for fn in ("shots.json", "script.md", "timing.json"):
                    if (src_ep / fn).exists():
                        shutil.copy2(src_ep / fn, ep / fn)
                before = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
                before_texts = [(s["id"], s.get("speaker", "narrator"), s["text"]) for s in before["shots"]]

                sb = DI.run_director(ep, compile_out=True, use_llm=False)
                self.assertEqual(len(sb["storyboard"]), len(before_texts))

                after = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
                after_texts = [(s["id"], s.get("speaker", "narrator"), s["text"]) for s in after["shots"]]
                self.assertEqual(before_texts, after_texts)

                errs, warns = VA.validate(ep)
                self.assertEqual(errs, [])
                self.assertEqual(warns, [])

    def test_06_compiler_rejects_invented_vocabulary(self):
        """validate_storyboard rejects unknown sets, marks, actions, props, or SFX."""
        ep = ROOT / "episodes" / "wi_3am_monster"
        sb = json.loads((ep / "storyboard.json").read_text(encoding="utf-8"))
        bad = copy.deepcopy(sb)
        bad["storyboard"][0]["location"] = "mars_colony"
        errs = CO.validate_storyboard(bad, "wi_3am_monster")
        self.assertTrue(any("mars_colony" in e for e in errs))

        bad2 = copy.deepcopy(sb)
        c0 = bad2["storyboard"][0]["characters"][0]
        bad2["storyboard"][0]["character_actions"][c0]["action"] = "backflip_360"
        errs2 = CO.validate_storyboard(bad2, "wi_3am_monster")
        self.assertTrue(any("backflip_360" in e for e in errs2))

    def test_07_cinematic_validator_catches_overlap_and_idle_action(self):
        """validate_detailed warns on overlapping R6 character positions and idle action narration."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp) / "wi_overlap_test"
            ep.mkdir()
            shots = {
                "episode": "wi_overlap_test",
                "format": "what_if",
                "title": "Overlap Test",
                "shots": [
                    {
                        "id": f"s0{i}",
                        "set": "street",
                        "speaker": "narrator",
                        "text": "Theo sprinted down the road as fast as he could.",
                        "camera": {"shot": "two_shot", "angle": "eye", "move": "static", "target": "Theo"},
                        "cast": [
                            {"name": "Theo", "mark": "sidewalk_b", "dx": 0.0, "pose": "stand", "face": "smile", "action": "idle"},
                            {"name": "Max", "mark": "sidewalk_b", "dx": 0.5, "pose": "stand", "face": "smile", "action": "idle"},
                        ],
                    }
                    for i in range(1, 7)
                ],
            }
            (ep / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
            res = VA.validate_detailed(ep)
            self.assertEqual(res["errors"], [])
            w_text = "\n".join(res["warnings"])
            self.assertIn("R6 clearance", w_text)
            self.assertIn("narration describes action", w_text)
            self.assertIn("consecutive shot repeats identical camera composition", w_text)

    def test_08_gemini_missing_key_stops_without_silent_fallback(self):
        """When GEMINI_API_KEY is missing, --llm --provider gemini fails explicitly instead of falling back."""
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            src_ep = ROOT / "episodes" / "wi_3am_monster"
            ep = Path(tmp) / "wi_3am_monster"
            ep.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_ep / "shots.json", ep / "shots.json")
            env = dict(os.environ)
            env.pop("GEMINI_API_KEY", None)
            # Only run this assertion if GEMINI_API_KEY is not in .env
            if not DI._read_config_var("GEMINI_API_KEY"):
                p = subprocess.run(
                    [sys.executable, str(PIPE / "director.py"), str(ep), "--llm", "--provider", "gemini"],
                    cwd=ROOT, env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("GEMINI_API_KEY is not configured", p.stdout + p.stderr)
                exec_json = json.loads((ep / "director_execution.json").read_text(encoding="utf-8"))
                self.assertEqual(exec_json["provider"], "gemini")
                self.assertFalse(exec_json["api_call_succeeded"])
                self.assertFalse(exec_json["fallback_used"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
