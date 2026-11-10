"""
Episode assembler: shots.json + timing.json -> one Blender scene, one timeline.

Run inside Blender (fresh/empty file is best):
    ns = {"EPISODE_DIR": r".../episodes/ep01_blue_lies"}
    exec(open(r".../pipeline/assemble.py").read(), ns)
    ns["assemble"]()                      # builds everything, saves <episode>/<episode>.blend

What it does
  * appends the needed sets (public/sets) side by side, and characters (public/characters)
  * per shot: places characters on marks (absent ones are parked underground), faces them,
    keys poses + breathing, expressions + changes, actions, lip sync from word timings,
    blinks, blue-skin fx, props, light dressing, world color
  * one camera per shot (framing from shot type/angle/move), bound with timeline markers
  * voiceover clips into the sequencer; render settings for 1080x1920 MP4 with audio
Transitions (whip/fade), captions and SFX are done in the edit step, not here.
"""
import bpy, json, math, os, random
from pathlib import Path
from mathutils import Vector, Euler

ROOT = Path(r"C:\Users\User\Desktop\blender roblox tiktoks")
PIPE = ROOT / "pipeline"
for _f in ("blocky_rig.py", "wardrobe.py", "motions.py", "sets.py"):
    exec(open(PIPE / _f, encoding="utf-8").read(), globals())

SET_OFFSET = {"street": (0, 0, 0), "town_square": (600, 0, 0), "house_interior": (1200, 0, 0), "hero_room": (1800, 0, 0)}
PARK = Vector((0, 0, -1000))
BLUE = (0.35, 0.6, 1.0)
LENS = 35.0
TAN_HALF = 18.0 / LENS            # vertical half-FOV tangent (sensor 36mm on the long side)

FRAME_H = {"extreme_close_up": 2.2, "close_up": 3.5, "medium_close": 4.4, "medium": 6.8, "two_shot": 7.5,
           "over_shoulder": 6.0, "insert": 2.2, "wide": 15.0, "extreme_wide": 34.0}
LOOK_Z = {"extreme_close_up": 4.75, "close_up": 4.5, "medium_close": 4.1, "medium": 3.6, "two_shot": 3.8,
          "over_shoulder": 4.3, "insert": 3.0, "wide": 4.0, "extreme_wide": 6.0}
FSTOP = {"extreme_close_up": 2.0, "close_up": 2.4, "medium_close": 3.2, "medium": 4.5, "two_shot": 5.0,
         "over_shoulder": 3.2, "insert": 2.4}


# ------------------------------------------------------------------ loading
def append_collection(blend, name):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == name]
    c = dst.collections[0]
    bpy.context.scene.collection.children.link(c)
    return c


def load_sets(names):
    for n in names:
        c = append_collection(ROOT / "public" / "sets" / f"{n}.blend", f"Set_{n}")
        off = Vector(SET_OFFSET[n])
        for o in [x for x in c.all_objects if x is not None]:
            if o.parent is None:
                o.location = o.location + off
            if o.type == 'LIGHT':
                o["set"] = n
                o.hide_render = o.hide_viewport = False
            for slot in getattr(o, "material_slots", []):
                if slot.material and any(k.startswith("dress_") for k in slot.material.keys()):
                    slot.material["set"] = n


def load_cast(names):
    rigs = {}
    for n in names:
        append_collection(ROOT / "public" / "characters" / f"{n}.blend", n)
        rig = bpy.data.objects[n]
        rig.location = PARK
        rigs[n] = rig
    refresh_drivers()
    return rigs


# ------------------------------------------------------------------ small utils
def F(t, fps):                      # seconds -> frame (1-based)
    return int(round(t * fps)) + 1


def mark_pos(set_name, mark_name):
    m = get_marks(set_name)[mark_name]
    return m.matrix_world.translation.copy(), m.rotation_euler.z


def fwd(yaw):                       # character forward vector for yaw (radians)
    return Vector((math.sin(yaw), -math.cos(yaw), 0))


def yaw_to(src, dst):
    d = dst - src
    return math.atan2(d.x, -d.y)


def lerp_angle(a, b, t):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


def skin_input(rig):
    m = bpy.data.materials[f"{rig.name}_Skin"]
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"]


def key_skin(rig, amount, frame):
    inp = skin_input(rig)
    base = rig.get("_skin_base")
    if base is None:
        rig["_skin_base"] = list(inp.default_value)[:3]
        base = rig["_skin_base"]
    b = srgb(BLUE)
    inp.default_value = (*[base[i] * (1 - amount) + b[i] * amount for i in range(3)], 1)
    inp.keyframe_insert("default_value", frame=frame)


def all_fcurves(idblock):
    ad = getattr(idblock, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def set_interp(idblock, paths, mode='CONSTANT'):
    for fc in all_fcurves(idblock):
        if any(fc.data_path.startswith(p) for p in paths):
            for kp in fc.keyframe_points:
                kp.interpolation = mode


def hold(rig, frame):
    """Freeze the rig's current evaluated state at `frame` so the next shot cuts cleanly."""
    if not all_fcurves(rig):
        return
    bpy.context.scene.frame_set(frame)
    for pb in rig.pose.bones:
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_euler", frame=frame)
    for p in FACE_PROPS:
        rig.keyframe_insert(f'["{p}"]', frame=frame)


# ------------------------------------------------------------------ character animation
def key_pose_breathing(rig, pose_name, f0, f1, seed, breathe=True):
    pose(rig, pose_name, f0)
    if not breathe:
        return
    base_sp = POSES[pose_name].get("spine", (0, 0, 0))
    hips = POSES[pose_name].get("hips_loc", (0, 0, 0))
    rnd = random.Random(seed)
    f, s = f0 + rnd.randint(8, 16), 1
    pbs = rig.pose.bones
    while f < f1 - 4:
        pbs["spine"].rotation_euler = [math.radians(base_sp[0] - 1.6 * s), math.radians(base_sp[1]),
                                       math.radians(base_sp[2] + 0.8 * s)]
        pbs["spine"].keyframe_insert("rotation_euler", frame=f)
        pbs["hips"].location = (hips[0] + 0.025 * s, hips[1] + 0.012 * s, hips[2])
        pbs["hips"].keyframe_insert("location", frame=f)
        s = -s
        f += 22 + rnd.randint(0, 8)


def lipsync(rig, words, fps, base_mouth, loud=False, seed=0):
    rnd = random.Random(seed)
    opens = [6, 4, 3] if loud else [4, 3, 4, 0]
    last_end = None
    for i, w in enumerate(words):
        f0, f1 = F(w["t0"], fps), F(w["t1"], fps)
        rig["mouth"] = rnd.choice(opens); rig.keyframe_insert('["mouth"]', frame=f0)
        f = f0 + 3
        while f < f1 - 1:
            rig["mouth"] = rnd.choice([1, 3] if f % 2 else opens); rig.keyframe_insert('["mouth"]', frame=f)
            f += 3
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or F(nxt["t0"], fps) - f1 > 2:
            rig["mouth"] = 1; rig.keyframe_insert('["mouth"]', frame=f1)
        last_end = f1
    if last_end:
        rig["mouth"] = base_mouth; rig.keyframe_insert('["mouth"]', frame=last_end + 2)


def hop(rig, frame, height=0.4):
    root = rig.pose.bones["root"]
    for f, z in ((frame - 1, 0.0), (frame + 3, height), (frame + 7, 0.0)):
        root.location = (0, 0, z)
        root.keyframe_insert("location", frame=f)


def animate_character(rig, c, shot, tshot, fps, seed):
    f0 = tshot["start_frame"]
    f1 = f0 + tshot["frames"] - 1
    dur = tshot["duration"]
    act = c["action"]
    pbs = rig.pose.bones
    # reset root + feet at shot start (walks/jumps from earlier shots)
    pbs["root"].location = (0, 0, 0); pbs["root"].rotation_euler = (0, 0, 0)
    pbs["root"].keyframe_insert("location", frame=f0); pbs["root"].keyframe_insert("rotation_euler", frame=f0)
    set_feet(rig, f0)

    # ---- pose segments (with timed changes)
    changes = sorted(c.get("changes", []), key=lambda x: x["at"])
    pose_segs = [(0.0, c["pose"])] + [(ch["at"], ch["pose"]) for ch in changes if "pose" in ch]
    expr_segs = [(0.0, c["expression"])] + [(ch["at"], ch["expression"]) for ch in changes if "expression" in ch]
    breathe = act not in ("gestures", "walk_to", "walk_in", "jump")
    for i, (t, p) in enumerate(pose_segs):
        fs = f0 + int(round(t * fps))
        fe = f0 + int(round(pose_segs[i + 1][0] * fps)) if i + 1 < len(pose_segs) else f1
        if i > 0:
            hold(rig, fs - 3)
        key_pose_breathing(rig, p, fs, fe, seed + i, breathe)

    # ---- expressions
    for i, (t, e) in enumerate(expr_segs):
        fs = f0 + int(round(t * fps))
        if i > 0:
            set_expression(rig, expr_segs[i - 1][1], fs - 2)
        set_expression(rig, e, fs)

    # ---- actions
    if act == "talk" or act == "gestures":
        if shot["speaker"] == rig.name:
            pass                                    # lip sync below from real words
        else:
            talk(rig, f0 + 2, f1 - 2, seed=seed)
        if act == "gestures":
            talk_gestures(rig, f0 + 2, f1 - 4, seed=seed)
    elif act == "nod":
        nod(rig, f0 + int(0.4 * fps))
    elif act == "shake_head":
        shake_head(rig, f0 + int(0.4 * fps))
    elif act == "jump":
        jump(rig, f0, height=1.1, air=10)
    elif act == "surprise_hop":
        t_hop = next((ch["at"] for ch in changes if ch.get("expression") in ("shocked", "surprised")), 0.15 * dur)
        fh = f0 + int(round(t_hop * fps))
        hop(rig, fh)
        hold(rig, fh - 1)
        pose(rig, "scared", fh + 2)
    elif act in ("walk_to", "walk_in"):
        walk(rig, f0, max(4, tshot["frames"] - 2), stride=1.3)
    elif act == "blink":
        pass

    # ---- lip sync when this character is the speaker
    if shot["speaker"] == rig.name and tshot["words"]:
        base_mouth = int(EXPRESSIONS[expr_segs[-1][1]][9])
        lipsync(rig, tshot["words"], fps, base_mouth, loud="!" in shot["text"], seed=seed)

    # ---- blinks
    rnd = random.Random(seed * 7 + 3)
    fb = f0 + rnd.randint(12, 40)
    while fb < f1 - 6:
        blink(rig, fb)
        fb += rnd.randint(55, 95)
    if act == "blink":
        blink(rig, f0 + int(0.6 * fps)); blink(rig, f0 + int(1.5 * fps))
    _constant_mouth(rig)



KEY_ENERGY = {"street": 260, "town_square": 260, "house_interior": 170, "hero_room": 90}


def key_light_follow(cam_pos, look, frame, shot):
    """Soft neutral key light riding just above/right of the active camera, so faces never go blue/dark."""
    kl = bpy.data.objects.get("EP_KeyLight")
    if kl is None:
        ld = bpy.data.lights.new("EP_KeyLight", 'AREA'); ld.size = 5.0; ld.color = (1.0, 0.9, 0.78)
        kl = bpy.data.objects.new("EP_KeyLight", ld); bpy.context.scene.collection.objects.link(kl)
    d = (look - cam_pos)
    right = Vector((d.y, -d.x, 0)).normalized() if d.length > 0.01 else Vector((1, 0, 0))
    p = cam_pos + right * min(3.0, 0.3 * d.length) + Vector((0, 0, min(3.0, 0.25 * d.length + 1.0)))
    kl.location = p
    kl.rotation_euler = (look - p).to_track_quat('-Z', 'Y').to_euler()
    silhouette = any(x["type"] == "silhouette" for x in shot.get("fx", []))
    kl.data.energy = 0.0 if silhouette else KEY_ENERGY.get(shot["set"], 300) * max(1.0, d.length / 8.0) ** 2 * 0.5
    kl.keyframe_insert("location", frame=frame)
    kl.keyframe_insert("rotation_euler", frame=frame)
    kl.data.keyframe_insert("energy", frame=frame)

# ------------------------------------------------------------------ camera
def shot_camera(shot, tshot, fps, idx, chars_pos, chars_yaw, set_name):
    c = shot["camera"]
    typ, ang, move, target = c["shot"], c["angle"], c["move"], c["target"]
    H = FRAME_H[typ]
    lz = LOOK_Z[typ]
    names = [x["name"] for x in shot["cast"]]
    marks = get_marks(set_name)

    if target in chars_pos:
        base = chars_pos[target].copy()
        look = base + Vector((0, 0, lz))
        tyaw = chars_yaw[target]
    else:
        base, myaw = mark_pos(set_name, target)
        look = base + Vector((0, 0, lz))
        tyaw = myaw

    if typ == "two_shot" and len(names) > 1:
        pts = [chars_pos[n] for n in names]
        mid = sum(pts, Vector()) / len(pts)
        look = Vector((mid.x, mid.y, mid.z + lz))
        span = max((p - mid).length for p in pts) * 2 + 4.5
        H = max(H, span * 1920 / 1080)

    # direction from target toward camera: camera side (-Y), nudged toward the target's facing
    d = Vector((0, -1, 0))
    f = fwd(tyaw)
    if target not in chars_pos:                       # marks: look from in front of the mark (its facing)
        d = (f + Vector((0, -0.35, 0))).normalized()
    elif f.y > 0.3 and typ not in ("two_shot", "wide", "extreme_wide"):
        d = (f + Vector((0, -0.3, 0))).normalized()   # character faces away from camera side -> go in front
    else:
        d = (d * 0.75 + f * 0.25).normalized()
    var = math.radians(12 if idx % 2 == 0 else -12)
    d = Vector((d.x * math.cos(var) - d.y * math.sin(var), d.x * math.sin(var) + d.y * math.cos(var), 0))

    dist = H / (2 * TAN_HALF)

    def place(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None):
        dd = Vector((d.x * math.cos(orbit) - d.y * math.sin(orbit), d.x * math.sin(orbit) + d.y * math.cos(orbit), 0))
        L = (look_override or look).copy()
        right = Vector((-dd.y, dd.x, 0))
        L += right * truck
        dm = dist * dist_mul
        pos = L + dd * dm
        if ang == "low":
            pos.z = max(base.z + 0.8, L.z - 0.38 * dm)
        elif ang == "high":
            pos.z = L.z + 0.55 * dm
        elif ang == "top":
            pos.z = L.z + 1.3 * dm
        else:
            pos.z = L.z + 0.06 * dm
        return pos, L

    if typ == "over_shoulder":
        ch = chars_pos[names[0]]; fy = fwd(chars_yaw[names[0]])
        right = Vector((-fy.y, fy.x, 0))
        def place(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None):  # noqa: F811
            side = -right
            pos = ch - fy * (5.0 * dist_mul) + side * 3.0 + Vector((0, 0, 5.8))
            L = ch + fy * 3.3 + side * 1.3 + Vector((0, 0, 4.2))
            return pos, L

    keys = []                                         # (frame_offset_s, pos, look, roll)
    dur = tshot["duration"]
    roll = math.radians(10) if ang == "dutch" else 0.0
    if move == "push_in":
        keys = [(0, *place(1.3), roll), (dur, *place(0.97), roll)]
    elif move == "pull_out":
        keys = [(0, *place(0.92), roll), (dur, *place(1.3), roll)]
    elif move in ("pan_left", "pan_right"):
        s = 1 if move == "pan_left" else -1
        keys = [(0, *place(1.0, truck=s * 1.6), roll), (dur, *place(1.0, truck=-s * 1.6), roll)]
    elif move in ("orbit_left", "orbit_right"):
        s = 1 if move == "orbit_left" else -1
        keys = [(0, *place(1.05, orbit=-s * math.radians(16)), roll), (dur, *place(1.05, orbit=s * math.radians(16)), roll)]
    elif move == "track":
        walker = names[0]
        speed = 1.3 / 10 * fps                        # walk() stride/period -> units per second
        end = chars_pos[walker] + fwd(chars_yaw[walker]) * speed * dur
        L0 = Vector((chars_pos[walker].x, chars_pos[walker].y, chars_pos[walker].z + lz))
        L1 = Vector((end.x, end.y, end.z + lz))
        keys = [(0, *place(1.0, look_override=L0), roll), (dur, *place(1.0, look_override=L1), roll)]
    elif move == "whip_in":
        keys = [(0, *place(2.4), roll), (min(0.2, dur), *place(1.0), roll), (dur, *place(0.96), roll)]
    elif move == "shake":
        rnd = random.Random(idx)
        p0, L0 = place(1.0)
        t = 0.0
        while t <= dur:
            amp = 0.06 * math.sqrt(dist)
            j = Vector((rnd.uniform(-amp, amp), rnd.uniform(-amp, amp), rnd.uniform(-amp, amp)))
            keys.append((t, p0 + j, L0 + j * 0.3, roll))
            t += 2 / fps
    else:  # static: tiny drift so it never feels frozen
        keys = [(0, *place(1.03), roll), (dur, *place(1.0), roll)]

    cam_data = bpy.data.cameras.new(f"CAM_{shot['id']}")
    cam_data.lens = LENS
    cam_data.sensor_fit = 'AUTO'
    cam_data.clip_start = 0.1
    cam_data.clip_end = 300
    if typ in FSTOP:
        cam_data.dof.use_dof = True
        cam_data.dof.aperture_fstop = FSTOP[typ]
    cam = bpy.data.objects.new(f"CAM_{shot['id']}", cam_data)
    bpy.data.collections["EP_Cameras"].objects.link(cam)
    cam.rotation_mode = 'XYZ'
    f0 = tshot["start_frame"]
    for t, pos, L, r in keys:
        f = f0 + min(int(round(t * fps)), tshot["frames"] - 1)   # never key onto the next shot's first frame
        cam.location = pos
        q = (L - pos).to_track_quat('-Z', 'Y')
        e = q.to_euler('XYZ')
        if r:
            e.rotate_axis('Z', r)
        cam.rotation_euler = e
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        key_light_follow(pos, L, f, shot)
        if cam_data.dof.use_dof:
            cam_data.dof.focus_distance = (L - pos).length
            cam_data.dof.keyframe_insert("focus_distance", frame=f)
    if move == "shake":
        set_interp(cam, ["location", "rotation_euler"], 'LINEAR')
    m = bpy.context.scene.timeline_markers.new(shot["id"], frame=f0)
    m.camera = cam
    return cam


# ------------------------------------------------------------------ dressing per shot
def key_dressing(set_name, dressing, frame, world):
    for o in [x for x in bpy.data.objects if x is not None]:
        if o.type == 'LIGHT' and "set" in o:
            e = o.get(f"dress_{dressing}", 0.0) if o["set"] == set_name else 0.0
            o.data.energy = e
            o.data.keyframe_insert("energy", frame=frame)
            r = o.get(f"dress_rot_{dressing}") if o["set"] == set_name else None
            base = o.get("dress_rot_base")
            if base is None:
                o["dress_rot_base"] = [math.degrees(a) for a in o.rotation_euler]
                base = o["dress_rot_base"]
            o.rotation_euler = [math.radians(a) for a in (r if r is not None else base)]
            o.keyframe_insert("rotation_euler", frame=frame)
        only = o.get("only_dressing")
        if only is not None:
            hide = not (only == dressing)
            o.hide_render = o.hide_viewport = hide
            o.keyframe_insert("hide_render", frame=frame)
            o.keyframe_insert("hide_viewport", frame=frame)
    for m in bpy.data.materials:
        if m.get("set") is None:
            continue
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Emission Color"].default_value = b.inputs["Base Color"].default_value
        b.inputs["Emission Strength"].default_value = m.get(f"dress_{dressing}", 0.0) if m["set"] == set_name else 0.0
        b.inputs["Emission Strength"].keyframe_insert("default_value", frame=frame)
    col, strength = WORLDS[dressing]
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*srgb(col), 1)
    bg.inputs[1].default_value = strength
    bg.inputs[0].keyframe_insert("default_value", frame=frame)
    bg.inputs[1].keyframe_insert("default_value", frame=frame)


def make_letter(rig):
    m = get_mat("Prop_Paper", (0.98, 0.97, 0.92), 0.6)
    ob = box("prop_letter", bpy.data.collections["EP_Props"], (1.2, 0.08, 0.8), (1.5, -0.62, 1.75), m, 0.03)
    keep = rig.location.copy(); rig.location = (0, 0, 0)
    bpy.context.view_layer.update()
    bind(ob, rig, "hand.L")
    rig.location = keep
    return ob


# ------------------------------------------------------------------ main
def assemble(episode_dir=None, save=True):
    ep = Path(episode_dir or EPISODE_DIR)
    shots = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    timing = json.loads((ep / "timing.json").read_text(encoding="utf-8"))
    fps = shots["fps"]
    T = {s["id"]: s for s in timing["shots"]}
    sc = bpy.context.scene
    sc.name = shots["episode"]
    sc.render.fps = fps
    sc.render.resolution_x, sc.render.resolution_y = shots["resolution"]
    sc.render.resolution_percentage = 100
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.frame_start = 1
    sc.frame_end = timing["total_frames"]
    for n in ("EP_Cameras", "EP_Props"):
        if n not in bpy.data.collections:
            sc.collection.children.link(bpy.data.collections.new(n))

    set_names = sorted({s["set"] for s in shots["shots"]})
    cast_names = sorted({c["name"] for s in shots["shots"] for c in s["cast"]})
    load_sets(set_names)
    rigs = load_cast(cast_names)
    world = bpy.data.worlds.new("EP_World"); world.use_nodes = True; sc.world = world
    letter = make_letter(rigs["Hero"]) if "Hero" in rigs else None

    for idx, shot in enumerate(shots["shots"]):
        ts = T[shot["id"]]
        f0 = ts["start_frame"]
        st = shot["set"]
        key_dressing(st, shot.get("dressing") or DRESSINGS[st][0], f0, world)

        # positions + facing
        pos, yaw = {}, {}
        for c in shot["cast"]:
            p, myaw = mark_pos(st, c["mark"])
            pos[c["name"]], yaw[c["name"]] = p, myaw
        cam_guess = {}
        for c in shot["cast"]:
            n, f = c["name"], c["facing"]
            if f in pos:
                y = yaw_to(pos[n], pos[f])
                y = lerp_angle(y, 0.0, 0.4)                 # cheat toward camera side
            elif f == "camera":
                y = 0.0
            elif f == "left":
                y = math.radians(-90)
            elif f == "right":
                y = math.radians(90)
            elif f == "away":
                y = math.radians(180)
            elif f in get_marks(st):
                mp_, myaw_ = mark_pos(st, f)
                y = myaw_ if (mp_ - pos[n]).length < 0.5 else yaw_to(pos[n], mp_)   # own mark -> use its facing
            else:
                y = yaw[n]
            yaw[n] = y

        cam = shot_camera(shot, ts, fps, idx, pos, yaw, st)
        # face the actual camera for "camera" facing
        bpy.context.scene.frame_set(f0)
        for c in shot["cast"]:
            if c["facing"] == "camera":
                yaw[c["name"]] = yaw_to(pos[c["name"]], cam.matrix_world.translation)

        present = {c["name"] for c in shot["cast"]}
        for n, rig in rigs.items():
            if n in present:
                hold(rig, f0 - 1) if f0 > 1 else None
                rig.location = pos[n]
                rig.rotation_euler = (0, 0, yaw[n])
            else:
                rig.location = PARK
            rig.keyframe_insert("location", frame=f0)
            rig.keyframe_insert("rotation_euler", frame=f0)

        for j, c in enumerate(shot["cast"]):
            rig = rigs[c["name"]]
            animate_character(rig, c, shot, ts, fps, seed=idx * 31 + j)
            # skin: reset (or fx start value) at shot start
            fx = next((x for x in shot.get("fx", []) if x["type"] == "blue_skin" and x["target"] == c["name"]), None)
            key_skin(rig, fx["from"] if fx else 0.0, f0)
            if fx:
                fa = f0 + int(round(fx["at"] * fps))
                key_skin(rig, fx["from"], max(f0, fa))
                key_skin(rig, fx["to"], fa + max(1, int(round(fx["over"] * fps))))

        # silhouette fx: kill front light, blast the hallway (hero_room only)
        if any(x["type"] == "silhouette" for x in shot.get("fx", [])):
            for o in bpy.data.objects:
                if o.type == 'LIGHT' and o.get("set") == st:
                    if "front_fill" in o.name or "ceiling" in o.name or "desk" in o.name:
                        o.data.energy = 0.0; o.data.keyframe_insert("energy", frame=f0)
                    if "hall_light" in o.name:
                        o.data.energy = 2500.0; o.data.keyframe_insert("energy", frame=f0)
        # door for hero_room shots
        hinge = next((o for o in bpy.data.objects if o.name.startswith("door_hinge")), None)
        if hinge and st == "hero_room":
            opening = shot["id"] == shots["shots"][-1]["id"]
            hinge.rotation_euler = (0, 0, 0)
            hinge.keyframe_insert("rotation_euler", frame=f0)
            if opening:
                hinge.rotation_euler = (0, 0, math.radians(80))
                hinge.keyframe_insert("rotation_euler", frame=f0 + int(0.7 * fps))
        # props
        if letter:
            want = any("letter" in c.get("props", []) for c in shot["cast"])
            letter.hide_render = letter.hide_viewport = not want
            letter.keyframe_insert("hide_render", frame=f0); letter.keyframe_insert("hide_viewport", frame=f0)

    # cuts must be hard: constant interpolation on object placement / dressing / visibility
    for rig in rigs.values():
        set_interp(rig, ["location", "rotation_euler"], 'CONSTANT')
        _constant_mouth(rig)
        for m in (bpy.data.materials.get(f"{rig.name}_Skin"),):
            if m and m.node_tree.animation_data:
                pass
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            set_interp(o.data, ["energy"], 'CONSTANT')
            set_interp(o, ["rotation_euler"], 'CONSTANT')
        set_interp(o, ["hide_"], 'CONSTANT')
    for m in bpy.data.materials:
        if m.node_tree and m.get("set") is not None:
            set_interp(m.node_tree, ["nodes"], 'CONSTANT')
    set_interp(world.node_tree, ["nodes"], 'CONSTANT')

    # ---- audio
    se = sc.sequence_editor or sc.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    for i, s in enumerate(timing["shots"]):
        if s["audio"]:
            st_ = strips.new_sound(s["id"], str(ep / s["audio"]), 1 + (i % 2), F(s["audio_start"], fps))
    # ---- output
    r = sc.render
    try:
        r.image_settings.media_type = 'VIDEO'
    except Exception:
        pass
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    r.ffmpeg.audio_codec = 'AAC'
    r.ffmpeg.audio_bitrate = 192
    (ep / "render").mkdir(exist_ok=True)
    r.filepath = str(ep / "render" / f"{shots['episode']}_raw.mp4")
    sc.frame_set(1)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=str(ep / f"{shots['episode']}.blend"))
    return sc
