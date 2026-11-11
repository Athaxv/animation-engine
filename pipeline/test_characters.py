"""
Phase 2 character-system tests.

Two modes, same file:

    python pipeline/test_characters.py                                    # registry/schema only
    blender -b --factory-startup -t 2 --python pipeline/test_characters.py  # + geometry

The schema half needs no Blender at all (it only reads the datasets and the
``vocab`` cheat-sheet sources). The geometry half builds real rigs and measures
them with ``characters/checks.py``:

  * R6 rig compatibility      every bone present, head/torso present, decal material
  * face visibility           all 16 expressions resolve to a decal cell, eyes clear
  * hair clipping             no hair vertex in front of the painted eye/mouth band
  * accessory intersections   zone-aware clearance (head_top / face / body)
  * clothing consistency      the same identity rebuilds to an identical signature
  * identity persistence      signatures are deterministic and match the exported JSON
  * preset compatibility      the eight legacy presets are unchanged by Phase 2 defaults

Blender always exits non-zero from ``--python`` scripts here, so judge the run by
the final ``RESULT:`` line, not the shell exit code.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else os.getcwd()
PIPE = os.path.join(ROOT, "pipeline")
for p in (ROOT, PIPE):
    if p not in sys.path:
        sys.path.insert(0, p)

import characters  # noqa: E402
import vocab  # noqa: E402

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
    return bool(ok)


def group(title):
    print(f"\n{title}")


def rig_namespace():
    ns = {"__name__": "roblox_rig_runtime"}
    with open(os.path.join(PIPE, "roblox_rig.py"), encoding="utf-8") as fh:
        exec(fh.read(), ns)
    return ns


def build_identity(ns, cid, name=None, location=(0, 0, 0)):
    ident = characters.get(cid)
    name = name or ident["name"]
    if ident.get("legacy_preset"):
        spec = dict(ns["PRESETS"][ident["legacy_preset"]])
        spec["face"] = ident["face_style"]
        return ns["build_character"](name, location=location, **spec)
    return ns["build_character"](name, location=location,
                                 **characters.identity_to_rig_kwargs(cid))


# ===================================================================== schema
def test_schema():
    group("SCHEMA  (no Blender required)")
    ids = sorted(characters.CHARACTER_IDENTITIES)
    check("registry/has-identities", len(ids) >= 5, f"found {len(ids)}")

    errs = characters.validate_all()
    check("registry/validate-all", not errs, "; ".join(errs[:4]))

    # required keys on every identity
    missing = {}
    for cid in ids:
        ident = characters.CHARACTER_IDENTITIES[cid]
        gap = characters.identities.REQUIRED_IDENTITY_KEYS - set(ident)
        if gap:
            missing[cid] = sorted(gap)
    check("registry/required-keys", not missing, str(missing)[:200])

    # ids / names unique
    check("registry/ids-unique", len(set(ids)) == len(ids))
    disp = [characters.CHARACTER_IDENTITIES[c]["name"] for c in ids]
    check("registry/names-unique", len(set(disp)) == len(disp),
          str([n for n in disp if disp.count(n) > 1]))

    # every referenced asset exists in the asset registries
    bad = []
    for cid in ids:
        ident = characters.CHARACTER_IDENTITIES[cid]
        hair = (ident.get("hair") or {}).get("style")
        cloth = ident.get("clothing") or {}
        if hair is not None and hair not in characters.HAIR_ALL_STYLES:
            bad.append(f"{cid}:hair={hair}")
        if cloth.get("outfit", "none") not in characters.OUTFITS:
            bad.append(f"{cid}:outfit={cloth.get('outfit')}")
        if cloth.get("print", "none") not in characters.PRINTS:
            bad.append(f"{cid}:print={cloth.get('print')}")
        for acc in ident.get("accessories") or ():
            if acc not in characters.ACCESSORY_REGISTRY:
                bad.append(f"{cid}:acc={acc}")
        if ident.get("head_style") not in characters.HEAD_STYLES:
            bad.append(f"{cid}:head={ident.get('head_style')}")
        if ident.get("face_style") not in characters.FACE_STYLES:
            bad.append(f"{cid}:face={ident.get('face_style')}")
    check("registry/assets-resolve", not bad, ", ".join(bad)[:300])

    # every accessory declares a known zone
    bad = [a for a, v in characters.ACCESSORY_REGISTRY.items() if v[0] not in characters.ACCESSORY_ZONES]
    check("assets/accessory-zones", not bad, ", ".join(bad))

    # hair catalogue is complete: legacy + new, no duplicates
    legacy = set(characters.HAIR_LEGACY_STYLES)
    allh = characters.HAIR_ALL_STYLES
    check("assets/hair-no-duplicates", len(set(allh)) == len(allh))
    check("assets/hair-includes-legacy", legacy <= set(allh), str(sorted(legacy - set(allh))))
    check("assets/hair-has-bald", "bald" in allh)

    # faces match the atlas order in roblox_rig
    ns_face = [e.value for e in vocab._assign(vocab.PIPE / "roblox_rig.py", "FACE_NAMES").elts]
    check("faces/match-atlas", list(characters.FACE_STYLES) == ns_face,
          f"identities={list(characters.FACE_STYLES)} atlas={ns_face}")

    # personalities only use words the engine understands
    poses, actions = set(vocab.POSES), set(vocab.ACTIONS)
    bad = []
    for pid, p in characters.PERSONALITIES.items():
        for key, pool in (("default_pose", poses), ("idle_action", actions)):
            val = p.get(key)
            if val is not None and val not in pool:
                bad.append(f"{pid}:{key}={val}")
    check("personality/words-in-vocab", not bad, ", ".join(bad))

    # identity -> rig kwargs is filtered and deterministic
    leaked, nondet = [], []
    for cid in ids:
        kw = characters.identity_to_rig_kwargs(cid)
        if kw is None:
            continue
        extra = set(kw) - set(characters.RIG_KWARGS)
        if extra:
            leaked.append(f"{cid}:{sorted(extra)}")
        if characters.identity_to_rig_kwargs(cid) != kw:
            nondet.append(cid)
    check("kwargs/filtered-to-rig", not leaked, "; ".join(leaked)[:200])
    check("kwargs/deterministic", not nondet, ", ".join(nondet))

    # signatures are stable and the new identities are visually distinct
    sigs, unstable = {}, []
    for cid in ids:
        a, b = characters.appearance_signature(cid), characters.appearance_signature(cid)
        if a != b:
            unstable.append(cid)
        sigs[cid] = a
    check("identity/signature-stable", not unstable, ", ".join(unstable))
    new_sigs = [sigs[c] for c in ids if not characters.CHARACTER_IDENTITIES[c].get("legacy_preset")]
    dups = len(new_sigs) - len(set(new_sigs))
    check("identity/new-signatures-distinct", dups == 0, f"{dups} duplicate(s)")

    # legacy identities stay bound to the original presets
    legacy_ids = [c for c in ids if characters.CHARACTER_IDENTITIES[c].get("legacy_preset")]
    check("preset/legacy-count", len(legacy_ids) == len(vocab.PRESETS),
          f"{len(legacy_ids)} legacy identities vs {len(vocab.PRESETS)} presets")
    check("preset/legacy-names-match",
          {characters.CHARACTER_IDENTITIES[c]["legacy_preset"] for c in legacy_ids} == set(vocab.PRESETS),
          str(sorted({characters.CHARACTER_IDENTITIES[c]["legacy_preset"] for c in legacy_ids})))

    # the exported document is plain JSON
    doc = characters.to_json_document()
    try:
        round_trip = json.loads(json.dumps(doc))
        check("registry/json-serialisable", len(round_trip.get("identities", {})) == len(ids))
    except (TypeError, ValueError) as exc:
        round_trip = {}
        check("registry/json-serialisable", False, str(exc))

    # the on-disk mirror, when present, must agree with the code (compare the
    # serialised forms: tuples legitimately become lists on disk)
    path = characters.IDENTITY_JSON
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            on_disk = json.load(fh)
        same = (on_disk.get("identities", {}) == round_trip.get("identities", {})
                and bool(on_disk.get("identities")))
        check("registry/json-matches-disk", same, "re-run pipeline/build_characters.py --json-only")
    else:
        check("registry/json-matches-disk", True, "skipped: no exported json yet")


# =================================================================== geometry
def test_geometry():
    from characters import checks

    ns = rig_namespace()
    ids = sorted(characters.CHARACTER_IDENTITIES)

    group("R6 RIG COMPATIBILITY")
    bad = []
    body_scaled = []
    for i, cid in enumerate(ids, 1):
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = build_identity(ns, cid)
        bpy.context.view_layer.update()
        rep = checks.rig_report(rig)
        problems = []
        if rep["missing_bones"]:
            problems.append(f"bones={rep['missing_bones']}")
        if not rep["is_roblox_rig"]:
            problems.append("not-a-rig")
        if not rep["head"]:
            problems.append("no-head")
        if not rep["decal_material"]:
            problems.append("no-face-decal")
        if rep["face_prop"] is None:
            problems.append("no-face-prop")
        if problems:
            bad.append(f"{cid}({','.join(problems)})")
        scale = float(characters.get(cid).get("proportions", {}).get("body_scale", 1.0))
        if abs(scale - 1.0) > 1e-6:
            got = float(getattr(rig, "scale", (1, 1, 1))[0])
            rec = float(rig.get("body_scale", 0.0) or 0.0)
            if abs(got - scale) > 1e-4 or abs(rec - scale) > 1e-4:
                body_scaled.append(f"{cid}(scale={got:.3f}, rec={rec:.3f}, want={scale:.3f})")
    check(f"rig/all-{len(ids)}-identities", not bad, "; ".join(bad)[:400])
    check("rig/body-scale-applied-once", not body_scaled, "; ".join(body_scaled)[:300])

    group("FACE VISIBILITY  (16 expressions)")
    atlas = list(ns["FACE_NAMES"])
    bad = []
    for fname in atlas:
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = ns["build_character"]("F", face=fname)
        bpy.context.view_layer.update()
        rep = checks.rig_report(rig)
        idx = rig.get("face", -1)
        if not rep["decal_material"] or idx != atlas.index(fname):
            bad.append(f"{fname}(idx={idx},decal={rep['decal_material']})")
    check("face/every-expression-has-decal", not bad, "; ".join(bad)[:300])

    # a bald head must never occlude its own painted face
    bpy.ops.wm.read_homefile(use_empty=True)
    rig = ns["build_character"]("F", hair_style="bald")
    bpy.context.view_layer.update()
    occ = checks.head_occlusion(checks.hair_points(rig))
    check("face/bald-head-clear", occ["ok"], str(occ))

    group("HAIR CLIPPING  (17 styles)")
    bad = []
    for style in characters.HAIR_ALL_STYLES:
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = ns["build_character"]("H", hair_style=style)
        bpy.context.view_layer.update()
        m = checks.measure(rig)
        if m["hair_eye_hits"] or m["hair_mouth_hits"]:
            bad.append(f"{style}(eye={m['hair_eye_hits']},mouth={m['hair_mouth_hits']})")
    check(f"hair/all-{len(characters.HAIR_ALL_STYLES)}-styles-clear", not bad, "; ".join(bad)[:300])

    # legacy hats sit above the same band
    bad = []
    for hat in ("crown", "police", "cap"):
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = ns["build_character"]("H", hat=hat)
        bpy.context.view_layer.update()
        occ = checks.head_occlusion(checks.collection_points(rig, ("Hat", "Crown")))
        if not occ["ok"]:
            bad.append(f"{hat}(eye={occ['eye_hits']},mouth={occ['mouth_hits']})")
    check("hair/legacy-hats-clear", not bad, "; ".join(bad)[:200])

    group("ACCESSORY INTERSECTIONS  (16 pieces, 3 zones)")
    bad = []
    zones_seen = set()
    for acc in characters.ACCESSORY_REGISTRY:
        zone = characters.ACCESSORY_REGISTRY[acc][0]
        zones_seen.add(zone)
        kwargs = dict(hair_style="bald" if zone in ("head_top", "face") else "short",
                      accessories=(acc,))
        bpy.ops.wm.read_homefile(use_empty=True)
        rig = ns["build_character"]("A", **kwargs)
        bpy.context.view_layer.update()
        res = checks.accessory_measure(rig, [acc])[acc]
        if not res["ok"]:
            bad.append(f"{acc}({zone}:{ {k: v for k, v in res.items() if k != 'ok'} })")
    check(f"accessory/all-{len(characters.ACCESSORY_REGISTRY)}-clear", not bad, "; ".join(bad)[:400])
    check("accessory/zones-covered", zones_seen == set(characters.ACCESSORY_ZONES), str(sorted(zones_seen)))

    group("CLOTHING CONSISTENCY")
    bad = []
    for outfit in characters.OUTFITS:
        bpy.ops.wm.read_homefile(use_empty=True)
        a = ns["build_character"]("C", outfit=outfit, print_kind="bolt")
        bpy.context.view_layer.update()
        sig_a = checks.mesh_signature(a)
        bpy.ops.wm.read_homefile(use_empty=True)
        b = ns["build_character"]("C", outfit=outfit, print_kind="bolt", location=(7.0, -3.0, 0.0))
        bpy.context.view_layer.update()
        sig_b = checks.mesh_signature(b)
        if sig_a != sig_b:
            bad.append(outfit)
    check(f"clothing/all-{len(characters.OUTFITS)}-outfits-reproducible", not bad, ", ".join(bad))

    # building other characters in between must not leak state
    bpy.ops.wm.read_homefile(use_empty=True)
    first = checks.mesh_signature(ns["build_character"]("C", outfit="hoodie", accessories=("scarf",)))
    ns["build_character"]("Other", hair_style="mohawk", outfit="dress")
    bpy.context.view_layer.update()
    second = checks.mesh_signature(ns["build_character"]("C", outfit="hoodie", accessories=("scarf",)))
    check("clothing/no-cross-character-leak", first == second)

    group("IDENTITY PERSISTENCE")
    bad = []
    for cid in ids:
        bpy.ops.wm.read_homefile(use_empty=True)
        r1 = build_identity(ns, cid)
        bpy.context.view_layer.update()
        s1 = checks.mesh_signature(r1)
        bpy.ops.wm.read_homefile(use_empty=True)
        r2 = build_identity(ns, cid, location=(4.0, 5.0, 0.0))
        bpy.context.view_layer.update()
        s2 = checks.mesh_signature(r2)
        if s1 != s2:
            bad.append(cid)
    check("identity/rebuild-identical", not bad, ", ".join(bad))

    group("PRESET COMPATIBILITY  (8 original characters)")
    phase2_defaults = dict(outfit="none", print_kind="none", print_color=None,
                           accessories=(), body_scale=1.0, head_style="round")
    legacy_ids = [c for c in ids if characters.CHARACTER_IDENTITIES[c].get("legacy_preset")]
    bad = []
    for cid in legacy_ids:
        preset = characters.CHARACTER_IDENTITIES[cid]["legacy_preset"]
        base = dict(ns["PRESETS"][preset])
        bpy.ops.wm.read_homefile(use_empty=True)
        a = ns["build_character"]("P", **base)
        bpy.context.view_layer.update()
        sig_a = checks.mesh_signature(a)
        bpy.ops.wm.read_homefile(use_empty=True)
        b = ns["build_character"]("P", **dict(base, **phase2_defaults))
        bpy.context.view_layer.update()
        sig_b = checks.mesh_signature(b)
        if sig_a != sig_b:
            bad.append(preset)
    check(f"preset/all-{len(legacy_ids)}-unchanged-by-defaults", not bad, ", ".join(bad))

    # the baked blends, when present, contain the character
    missing = []
    out_dir = os.path.join(ROOT, "public", "roblox", "characters")
    for cid in ids:
        name = characters.CHARACTER_IDENTITIES[cid]["name"]
        path = os.path.join(out_dir, name + ".blend")
        if not os.path.exists(path):
            missing.append(name)
    check("bake/every-identity-has-blend", not missing,
          f"{len(missing)} missing: {missing[:5]}")


def main():
    print("=" * 72)
    print(f"PHASE 2 CHARACTER TESTS   blender={HAVE_BPY}")
    print("=" * 72)
    test_schema()
    if HAVE_BPY:
        test_geometry()
    else:
        print("\nGEOMETRY  (skipped: run this file with Blender for rig/clipping tests)")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print("\n" + "-" * 72)
    if failed:
        for n, d in failed:
            print(f"  FAILED  {n}  {d}")
    print(f"RESULT: {passed}/{len(RESULTS)} passed, {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
