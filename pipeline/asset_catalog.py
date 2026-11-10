"""
Asset Catalog Builder & Validator:
  - In Blender: builds all 31 modular Roblox assets from pipeline/assets/, measures exact
    dimensions/bounding boxes/ground contact from real Blender mesh geometry, saves
    public/roblox/assets/assets_library.blend, renders preview thumbnails & lineup sheet
    (public/roblox/assets_lineup.png), and writes public/roblox/asset_catalog.json.
  - In Python: validates public/roblox/asset_catalog.json schema, references, and bounds.

Usage:
    blender -b --factory-startup -t 2 --python pipeline/asset_catalog.py -- --render-previews
    python pipeline/asset_catalog.py --validate
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
PIPE = ROOT / "pipeline"
RBX = ROOT / "public" / "roblox"
ASSETS_DIR = RBX / "assets"
PREVIEWS_DIR = ASSETS_DIR / "previews"
CATALOG_JSON = RBX / "asset_catalog.json"

if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

import assets as A  # noqa: E402

REQUIRED_ASSET_KEYS = {
    "id", "category", "subcategory", "tags", "blender_ref",
    "dimensions", "bounding_box", "origin_pivot", "ground_contact",
    "collision_proxy", "allowed_surfaces", "scale_constraints",
    "attachment_points", "preview_image",
}


def build_catalog_in_blender(render_previews=False):
    import bpy
    from mathutils import Vector

    ns = {}
    for f in ("roblox_rig.py", "roblox_motions.py", "roblox_sets.py"):
        exec((PIPE / f).read_text(encoding="utf-8"), ns)

    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    try:
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = 8
        sc.eevee.use_raytracing = False
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.15
    sc.render.resolution_x = 320
    sc.render.resolution_y = 320
    sc.render.resolution_percentage = 100
    sc.world = ns["_world"]("day")

    # Key + fill lights for asset previews
    sun_ld = bpy.data.lights.new("AssetSun", "SUN")
    sun_ld.energy = 3.8
    sun_ob = bpy.data.objects.new("AssetSun", sun_ld)
    sc.collection.objects.link(sun_ob)
    sun_ob.rotation_euler = (math.radians(48), 0, math.radians(35))

    cam_d = bpy.data.cameras.new("AssetCam")
    cam_d.lens = 35
    cam_ob = bpy.data.objects.new("AssetCam", cam_d)
    sc.collection.objects.link(cam_ob)
    sc.camera = cam_ob

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    lib_rel = "public/roblox/assets/assets_library.blend"

    catalog_entries = {}
    spacing = 80.0

    for idx, (aid, spec) in enumerate(sorted(A.ASSET_DEFINITIONS.items())):
        coll_name = f"Asset_{aid}"
        coll = bpy.data.collections.new(coll_name)
        sc.collection.children.link(coll)

        # Build at origin first so local bounds are measured accurately
        root_empty, created, local_b, _ = A.instantiate_asset(ns, coll, aid, instance_name=aid, location=(0, 0, 0))
        bmin, bmax = local_b["min"], local_b["max"]
        dims = local_b["dimensions"]

        z_min = bmin[2]
        is_floating = aid == "fan_floating_platform" or "window" in aid or "shelf" in aid
        grounded = True if is_floating else (abs(z_min) <= 0.45)

        preview_rel = f"public/roblox/assets/previews/{aid}.png"
        preview_abs = ROOT / preview_rel

        if render_previews:
            # Frame the isolated asset from a 3/4 isometric-like angle at origin before parking it
            cx = (bmin[0] + bmax[0]) * 0.5
            cy = (bmin[1] + bmax[1]) * 0.5
            cz = (bmin[2] + bmax[2]) * 0.5
            span = max(dims[0], dims[1], dims[2], 3.5)
            dist = span * 1.65
            look = Vector((cx, cy, cz))
            cam_pos = look + Vector((dist * 0.58, -dist * 0.98, dist * 0.52))
            cam_ob.location = cam_pos
            cam_ob.rotation_euler = (look - cam_pos).to_track_quat("-Z", "Y").to_euler()
            try:
                sc.render.image_settings.media_type = "IMAGE"
            except Exception:
                pass
            sc.render.image_settings.file_format = "PNG"
            sc.render.filepath = str(preview_abs)
            bpy.ops.render.render(write_still=True)

        # Hide this collection while rendering subsequent previews so each thumbnail is 100% isolated
        coll.hide_render = True
        coll.hide_viewport = True

        # Park asset at grid offset in assets_library.blend so all assets coexist cleanly
        gx = ((idx % 6) + 1) * spacing
        gy = ((idx // 6) + 1) * spacing
        root_empty.location = (gx, gy, 0.0)

        catalog_entries[aid] = {
            "id": aid,
            "category": spec["category"],
            "subcategory": spec["subcategory"],
            "tags": list(spec["tags"]),
            "blender_ref": {
                "collection": coll_name,
                "root_object": aid,
                "blend_file": lib_rel,
            },
            "dimensions": dims,
            "bounding_box": {
                "min": bmin,
                "max": bmax,
            },
            "origin_pivot": [0.0, 0.0, 0.0],
            "ground_contact": {
                "z_min": z_min,
                "grounded": grounded,
                "footprint_2d": [bmin[0], bmin[1], bmax[0], bmax[1]],
            },
            "collision_proxy": {
                "type": "none" if spec["walkable"] else "aabb",
                "walkable": bool(spec["walkable"]),
                "bounds_2d": [bmin[0], bmin[1], bmax[0], bmax[1]],
                "height": dims[2],
            },
            "allowed_surfaces": list(spec["allowed_surfaces"]),
            "scale_constraints": dict(spec["scale_constraints"]),
            "attachment_points": dict(spec.get("attachment_points", {})),
            "preview_image": preview_rel,
        }

    for c in sc.collection.children:
        c.hide_render = False
        c.hide_viewport = False
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / lib_rel), compress=True)

    cat_doc = {
        "schema_version": "1.0",
        "total_assets": len(catalog_entries),
        "categories": {
            cat_name: sorted(k for k, v in catalog_entries.items() if v["category"] == cat_name)
            for cat_name in ("architecture", "environment", "interiors", "fantasy")
        },
        "assets": catalog_entries,
    }
    CATALOG_JSON.write_text(json.dumps(cat_doc, indent=2) + "\n", encoding="utf-8")
    print(f"BUILT_ASSET_CATALOG {CATALOG_JSON} ({len(catalog_entries)} assets)", flush=True)

    if render_previews:
        stitch_assets_lineup(cat_doc)
    return cat_doc


def stitch_assets_lineup(cat_doc=None):
    """Stitch all asset preview PNGs into public/roblox/assets_lineup.png."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.run(["python", str(Path(__file__).resolve()), "--stitch-lineup"], check=True)
        return RBX / "assets_lineup.png"

    if cat_doc is None:
        cat_doc = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    assets = cat_doc.get("assets", {})
    items = [(aid, info) for aid, info in sorted(assets.items()) if (ROOT / info["preview_image"]).exists()]
    if not items:
        return None

    w, h = Image.open(ROOT / items[0][1]["preview_image"]).size
    cols = 6
    rows = (len(items) + cols - 1) // cols
    lab_h = 38
    sheet = Image.new("RGB", (w * cols, (h + lab_h) * rows), (22, 24, 30))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    for i, (aid, info) in enumerate(items):
        x0 = (i % cols) * w
        y0 = (i // cols) * (h + lab_h)
        im = Image.open(ROOT / info["preview_image"]).convert("RGB")
        sheet.paste(im, (x0, y0))
        dims = info["dimensions"]
        draw.text((x0 + 6, y0 + h + 2), aid, fill=(255, 230, 90), font=font)
        draw.text((x0 + 6, y0 + h + 18), f"{info['category']} | {dims[0]:.1f}x{dims[1]:.1f}x{dims[2]:.1f}", fill=(210, 215, 225), font=font)

    out_png = RBX / "assets_lineup.png"
    sheet.save(out_png)
    print(f"WROTE_ASSETS_LINEUP {out_png}", flush=True)
    return out_png


def validate_asset_catalog(cat_path=CATALOG_JSON):
    """Validate public/roblox/asset_catalog.json schema, references, dimensions, and ground contact."""
    errs = []
    E = errs.append
    if not Path(cat_path).exists():
        return [f"Missing asset catalog file: {cat_path}"]
    try:
        doc = json.loads(Path(cat_path).read_text(encoding="utf-8"))
    except Exception as e:
        return [f"Invalid JSON in {cat_path}: {e}"]

    assets = doc.get("assets", {})
    if not assets:
        return ["asset_catalog.json has no 'assets' entries"]

    for expected_id in A.ASSET_DEFINITIONS:
        if expected_id not in assets:
            E(f"Registered asset {expected_id!r} missing from asset_catalog.json")

    for aid, info in assets.items():
        missing_k = REQUIRED_ASSET_KEYS - set(info.keys())
        if missing_k:
            E(f"{aid}: missing required keys {sorted(missing_k)}")
            continue
        if info["id"] != aid:
            E(f"{aid}: id field {info['id']!r} does not match key")
        if info["category"] not in ("architecture", "environment", "interiors", "fantasy"):
            E(f"{aid}: unknown category {info['category']!r}")
        dims = info["dimensions"]
        if not (isinstance(dims, list) and len(dims) == 3 and all(isinstance(x, (int, float)) and x > 0 for x in dims)):
            E(f"{aid}: invalid dimensions {dims!r}")
        bb = info["bounding_box"]
        for k in ("min", "max"):
            if not (isinstance(bb.get(k), list) and len(bb[k]) == 3):
                E(f"{aid}: invalid bounding_box.{k}")
        if all(isinstance(bb.get(k), list) and len(bb[k]) == 3 for k in ("min", "max")):
            for axis in range(3):
                if bb["max"][axis] <= bb["min"][axis]:
                    E(f"{aid}: bounding_box max[{axis}] <= min[{axis}]")
        ref = info["blender_ref"]
        blend_f = ROOT / ref.get("blend_file", "")
        if not blend_f.exists():
            E(f"{aid}: referenced blend_file does not exist: {blend_f}")
        sc = info["scale_constraints"]
        if not (0 < sc.get("min", 0) <= sc.get("default", 1) <= sc.get("max", 0)):
            E(f"{aid}: invalid scale_constraints {sc!r}")

    return errs


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--validate" in argv:
        errors = validate_asset_catalog()
        for e in errors:
            print("ERROR", e)
        print(f"asset catalog validation: {len(errors)} error(s)")
        sys.exit(1 if errors else 0)
    elif "--stitch-lineup" in argv:
        stitch_assets_lineup()
    else:
        build_catalog_in_blender(render_previews=("--render-previews" in argv))
