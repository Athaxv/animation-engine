"""
Render helper, run on a built episode file:
    blender -b <ep>/<ep>.blend --python pipeline/render.py -- raw          preview|final
    blender -b <ep>/<ep>.blend --python pipeline/render.py -- sheet                      # one still per shot -> render/sheet/
    blender -b <ep>/<ep>.blend --python pipeline/render.py -- motion_sheet               # start/mid/end stills + 3D telemetry -> render/motion_sheet/
    blender -b <ep>/<ep>.blend --python pipeline/render.py -- thumb        <frame>       # full-res still -> render/thumb.png

preview = 540x960, few samples (fast check). final = 1080x1920, more samples, raytraced reflections.
"""
import bpy, os, sys, json, math, time

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mode = argv[0] if argv else "raw"
sc = bpy.context.scene
r = sc.render
ep = os.path.dirname(bpy.data.filepath)
out_dir = os.path.join(ep, "render")
os.makedirs(out_dir, exist_ok=True)

QUALITY = {
    "preview": dict(pct=50, samples=12, rt=False),
    "final":   dict(pct=100, samples=48, rt=True),
    "sheet":   dict(pct=25, samples=8, rt=False),
    "thumb":   dict(pct=100, samples=64, rt=True),
}

FACE_NAMES = [
    "smile", "grin", "worried", "shocked",
    "laugh", "sleep", "angry", "sad",
    "neutral", "blink", "talk", "smirk",
    "surprised", "confident", "cry", "nervous",
]
BODY_BONES = ("hips", "spine", "head", "upper_arm.L", "upper_arm.R", "upper_leg.L", "upper_leg.R")


def apply(q):
    r.resolution_percentage = q["pct"]
    try:
        sc.eevee.taa_render_samples = q["samples"]
        sc.eevee.use_raytracing = q["rt"]
        sc.eevee.shadow_pool_size = "1024"
    except Exception:
        pass
    r.use_motion_blur = False


def still(frame, path):
    try:
        r.image_settings.media_type = 'IMAGE'
    except Exception:
        pass
    r.image_settings.file_format = 'PNG'
    sc.frame_set(frame)
    r.filepath = path
    bpy.ops.render.render(write_still=True)


def _sample_scene_telemetry(cam):
    """
    Capture evaluated 3D telemetry at the current frame:
      - Root world coordinates & heading (degrees)
      - Head tip world coordinates
      - Pose bone Euler rotations (degrees) for all 7 R6 body bones
      - Face decal index & name
      - Visible hand props & placed world props
      - Camera world location & rotation (degrees)
    """
    bpy.context.view_layer.update()
    chars = {}
    for ob in bpy.data.objects:
        if ob is not None and ob.get("is_roblox_rig") and ob.location.z > -100:
            root_pb = ob.pose.bones.get("root") if ob.pose else None
            head_pb = ob.pose.bones.get("head") if ob.pose else None
            rw = (ob.matrix_world @ root_pb.head) if root_pb else ob.matrix_world.translation
            hw = (ob.matrix_world @ head_pb.tail) if head_pb else rw
            heading_deg = round(math.degrees(root_pb.rotation_euler.z), 2) if root_pb else 0.0
            bone_rots = {}
            if ob.pose:
                for bname in BODY_BONES:
                    pb = ob.pose.bones.get(bname)
                    if pb is not None:
                        bone_rots[bname] = [round(math.degrees(a), 2) for a in pb.rotation_euler]
            f_idx = int(ob.get("face", 0))
            f_name = FACE_NAMES[f_idx] if 0 <= f_idx < len(FACE_NAMES) else f"face_{f_idx}"
            chars[ob.name] = {
                "root": [round(rw.x, 3), round(rw.y, 3), round(rw.z, 3)],
                "head": [round(hw.x, 3), round(hw.y, 3), round(hw.z, 3)],
                "heading_deg": heading_deg,
                "bone_rotations_deg": bone_rots,
                "scale": round(float(ob.scale.x), 3),
                "face": f_idx,
                "face_name": f_name,
            }

    visible_hand_props = {}
    visible_world_props = []
    prop_coll = bpy.data.collections.get("EP_Props")
    if prop_coll is not None:
        for po in prop_coll.objects:
            if po is None or po.parent is not None and not po.parent.get("is_roblox_rig"):
                continue
            # Check visibility of prop root or its children
            children = [po] + list(po.children_recursive)
            is_vis = any(not c.hide_render for c in children) and po.scale.x > 0.05
            if not is_vis:
                continue
            if po.parent and po.parent.get("is_roblox_rig"):
                cname = po.parent.name
                visible_hand_props.setdefault(cname, []).append(po.name)
            elif po.name.startswith("s") and "_place" in po.name:
                visible_world_props.append({
                    "name": po.name,
                    "scale": round(float(po.scale.x), 3),
                    "loc": [round(po.location.x, 3), round(po.location.y, 3), round(po.location.z, 3)],
                })

    c_pos = cam.matrix_world.translation if cam else None
    c_rot = [round(math.degrees(a), 2) for a in cam.rotation_euler] if cam else None
    return {
        "camera_loc": [round(c_pos.x, 3), round(c_pos.y, 3), round(c_pos.z, 3)] if c_pos else None,
        "camera_rot_deg": c_rot,
        "characters": chars,
        "visible_hand_props": visible_hand_props,
        "visible_world_props": visible_world_props,
    }


if mode == "raw":
    q = argv[1] if len(argv) > 1 else "preview"
    apply(QUALITY[q])
    r.filepath = os.path.join(out_dir, f"raw_{q}.mp4")
    print(f"RENDER raw {q} {sc.frame_start}-{sc.frame_end} -> {r.filepath}", flush=True)
    bpy.ops.render.render(animation=True)
    print("DONE", r.filepath, flush=True)
elif mode == "sheet":
    apply(QUALITY["sheet"])
    sheet = os.path.join(out_dir, "sheet")
    os.makedirs(sheet, exist_ok=True)
    marks = sorted(sc.timeline_markers, key=lambda m: m.frame)
    ends = [m.frame for m in marks[1:]] + [sc.frame_end + 1]
    info = []
    for m, e in zip(marks, ends):
        f = (m.frame + e) // 2 if len(argv) < 2 else min(e - 1, m.frame + int(argv[1]))
        p = os.path.join(sheet, f"{m.name}.png")
        still(f, p)
        info.append({"id": m.name, "frame": f, "png": p})
    with open(os.path.join(sheet, "sheet.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1)
    print("DONE sheet", len(info), flush=True)
elif mode == "motion_sheet":
    apply(QUALITY["sheet"])
    ms_dir = os.path.join(out_dir, "motion_sheet")
    os.makedirs(ms_dir, exist_ok=True)
    marks = sorted(sc.timeline_markers, key=lambda m: m.frame)
    ends = [m.frame for m in marks[1:]] + [sc.frame_end + 1]
    only_ids = set(argv[1].split(",")) if len(argv) > 1 and argv[1] else None
    info = []
    rendered_count = 0
    for m, e in zip(marks, ends):
        if only_ids and m.name not in only_ids:
            continue
        f_start = min(e - 1, m.frame + 1)
        f_mid = (m.frame + e) // 2
        f_end = max(f_start, e - 2)
        samples = {}
        for tag, fr in (("start", f_start), ("mid", f_mid), ("end", f_end)):
            p = os.path.join(ms_dir, f"{m.name}_{tag}.png")
            still(fr, p)
            samples[tag] = {
                "frame": fr,
                "png": p,
                "telemetry": _sample_scene_telemetry(m.camera),
            }
            rendered_count += 1
            if rendered_count % 15 == 0:
                time.sleep(2.0)
        info.append({
            "id": m.name,
            "start_frame": m.frame,
            "end_frame": e - 1,
            "samples": samples,
        })
    with open(os.path.join(ms_dir, "motion_sheet.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    print("DONE motion_sheet", len(info), flush=True)
elif mode == "thumb":
    apply(QUALITY["thumb"])
    still(int(argv[1]) if len(argv) > 1 else 1, os.path.join(out_dir, "thumb.png"))
    print("DONE thumb", flush=True)
