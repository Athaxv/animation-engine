"""
Scan the asset library and write public/roblox/catalog.json (sets, dressings, marks, cast).
The episode builder, the validator and vocab.py all read that file.

    blender -b --factory-startup --python pipeline/catalog.py

Run it again whenever a set or a character file changes.
"""
import bpy, json, math, os
from pathlib import Path

ROOT = Path(r"C:\Users\User\Desktop\blender roblox tiktoks")
RBX = ROOT / "public" / "roblox"

# seat height (top of the seat, studs above the mark) for marks where characters sit
SEATS = {"table_a": 2.0, "table_b": 2.0, "couch": 2.4, "bed_sit": 2.6}


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
            seat = SEATS.get(m, 2.0 if m.startswith("desk_") else None)
            marks[m] = {"pos": [round(p.x, 2), round(p.y, 2), round(p.z, 2)],
                        "facing": round(math.degrees(o.rotation_euler.z)) % 360}
            if seat is not None:
                marks[m]["seat"] = seat
    dress = coll.get("dressings", "day").split(",")
    for o in list(coll.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(coll)
    return name, {"dressings": dress, "marks": dict(sorted(marks.items()))}


def main():
    cat = {"sets": {}, "characters": []}
    for p in sorted((RBX / "sets").glob("*.blend")):
        n, info = scan_set(p)
        cat["sets"][n] = info
        print("set", n, len(info["marks"]), "marks", info["dressings"])
    cat["characters"] = sorted(p.stem for p in (RBX / "characters").glob("*.blend"))
    out = RBX / "catalog.json"
    out.write_text(json.dumps(cat, indent=1), encoding="utf-8")
    print("wrote", out)


main()
