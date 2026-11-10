"""
Scan the asset library and write public/roblox/catalog.json (sets, dressings, marks, obstacles, cast, asset_library).
The episode builder, the validator and vocab.py all read that file.

    blender -b --factory-startup --python pipeline/catalog.py

Run it again whenever a set or a character file changes.
"""
import bpy, json, math, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
RBX = ROOT / "public" / "roblox"

# seat height (top of the seat, studs above the mark) for marks where characters sit
SEATS = {"table_a": 2.0, "table_b": 2.0, "couch": 2.4, "bed_sit": 2.6, "bench_sit": 2.15}


def scan_set(path):
    name = path.stem
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == f"Set_{name}"]
    coll = dst.collections[0]
    bpy.context.scene.collection.children.link(coll)
    bpy.context.view_layer.update()
    marks = {}
    for o in coll.all_objects:
        if o is not None and o.get("mark"):
            p = o.matrix_world.translation
            m = o["mark"]
            seat = o.get("seat")
            if seat is None:
                seat = SEATS.get(m, 2.0 if m.startswith("desk_") else None)
            marks[m] = {
                "pos": [round(p.x, 2), round(p.y, 2), round(p.z, 2)],
                "facing": round(math.degrees(o.rotation_euler.z)) % 360,
            }
            if seat is not None:
                marks[m]["seat"] = round(float(seat), 2)
    dress = coll.get("dressings", "day").split(",")
    info = {"dressings": dress, "marks": dict(sorted(marks.items()))}
    obs_raw = coll.get("obstacles_json")
    if obs_raw:
        try:
            info["obstacles"] = json.loads(obs_raw)
        except Exception:
            pass
    for o in list(coll.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)
    return name, info


def main():
    cat = {"sets": {}, "characters": []}
    for p in sorted((RBX / "sets").glob("*.blend")):
        n, info = scan_set(p)
        cat["sets"][n] = info
        print("set", n, len(info["marks"]), "marks", info["dressings"])
    cat["characters"] = sorted(p.stem for p in (RBX / "characters").glob("*.blend"))
    asset_cat_file = RBX / "asset_catalog.json"
    if asset_cat_file.exists():
        try:
            ac = json.loads(asset_cat_file.read_text(encoding="utf-8"))
            cat["asset_library"] = {
                "catalog_file": "public/roblox/asset_catalog.json",
                "blend_file": "public/roblox/assets/assets_library.blend",
                "total_assets": ac.get("total_assets", 0),
                "categories": ac.get("categories", {}),
            }
        except Exception:
            pass
    out = RBX / "catalog.json"
    out.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("wrote", out)


main()
