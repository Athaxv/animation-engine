"""
Bake every Phase 2 character identity into its own reusable blend file.

    blender -b --factory-startup -t 2 --python pipeline/build_characters.py
    blender -b --factory-startup -t 2 --python pipeline/build_characters.py -- aiko sable
    python pipeline/build_characters.py --json-only      # registry json, no Blender

Outputs
-------
``public/roblox/characters/<Name>.blend``       one collection per identity, the
                                                same contract ``episode.py``
                                                appends from
``public/roblox/character_identities.json``     the registry Mirror
``public/roblox/characters/build_report.json``  per-identity R6 / clipping metrics

No rendering happens here, so the thermal rule (<=150 frames per process) is
irrelevant: this is a pure geometry build.

``--json-only`` works both ways: as plain Python (no bpy) and under Blender,
because argv is only read after the ``--`` separator.
Headless full bake:
    blender -b --factory-startup -t 2 --python pipeline/build_characters.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else os.getcwd()
PIPE = os.path.join(ROOT, "pipeline")
if PIPE not in sys.path:
    sys.path.insert(0, PIPE)

import characters  # noqa: E402

OUT_DIR = os.path.join(ROOT, "public", "roblox", "characters")
REPORT = os.path.join(OUT_DIR, "build_report.json")


def rig_namespace():
    ns = {"__name__": "roblox_rig_runtime"}
    with open(os.path.join(PIPE, "roblox_rig.py"), encoding="utf-8") as fh:
        exec(fh.read(), ns)
    return ns


def build_identity(ns, cid, name=None):
    """Build one identity's rig at the origin. Legacy identities resolve via PRESETS."""
    ident = characters.get(cid)
    name = name or ident["name"]
    if ident.get("legacy_preset"):
        spec = dict(ns["PRESETS"][ident["legacy_preset"]])
        spec["face"] = ident["face_style"]
        return ns["build_character"](name, location=(0, 0, 0), **spec)
    return ns["build_character"](name, location=(0, 0, 0), **characters.identity_to_rig_kwargs(cid))


def main(ids=None):
    import bpy
    from characters import checks

    os.makedirs(OUT_DIR, exist_ok=True)
    characters.write_json()
    print("WROTE_IDENTITIES_JSON", characters.IDENTITY_JSON)

    ids = ids or sorted(characters.CHARACTER_IDENTITIES)
    ns = rig_namespace()
    report = {}

    for i, cid in enumerate(ids, 1):
        ident = characters.get(cid)
        name = ident["name"]
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = build_identity(ns, cid, name)
        bpy.context.view_layer.update()

        m = checks.measure(rig)
        acc = checks.accessory_measure(rig, ident.get("accessories") or [])

        n_meshes = m["mesh_objects"]
        out = os.path.join(OUT_DIR, f"{name}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)

        report[cid] = {
            "name": name,
            "blend": os.path.relpath(out, ROOT).replace("\\", "/"),
            "legacy_preset": ident.get("legacy_preset"),
            "hair": (ident.get("hair") or {}).get("style") or (ns["PRESETS"][ident["legacy_preset"]].get("hair_style") if ident.get("legacy_preset") else None),
            "outfit": (ident.get("clothing") or {}).get("outfit", "none"),
            "accessories": list(ident.get("accessories") or []),
            "face_style": ident["face_style"],
            "personality": (ident.get("personality") or {}).get("id"),
            "r6_bones_missing": m["missing_bones"],
            "is_roblox_rig": m["is_roblox_rig"],
            "decal_material": m["decal_material"],
            "mesh_objects": n_meshes,
            "head_dims": m["head_dims"],
            "torso_dims": m["torso_dims"],
            "hair_vertices": m["hair_vertices"],
            "hair_eye_hits": m["hair_eye_hits"],
            "hair_mouth_hits": m["hair_mouth_hits"],
            "accessory_checks": acc,
            "accessory_ok": all(v["ok"] for v in acc.values()),
            "ok": bool(m["hair_ok"] and not m["missing_bones"] and all(v["ok"] for v in acc.values())),
        }
        print(f"[{i:2d}/{len(ids)}] {cid:9s} {name:8s} meshes={n_meshes:3d} "
              f"hair={report[cid]['hair']:12s} {'OK' if report[cid]['ok'] else 'CHECK'}")

    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": "2.0", "total": len(report), "characters": report}, fh, indent=2)
    bad = [k for k, v in report.items() if not v["ok"]]
    print("WROTE_REPORT", REPORT)
    print(f"BUILT {len(report)} identities, {len(bad)} need attention: {bad}")
    return report


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--json-only" in argv:
        print("WROTE_IDENTITIES_JSON", characters.write_json())
        sys.exit(0)
    wanted = [a for a in argv if not a.startswith("-")] or None
    main(wanted)
