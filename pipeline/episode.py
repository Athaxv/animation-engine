"""
Episode builder (R6 Roblox cast): shots.json + timing.json -> one Blender scene, one timeline.

Headless (what make.py runs):
    blender -b --factory-startup --python pipeline/episode.py -- <episode_dir>
Inside a live Blender (MCP):
    ns = {"__name__": "episode"}; exec(open(r".../pipeline/episode.py", encoding="utf-8").read(), ns)
    ns["build"](r".../episodes/<ep>")

What it does
  * appends the sets the episode uses (public/roblox/sets) side by side, and the cast
    (public/roblox/characters, or custom characters built from a preset + overrides)
  * per shot: dressing (lights / sky), characters on marks with pose, face, actions, lip flaps on
    the real word timings, blinks, scale / tint / props, one camera with its move, bound by a marker
  * saves <episode>/<episode>.blend set up to render render/raw.mp4 (no audio: edit.py adds sound,
    captions and transitions)
"""
import bpy, json, math, os, random, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
PIPE = ROOT / "pipeline"
RBX = ROOT / "public" / "roblox"
for _f in ("roblox_rig.py", "roblox_motions.py", "roblox_sets.py", "props.py"):
    exec(open(PIPE / _f, encoding="utf-8").read(), globals())

if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))
import cinematography

CATALOG = json.loads((RBX / "catalog.json").read_text(encoding="utf-8"))
SET_SPACING = 600.0
PARK = Vector((0, 0, -500))

LENS = 35.0
TAN_HALF = 18.0 / LENS            # vertical half-FOV tangent (portrait: sensor fits the long side)
FRAME_H = dict(cinematography.FRAME_H)
LOOK_Z = dict(cinematography.LOOK_Z)
FSTOP = dict(cinematography.FSTOP)

BLINKABLE = {"smile", "grin", "worried", "shocked", "angry", "sad", "neutral", "smirk", "surprised",
             "confident", "nervous"}
ACTION_FACE = {"surprise_hop": "shocked", "laugh": "laugh", "cry": "cry", "sleep": "sleep",
               "celebrate": "laugh", "fall_back": "shocked"}
TALKY = {"relaxed", "stand", "explain"}


# ------------------------------------------------------------------ small utils
def fcurves_of(idblock):
    ad = getattr(idblock, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", []) or []):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def interp_all(idblock, prefixes, mode='CONSTANT'):
    for fc in fcurves_of(idblock):
        if any(fc.data_path.startswith(p) for p in prefixes):
            for kp in fc.keyframe_points:
                kp.interpolation = mode


def remove_keys(idblock, f_from, f_to, path_prefix=""):
    for fc in fcurves_of(idblock):
        if not fc.data_path.startswith(path_prefix):
            continue
        for kp in [k for k in fc.keyframe_points if f_from - 0.01 <= k.co.x <= f_to + 0.01][::-1]:
            fc.keyframe_points.remove(kp)


def fwd(yaw):
    return Vector((math.sin(yaw), -math.cos(yaw), 0))


def yaw_to(src, dst):
    d = dst - src
    return math.atan2(d.x, -d.y)


def lerp_angle(a, b, t):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * t


def tup(v):
    return tuple(v) if isinstance(v, list) else v


# ------------------------------------------------------------------ loading
def append_collection(blend, name):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == name]
    c = dst.collections[0]
    bpy.context.scene.collection.children.link(c)
    return c


def set_origin(name, order):
    return Vector((order[name] * SET_SPACING, 0, 0))


def load_sets(names):
    order = {n: i for i, n in enumerate(names)}
    for n in names:
        c = append_collection(RBX / "sets" / f"{n}.blend", f"Set_{n}")
        off = set_origin(n, order)
        for o in [x for x in c.all_objects if x is not None]:
            if o.parent is None:
                o.location = o.location + off
            if o.type == 'LIGHT':
                o["set"] = n
            if o.type == 'CAMERA':
                o.hide_render = True
            for slot in getattr(o, "material_slots", []):
                if slot.material and any(k.startswith("dress_") for k in slot.material.keys()):
                    slot.material["set"] = n
    bpy.context.view_layer.update()
    return order


def mark_world(set_name, mark, order):
    info = CATALOG["sets"][set_name]["marks"][mark]
    return Vector(info["pos"]) + set_origin(set_name, order), math.radians(info["facing"])


def load_cast(names, custom):
    rigs = {}
    for n in names:
        spec = custom.get(n) or {}
        if spec.get("identity"):
            rig = build_identity_rig(n, spec)
        elif n in custom:
            import inspect
            allowed = set(inspect.signature(build_character).parameters) - {"name", "location"}
            spec_b = dict(PRESETS[custom[n].get("base", "Theo")])
            for k, v in custom[n].items():
                if k in allowed:
                    spec_b[k] = tuple(v) if isinstance(v, list) else v
            rig = build_character(n, **spec_b)
        else:
            append_collection(RBX / "characters" / f"{n}.blend", n)
            rig = bpy.data.objects[n]
        rig.location = PARK
        rig["ground"] = (0.0, 0.0, 0.0)
        rig["heading"] = 0.0
        rigs[n] = rig
    # appended drivers (face atlas cell) need a nudge to re-evaluate
    for m in bpy.data.materials:
        ad = m.node_tree.animation_data if m.node_tree else None
        for fc in (ad.drivers if ad else []):
            fc.driver.type = fc.driver.type
    bpy.context.view_layer.update()
    return rigs


def build_identity_rig(name, spec):
    """
    Build a cast member whose *appearance* comes from a persistent identity.

    The identity owns skin / hair / outfit / accessories / body scale. Scene and
    episode data only choose who is on screen, never how they look, so a character
    stays identical from shot to shot and across episodes. Appearance overrides in
    the cast entry are ignored on purpose (with a warning) rather than silently
    forking the identity.
    """
    import inspect
    import sys
    if str(PIPE) not in sys.path:
        sys.path.insert(0, str(PIPE))
    import characters

    cid = characters.resolve(spec["identity"])
    if cid is None:
        raise KeyError(f"cast {name!r}: unknown identity {spec['identity']!r}; "
                       f"available: {sorted(characters.CHARACTER_IDENTITIES)}")
    ident = characters.get(cid)
    if ident.get("legacy_preset"):
        kwargs = dict(PRESETS[ident["legacy_preset"]])
        kwargs["face"] = ident["face_style"]
    else:
        kwargs = characters.identity_to_rig_kwargs(cid)

    allowed = set(inspect.signature(build_character).parameters) - {"name", "location"}
    ignored = sorted(set(spec) & allowed)
    if ignored:
        print(f"! cast {name}: appearance comes from identity {cid!r}; ignored {ignored}")
    return build_character(name, **kwargs)


# ------------------------------------------------------------------ dressing per shot
def make_world():
    w = bpy.data.worlds.new("EP_World"); w.use_nodes = True
    N, L = w.node_tree.nodes, w.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_WORLD':
            N.remove(n)
    out = next(n for n in N if n.type == 'OUTPUT_WORLD')
    lp = N.new("ShaderNodeLightPath")
    cam_bg = N.new("ShaderNodeBackground"); cam_bg.name = "CamBG"
    light_bg = N.new("ShaderNodeBackground"); light_bg.name = "LightBG"
    mix = N.new("ShaderNodeMixShader")
    L.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    L.new(light_bg.outputs[0], mix.inputs[1]); L.new(cam_bg.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = w
    return w


def key_dressing(set_name, dressing, frame, world, mood=None):
    for o in [x for x in bpy.data.objects if x is not None]:
        if o.type == 'LIGHT' and "set" in o:
            on = o["set"] == set_name
            e = o.get(f"dress_{dressing}", 0.0) if on else 0.0
            o.data.energy = e
            o.data.keyframe_insert("energy", frame=frame)
            o.hide_render = (e == 0)
            o.keyframe_insert("hide_render", frame=frame)
            r = o.get(f"dress_rot_{dressing}") if on else None
            if r is not None:
                o.rotation_euler = [math.radians(a) for a in r]
                o.keyframe_insert("rotation_euler", frame=frame)
            c = o.get(f"dress_col_{dressing}") if on else None
            if c is not None:
                o.data.color = tuple(c)
                o.data.keyframe_insert("color", frame=frame)
        only = o.get("only_dressing")
        if only is not None:
            o.hide_render = o.hide_viewport = (only != dressing)
            o.keyframe_insert("hide_render", frame=frame)
            o.keyframe_insert("hide_viewport", frame=frame)
    for m in bpy.data.materials:
        if m.get("set") is None or m.get("set") != set_name or f"dress_{dressing}" not in m:
            continue
        r, g, bl, em = m[f"dress_{dressing}"]
        b = _bsdf(m)
        if m.get("interior", True):
            b.inputs["Base Color"].default_value = (*srgb((r, g, bl)), 1)
            b.inputs["Base Color"].keyframe_insert("default_value", frame=frame)
        b.inputs["Emission Color"].default_value = (*srgb((r, g, bl)), 1)
        b.inputs["Emission Strength"].default_value = em
        b.inputs["Emission Color"].keyframe_insert("default_value", frame=frame)
        b.inputs["Emission Strength"].keyframe_insert("default_value", frame=frame)
    if mood:
        cinematography.apply_world_lighting(bpy, world, mood, frame)
    elif dressing in WORLDS:
        sky, lightc, strength = WORLDS[dressing]
        N = world.node_tree.nodes
        cam_bg, light_bg = N["CamBG"], N["LightBG"]
        cam_bg.inputs[0].default_value = (*srgb(sky), 1)
        light_bg.inputs[0].default_value = (*srgb(lightc), 1)
        light_bg.inputs[1].default_value = strength
        for inp in (cam_bg.inputs[0], light_bg.inputs[0], light_bg.inputs[1]):
            inp.keyframe_insert("default_value", frame=frame)
    else:
        cinematography.apply_world_lighting(bpy, world, dressing, frame)


# ------------------------------------------------------------------ character state
def skin_inputs(rig):
    out = []
    m = bpy.data.materials.get(f"{rig.name}_Skin")
    if m:
        out.append(_bsdf(m).inputs["Base Color"])
    h = bpy.data.materials.get(f"{rig.name}_Head")
    if h:
        mix = next((n for n in h.node_tree.nodes if n.type == 'MIX'), None)
        if mix:
            out.append(mix.inputs[6])
    return out


def key_tint(rig, color, amount, frame):
    for i, inp in enumerate(skin_inputs(rig)):
        key = f"_skin_base{i}"
        if key not in rig:
            rig[key] = list(inp.default_value)[:3]
        base = rig[key]
        c = srgb(color) if color else base
        a = amount if color else 0.0
        inp.default_value = (*[base[j] * (1 - a) + c[j] * a for j in range(3)], 1)
        inp.keyframe_insert("default_value", frame=frame)


def hold_rig(rig, frame):
    """Key the rig's evaluated state at `frame` (caller did scene.frame_set(frame))."""
    if not fcurves_of(rig):
        return
    for pb in rig.pose.bones:
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_euler", frame=frame)
    rig.keyframe_insert('["face"]', frame=frame)
    rig.keyframe_insert("location", frame=frame)
    rig.keyframe_insert("scale", frame=frame)


def F(t, fps):
    return int(round(t * fps)) + 1


# ------------------------------------------------------------------ actions
def dance(rig, fs, fe):
    f, i = fs, 0
    while f < fe - 4:
        s = 1 if i % 2 == 0 else -1
        bone(rig, "upper_arm.L", f, (-150 if s > 0 else -30, 0, -30))
        bone(rig, "upper_arm.R", f, (-30 if s > 0 else -150, 0, 30))
        bone(rig, "spine", f, (0, 0, 8 * s))
        bone(rig, "head", f, (0, 12 * s, -6 * s))
        bone(rig, "upper_leg.L", f, (-15 if s > 0 else 0, 0, 0))
        bone(rig, "upper_leg.R", f, (0 if s > 0 else -15, 0, 0))
        f += 8; i += 1
    return f


def spin(rig, fs, dur=18):
    root = rig.pose.bones["root"]
    h = rig.get("heading", 0.0)
    _key(root, fs, rot=True, loc=False)
    root.rotation_euler.z = h + 2 * math.pi
    _key(root, fs + dur, rot=True, loc=False)
    root.rotation_euler.z = h
    _key(root, fs + dur + 1, rot=True, loc=False)
    return fs + dur


FLOAT_H = 3.0


def float_up(rig, fs, fe, height=FLOAT_H):
    root = rig.pose.bones["root"]
    z0 = root.location.z
    _key(root, fs, rot=False, loc=True)
    root.location.z = z0 + height
    _key(root, min(fe, fs + 30), rot=False, loc=True)
    f, s = fs + 30, 1
    while f + 20 < fe:
        f += 20
        root.location.z = z0 + height + 0.35 * s
        _key(root, f, rot=False, loc=True)
        s = -s
    return fe


def key_scale(rig, frame, s):
    rig.scale = (s, s, s)
    rig.keyframe_insert("scale", frame=frame)


def run_action(rig, act, a, fs, fe, ctx):
    """ctx: dict(pose, seed, set, order, start_world, cur_scale, fps)."""
    seed, fps = ctx["seed"], ctx["fps"]
    cur = ctx["pose"]
    root = rig.pose.bones["root"]

    def target_local():
        if a.get("to"):
            p, _ = mark_world(ctx["set"], a["to"], ctx["order"])
            v = p - ctx["start_world"]
            return v.x + a.get("to_dx", 0.0), v.y + a.get("to_dy", 0.0)
        off = a.get("to_offset", [0, 6])
        return root.location.x + off[0], root.location.y + off[1]

    def arrive(end, heading=None):
        """after a walk: optionally turn back to `heading` (radians), then take the segment's pose again."""
        if heading is not None:
            end = turn(rig, end, math.degrees(heading), 5)
        if cur not in ("relaxed", "stand", "run", "walk"):
            pose(rig, cur if cur in POSES else "relaxed", end + 2, keep_root=True)
        return end + 2

    if act in ("idle", "talk_still"):
        if cur not in ("lie", "sit", "run", "jump"):
            idle(rig, fs, fe - 5, seed=seed, base=cur if cur in POSES else "relaxed")
    elif act == "talk":
        if cur in TALKY:
            talk_gestures(rig, fs, fe - 6, seed=seed)
        elif cur not in ("lie", "sit"):
            idle(rig, fs, fe - 5, seed=seed, base=cur)
    elif act == "gestures":
        talk_gestures(rig, fs, fe - 6, seed=seed, every=(9, 16), energy=1.4)
    elif act in ("walk_to", "run_to"):
        x, y = target_local()
        h0 = rig.get("heading", 0.0)
        end = walk_to(rig, fs, x, y, running=(act == "run_to"), fps=fps)
        ctx["dest"] = (x, y)
        return arrive(end, h0 if a.get("face_after", True) else None)
    elif act == "walk_in":
        side = a.get("from", "left")
        tx, ty = root.location.x, root.location.y
        h0 = rig.get("heading", 0.0)
        sx = {"left": -10, "right": 10}.get(side, 0)
        sy = 9 if side == "back" else 0
        place(rig, fs, x=tx + sx, y=ty + sy)
        return arrive(walk_to(rig, fs, tx, ty, fps=fps), h0)
    elif act in ("walk_out", "run_out"):
        side = a.get("to_side", "right")
        x = root.location.x + (14 if side == "right" else -14)
        return walk_to(rig, fs, x, root.location.y, running=(act == "run_out"), fps=fps)
    elif act == "jump":
        return jump(rig, fs)
    elif act == "celebrate":
        return celebrate(rig, fs)
    elif act == "surprise_hop":
        return surprise_hop(rig, fs)
    elif act == "fall_back":
        return fall_back(rig, fs)
    elif act == "nod":
        return nod(rig, fs)
    elif act == "shake_head":
        return shake_head(rig, fs)
    elif act == "wave":
        return wave(rig, fs)
    elif act == "laugh":
        return laugh(rig, fs, dur=max(8, min(fe - fs - 2, 60)))
    elif act == "cry":
        return cry(rig, fs, dur=max(8, fe - fs - 2), seed=seed)
    elif act == "look_around":
        return look_around(rig, fs)
    elif act == "shiver":
        shiver(rig, fs, fe - 2, base=cur if cur in POSES else "scared", seed=seed)
    elif act == "sleep":
        sleep(rig, fs, fe)
    elif act == "sit_down":
        return sit_down(rig, fs, ctx.get("seat", 2.0))
    elif act == "stand_up":
        return stand_up(rig, fs, 0.0)
    elif act == "dance":
        return dance(rig, fs, fe)
    elif act == "spin":
        return spin(rig, fs)
    elif act == "float":
        return float_up(rig, fs, fe)
    elif act == "poof":
        s = ctx["cur_scale"]
        key_scale(rig, fs, s); key_scale(rig, fs + 2, s * 1.15); key_scale(rig, fs + 6, 0.001)
    elif act == "pop_in":
        s = ctx["cur_scale"]
        key_scale(rig, fs, 0.001); key_scale(rig, fs + 4, s * 1.15); key_scale(rig, fs + 7, s)
    elif act == "pickup":
        return pickup(rig, fs, dur=max(8, min(fe - fs - 2, 22)))
    elif act == "drop":
        return drop(rig, fs, dur=max(6, min(fe - fs - 2, 16)))
    elif act == "pass_prop":
        return pass_prop(rig, fs, dur=max(10, min(fe - fs - 2, 24)))
    elif act == "catch_prop":
        return catch_prop(rig, fs, dur=max(10, min(fe - fs - 2, 24)))
    elif act == "handshake":
        return handshake(rig, fs, dur=max(12, min(fe - fs - 2, 28)))
    elif act == "hug":
        return hug(rig, fs, dur=max(14, min(fe - fs - 2, 32)))
    elif act == "approach":
        x, y = target_local()
        h0 = rig.get("heading", 0.0)
        end = approach(rig, fs, x, y, fps=fps)
        ctx["dest"] = (x, y)
        return arrive(end, h0 if a.get("face_after", True) else None)
    elif act == "push_prop":
        return push_prop(rig, fs, dur=max(10, min(fe - fs - 2, 24)))
    return fs


# ------------------------------------------------------------------ one character in one shot
def animate_char(rig, c, shot, ts, fps, seed, order, f1, start_world, cam_words):
    f0 = ts["start_frame"]
    set_name = shot["set"]
    T = lambda t: max(f0, min(f1, f0 + int(round(t * fps))))
    pbs = rig.pose.bones
    mk = CATALOG["sets"][set_name]["marks"].get(c["mark"], {})
    seat = mk.get("seat", 2.0)
    pose0 = c.get("pose", "relaxed")
    zoff = (seat - SEAT_HEIGHT) if pose0 == "sit" else 0.0

    # root: offset on the mark, heading, ground
    rig["ground"] = (0.0, 0.0, zoff)
    rig["heading"] = c["_yaw"]
    root = pbs["root"]
    root.location = (c.get("dx", 0.0), c.get("dy", 0.0), zoff)
    root.rotation_euler = (0, 0, c["_yaw"])
    for pb in pbs:
        if pb.name != "root":
            pb.location = (0, 0, 0)
            _key(pb, f0, rot=False, loc=True)
    pose(rig, pose0 if pose0 in POSES else "relaxed", f0)

    changes = sorted(c.get("changes", []), key=lambda x: x["at"])
    # ---- pose segments
    pose_segs = [(f0, pose0)] + [(T(ch["at"]), ch["pose"]) for ch in changes if "pose" in ch]
    for i in range(1, len(pose_segs)):
        fs, p = pose_segs[i]
        prev = pose_segs[i - 1][1]
        pose(rig, prev if prev in POSES else "relaxed", max(pose_segs[i - 1][0], fs - 4), keep_root=True)
        pose(rig, p if p in POSES else "relaxed", fs, keep_root=True)

    def pose_at(f):
        p = pose0
        for fs, pp in pose_segs:
            if fs <= f:
                p = pp
        return p

    # ---- actions
    acts = [(f0, c.get("action", "idle"), c)] + [(T(ch["at"]), ch["action"], ch) for ch in changes if "action" in ch]
    cur_scale = float(c.get("scale", 1.0)) * float(rig.get("body_scale", 1.0) or 1.0)
    ctx = {"seed": seed, "fps": fps, "set": set_name, "order": order, "start_world": start_world,
           "seat": seat, "cur_scale": cur_scale}
    dest = None
    for i, (fs, act, a) in enumerate(acts):
        fe = acts[i + 1][0] if i + 1 < len(acts) else f1
        nxt_pose = [f for f, _ in pose_segs if f > fs]
        if nxt_pose and act in ("idle", "talk", "talk_still", "gestures", "shiver"):
            fe = min(fe, nxt_pose[0])
        ctx["pose"] = pose_at(fs)
        run_action(rig, act, a, fs, fe, ctx)
        dest = ctx.get("dest", dest)

    # ---- scale changes
    key_scale(rig, f0, cur_scale) if not any(a[1] == "pop_in" and a[0] == f0 for a in acts) else None
    for ch in changes:
        if "scale" in ch:
            fs = T(ch["at"])
            key_scale(rig, fs, cur_scale)
            cur_scale = float(ch["scale"])
            key_scale(rig, fs + int(ch.get("over", 0.3) * fps), cur_scale)

    # ---- tint (static per shot, or changes)
    tint = c.get("tint")
    key_tint(rig, tint.get("color") if tint else None, tint.get("amount", 0.8) if tint else 0.0, f0)
    for ch in changes:
        if "tint" in ch:
            fs = T(ch["at"])
            key_tint(rig, tint.get("color") if tint else None, tint.get("amount", 0.8) if tint else 0.0, fs)
            tint = ch["tint"]
            key_tint(rig, tint.get("color") if tint else None, tint.get("amount", 0.8) if tint else 0.0,
                     fs + int(ch.get("over", 0.4) * fps))

    # ---- faces: actions keyed some; rebuild the whole face track for this shot
    remove_keys(rig, f0, f1 + 40, '["face"]')
    face0 = c.get("face", "smile")
    segs = [(f0, face0)]
    for ch in changes:
        if "face" in ch:
            segs.append((T(ch["at"]), ch["face"]))
        elif ch.get("action") in ACTION_FACE:
            segs.append((T(ch["at"]), ACTION_FACE[ch["action"]]))
    if c.get("action") in ACTION_FACE and "face" not in c:
        segs[0] = (f0, ACTION_FACE[c["action"]])
    segs.sort(key=lambda x: x[0])

    def base_at(f):
        b = face0
        for fs, fc in segs:
            if fs <= f:
                b = fc
        return b if b in FACE_INDEX else "smile"

    events = {fs: (fc if fc in FACE_INDEX else "smile") for fs, fc in segs}
    speaking = shot.get("speaker") == rig.name or c.get("action") in ("talk", "talk_still") \
        or any(ch.get("action") in ("talk", "talk_still") for ch in changes)
    busy = set()
    if speaking:
        rnd = random.Random(seed)
        for w in cam_words:
            wf0, wf1 = max(f0, F(w["t0"], fps)), min(f1, F(w["t1"], fps))
            f, open_ = wf0, True
            while f < wf1:
                events[f] = "talk" if open_ else base_at(f)
                busy.update(range(f - 3, f + 4))
                open_ = not open_
                f += 3 + rnd.choice([0, 0, 1])
            events[wf1] = base_at(wf1)
            busy.update(range(wf1 - 3, wf1 + 4))
    rnd = random.Random(seed * 7 + 3)
    fb = f0 + rnd.randint(10, 35)
    while fb < f1 - 6:
        if base_at(fb) in BLINKABLE and not any(f in busy or f in events for f in range(fb - 3, fb + 6)):
            events[fb] = "blink"
            events[fb + 3] = base_at(fb)
        fb += rnd.randint(50, 90)
    for f in sorted(events):
        if f0 <= f <= f1:
            set_face(rig, events[f], f)

    # ---- trim anything an action keyed past the cut
    remove_keys(rig, f1 + 1, f1 + 400)
    return dest


# ------------------------------------------------------------------ camera
def key_light_follow(cam_pos, look, frame, interior, mood="bright_day"):
    cinematography.apply_three_point_rig(bpy, cam_pos, look, frame, mood, interior)


HEAD_Z = 4.62
PLACED = {}            # id -> (ground point, height) of props placed in the current shot


def body_points(c, pos, yaw):
    """(feet, head) world points of a cast entry at its shot start (sit / lie / scale aware)."""
    p0 = c.get("pose", "relaxed")
    s = max(float(c.get("scale", 1.0)), max([float(ch["scale"]) for ch in c.get("changes", []) if "scale" in ch] or [0]))
    feet = pos.copy()
    if p0 == "sit":
        feet.z += c["_zoff"]
    if p0 == "lie":
        feet.z += 0.5 * s
        y = yaw
        head = feet + Vector((-math.sin(y), math.cos(y), 0)) * HEAD_Z * s
        return feet, head
    return feet, feet + Vector((0, 0, HEAD_Z * s))


def _is_actor(ob):
    while ob is not None:
        if ob.get("is_roblox_rig") or ob.get("prop") or ob.name.startswith("EP_"):
            return True
        ob = ob.parent
    return False


def first_blocker(a, b):
    """Distance from a toward b to the first set object in the way (characters/props ignored), or None."""
    dg = bpy.context.evaluated_depsgraph_get()
    d = b - a
    L = d.length
    if L < 1e-4:
        return None
    d.normalize()
    o, travelled = a.copy(), 0.0
    for _ in range(8):
        hit, loc, _n, _i, ob, _m = bpy.context.scene.ray_cast(dg, o, d, distance=L - travelled)
        if not hit:
            return None
        step = (loc - o).length
        travelled += step
        if not _is_actor(ob):
            return travelled
        o = loc + d * 0.05
        travelled += 0.05
    return None


def unblock(p, L):
    """Move a camera position so nothing in the set hides the look point."""
    start = L + (p - L).normalized() * 0.9          # step out of the head first
    if first_blocker(start, p) is None:
        return p
    d = p - L
    dist = d.length
    for lift in (1.5, 3.0, 5.0):                    # 1) raise the camera (looks over tables / counters)
        q = L + d.normalized() * dist
        q.z += lift
        if first_blocker(L + (q - L).normalized() * 0.9, q) is None:
            return q
    for ang in (20, -20, 35, -35):                  # 2) orbit around the target
        a = math.radians(ang)
        dd = Vector((d.x * math.cos(a) - d.y * math.sin(a), d.x * math.sin(a) + d.y * math.cos(a), d.z))
        q = L + dd
        if first_blocker(L + dd.normalized() * 0.9, q) is None:
            return q
    t = first_blocker(start, p)                     # 3) come in front of the blocker
    if t is not None and t > 1.2:
        return start + (p - start).normalized() * (t - 0.4)
    return p


def shot_camera(shot, f0, frames, fps, idx, pos, yaw, order, dests, bodies=None, floaters=()):
    cin = cinematography.resolve_shot_cinematography(shot)
    typ = cin["shot"]; ang = cin["angle"]; move = cin["move"]
    mood = cin["mood"]
    target = shot.get("camera", {}).get("target") or (shot["cast"][0]["name"] if shot["cast"] else "center")
    set_name = shot["set"]
    marks = CATALOG["sets"][set_name]["marks"]
    H, lz = FRAME_H.get(typ, 6.6), LOOK_Z.get(typ, 3.4)
    names = [x["name"] for x in shot["cast"]]
    bodies = bodies or {}
    dur = frames / fps

    def look_of(n):
        feet, head = bodies.get(n, (pos[n], pos[n] + Vector((0, 0, HEAD_Z))))
        return feet + (head - feet) * (lz / HEAD_Z)

    if target in pos:
        base = pos[target].copy(); tyaw = yaw[target]
        look = look_of(target)
    elif target in marks:
        base, tyaw = mark_world(set_name, target, order)
        look = base + Vector((0, 0, lz))
    elif target in PLACED:                          # a prop placed in the set
        base, ph = PLACED[target]; tyaw = 0.0
        look = base + Vector((0, 0, ph * 0.55))
        H = max(H * 0.6, ph * 1.6) if typ in ("insert", "close_up", "extreme_close_up") else H
    else:
        base, tyaw = set_origin(set_name, order), 0.0
        look = base + Vector((0, 0, lz))

    if (typ in ("two_shot", "group") or (typ in ("wide", "extreme_wide") and target in pos)) and len(names) > 1:
        pts = [pos[n] for n in names]
        mid = sum(pts, Vector()) / len(pts)
        if typ in ("two_shot", "group"):
            look = sum((look_of(n) for n in names), Vector()) / len(names)
        else:
            look = Vector((mid.x, mid.y, look.z))
        span = max(abs(p.x - mid.x) for p in pts) * 2 + 4.0
        hs = [bodies[n][1].z - pos[n].z for n in names if n in bodies]
        H = max(H, span * 16 / 9, (max(hs) + 1.5) if hs else 0)
        # Phase 03: Social media vertical safe-area headroom (window y in [0.22, 0.85])
        max_head_z = max([bodies[n][1].z for n in names if n in bodies] or [look.z + 1.2])
        min_feet_z = min([bodies[n][0].z for n in names if n in bodies] or [look.z - 3.4])
        H = max(H, (max_head_z - min_feet_z) / 0.63)

    d = Vector((0, -1, 0))
    f = fwd(tyaw)
    if target not in pos:
        d = (f + Vector((0, -0.35, 0))).normalized()
    elif f.y > 0.3 and typ not in ("two_shot", "group", "wide", "extreme_wide"):
        d = (f + Vector((0, -0.3, 0))).normalized()
    else:
        d = (d * 0.75 + f * 0.25).normalized()
    var = math.radians(10 if idx % 2 == 0 else -10)
    d = Vector((d.x * math.cos(var) - d.y * math.sin(var), d.x * math.sin(var) + d.y * math.cos(var), 0))
    dist = H / (2 * TAN_HALF)

    def place_cam(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None, lift=0.0):
        dd = Vector((d.x * math.cos(orbit) - d.y * math.sin(orbit), d.x * math.sin(orbit) + d.y * math.cos(orbit), 0))
        L = (look_override or look).copy()
        L += Vector((-dd.y, dd.x, 0)) * truck
        dm = dist * dist_mul
        p = L + dd * dm
        if ang == "low":
            p.z = max(base.z + 0.8, L.z - 0.38 * dm)
        elif ang == "high":
            p.z = L.z + 0.55 * dm
        elif ang in ("top", "birds_eye"):
            p.z = L.z + 1.35 * dm
        else:
            p.z = L.z + 0.06 * dm
        p.z += lift
        return p, L

    if typ == "over_shoulder" and len(names) > 0:
        ch = pos[names[0]]; fy = fwd(yaw[names[0]])
        other_name = names[1] if len(names) > 1 else (target if target in pos else names[0])
        side_mult = cinematography.AXIS_TRACKER.get_or_set_axis_side(names[0], other_name, pos[names[0]], pos.get(other_name, pos[names[0]]))
        side = -Vector((-fy.y, fy.x, 0)) * side_mult

        def place_cam(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None, lift=0.0):  # noqa: F811
            p = ch - fy * (4.2 * dist_mul) + side * 2.4 + Vector((0, 0, 5.2 + lift))
            tgt_pos = pos.get(other_name, ch + fy * 5.0)
            L = (look_override or (tgt_pos + Vector((0, 0, 4.2)))) + side * (0.8 * truck)
            return p, L

    elif typ == "pov" and len(names) > 0:
        p_actor = pos[names[0]]
        fy = fwd(yaw[names[0]])
        def place_cam(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None, lift=0.0):  # noqa: F811
            p = p_actor + Vector((0, 0, 4.3 + lift)) + fy * (0.6 * dist_mul)
            other_name = names[1] if len(names) > 1 else (target if target in pos else None)
            L = (look_override or (pos[other_name] + Vector((0, 0, 3.8)) if other_name else p + fy * 12.0))
            return p, L

    if isinstance(target, str) and target.startswith("cam_") and target in marks:
        p0, _ = mark_world(set_name, target, order)
        focus = marks.get("center") or marks.get("sidewalk_b")
        L0 = (Vector(focus["pos"]) + set_origin(set_name, order) if focus else set_origin(set_name, order)) + Vector((0, 0, 3))

        def place_cam(dist_mul=1.0, orbit=0.0, truck=0.0, look_override=None, lift=0.0):  # noqa: F811
            return L0 + (p0 - L0) * dist_mul + Vector((0, 0, lift)), L0

    roll = math.radians(10) if ang == "dutch" else 0.0
    if move in ("push_in", "dolly_in"):
        keys = [(0, *place_cam(1.25)), (dur, *place_cam(0.97))]
    elif move in ("pull_out", "dolly_out"):
        keys = [(0, *place_cam(0.92)), (dur, *place_cam(1.3))]
    elif move in ("pan_left", "truck_left"):
        keys = [(0, *place_cam(1.0, truck=1.5)), (dur, *place_cam(1.0, truck=-1.5))]
    elif move in ("pan_right", "truck_right"):
        keys = [(0, *place_cam(1.0, truck=-1.5)), (dur, *place_cam(1.0, truck=1.5))]
    elif move in ("tilt_up", "crane_up"):
        keys = [(0, *place_cam(1.0, lift=-1.2)), (dur, *place_cam(1.0, lift=1.8))]
    elif move in ("tilt_down", "crane_down"):
        keys = [(0, *place_cam(1.0, lift=1.8)), (dur, *place_cam(1.0, lift=-1.2))]
    elif move in ("orbit_left", "orbit_right"):
        s = 1 if move == "orbit_left" else -1
        keys = [(0, *place_cam(1.05, orbit=-s * math.radians(16))), (dur, *place_cam(1.05, orbit=s * math.radians(16)))]
    elif move == "establishing_pan":
        keys = [(0, *place_cam(1.0, truck=-2.5)), (dur, *place_cam(1.0, truck=2.5))]
    elif move in ("track", "follow") and target in dests and dests[target] is not None:
        L1 = dests[target] + Vector((0, 0, lz))
        keys = [(0, *place_cam(1.0, look_override=look)), (dur, *place_cam(1.0, look_override=L1))]
    elif move == "whip_in":
        keys = [(0, *place_cam(2.3)), (min(0.2, dur), *place_cam(1.0)), (dur, *place_cam(0.96))]
    elif move == "crash_zoom":
        # hold, then slam into a close-up on the target's face
        face = look
        if target in pos:
            feet, head = bodies.get(target, (pos[target], pos[target] + Vector((0, 0, HEAD_Z))))
            face = feet + (head - feet) * (LOOK_Z["close_up"] / HEAD_Z)
        k = FRAME_H["close_up"] / H
        keys = [(0, *place_cam(1.0)), (min(0.35, dur * 0.4), *place_cam(1.0)),
                (min(0.5, dur * 0.55), *place_cam(k * 1.05, look_override=face)), (dur, *place_cam(k, look_override=face))]
    else:   # static / shake / handheld: tiny drift so it never feels frozen
        keys = [(0, *place_cam(1.03)), (dur, *place_cam(1.0))]

    cd = bpy.data.cameras.new(f"CAM_{shot['id']}")
    cd.lens = LENS; cd.sensor_fit = 'AUTO'; cd.clip_start = 0.1; cd.clip_end = 600
    if typ in FSTOP:
        cd.dof.use_dof = True; cd.dof.aperture_fstop = FSTOP[typ]
    cam = bpy.data.objects.new(f"CAM_{shot['id']}", cd)
    bpy.data.collections["EP_Cameras"].objects.link(cam)
    cam.rotation_mode = 'XYZ'
    interior = set_name != "street"
    # follow a floating target up; keep every key clear of set geometry
    if target in floaters:
        if keys[-1][0] > 1.0 and not any(abs(k[0] - 1.0) < 0.05 for k in keys):
            i = next(i for i, k in enumerate(keys) if k[0] > 1.0)
            (ta, pa, La), (tb, pb, Lb) = keys[i - 1], keys[i]
            u = (1.0 - ta) / (tb - ta)
            keys.insert(i, (1.0, pa.lerp(pb, u), La.lerp(Lb, u)))
        keys = [(t, p + Vector((0, 0, FLOAT_H * 0.75 * min(1.0, t))), L + Vector((0, 0, FLOAT_H * 0.75 * min(1.0, t))))
                for t, p, L in keys]
    if not (isinstance(target, str) and target.startswith("cam_")):
        bpy.context.view_layer.update()
        keys = [(t, unblock(p, L), L) for t, p, L in keys]
    for t, p, L in keys:
        fr = f0 + min(int(round(t * fps)), frames - 1)
        cam.location = p
        e = (L - p).to_track_quat('-Z', 'Y').to_euler('XYZ')
        if roll:
            e.rotate_axis('Z', roll)
        cam.rotation_euler = e
        cam.keyframe_insert("location", frame=fr)
        cam.keyframe_insert("rotation_euler", frame=fr)
        key_light_follow(p, L, fr, interior, mood)
        if cd.dof.use_dof:
            cd.dof.focus_distance = (L - p).length
            cd.dof.keyframe_insert("focus_distance", frame=fr)
    # camera shake: whole shot (move=shake/handheld) or fx windows
    shakes = []
    if move in ("shake", "handheld"):
        strength = 0.35 if move == "handheld" else 1.0
        shakes.append((f0, f0 + frames - 1, strength))
    for fx in shot.get("fx", []):
        if fx.get("type") == "shake":
            a = f0 + int(round(fx.get("at", 0) * fps))
            shakes.append((a, min(f0 + frames - 1, a + int(round(fx.get("dur", 0.5) * fps))), fx.get("strength", 1.0)))
    for a, b, s in shakes:
        for fc in fcurves_of(cam):
            if fc.data_path in ("location", "rotation_euler"):
                m = fc.modifiers.new('NOISE')
                m.scale = 2.0
                m.strength = (0.12 * math.sqrt(dist) if fc.data_path == "location" else 0.02) * s
                m.phase = random.Random(idx * 7 + fc.array_index).uniform(0, 100)
                m.use_restricted_range = True
                m.frame_start, m.frame_end = a, b
                m.blend_in = m.blend_out = 2
    m = bpy.context.scene.timeline_markers.new(shot["id"], frame=f0)
    m.camera = cam
    return cam


# ------------------------------------------------------------------ main
def build(episode_dir, save=True):
    ep = Path(episode_dir)
    data = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    timing = json.loads((ep / "timing.json").read_text(encoding="utf-8"))
    fps = data.get("fps", 30)
    T = {s["id"]: s for s in timing["shots"]}
    shots = data["shots"]

    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.name = data["episode"]
    sc.render.fps = fps
    sc.render.resolution_x, sc.render.resolution_y = data.get("resolution", [1080, 1920])
    sc.render.resolution_percentage = 100
    try:
        sc.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.exposure = -0.2
    try:
        sc.eevee.shadow_pool_size = "1024"
    except Exception:
        pass
    sc.frame_start = 1
    sc.frame_end = timing["total_frames"]
    for n in ("EP_Cameras", "EP_Props"):
        sc.collection.children.link(bpy.data.collections.new(n))

    set_names = list(dict.fromkeys(s["set"] for s in shots))
    cast_names = list(dict.fromkeys(c["name"] for s in shots for c in s["cast"]))
    order = load_sets(set_names)
    face_atlas()
    rigs = load_cast(cast_names, data.get("characters", {}))
    world = make_world()

    # props: one object set per (character, prop spec)
    props = {}
    for s in shots:
        for c in s["cast"]:
            for spec in list(c.get("props", [])) + [p for ch in c.get("changes", []) for p in ch.get("props", [])]:
                key = (c["name"], spec)
                if key not in props:
                    root = build_prop(spec, bpy.data.collections["EP_Props"], f"{c['name']}_{spec.split(':')[0]}_{len(props)}")
                    attach_to_hand(root, rigs[c["name"]])
                    props[key] = prop_objects(root)

    starts = [T[s["id"]]["start_frame"] for s in shots] + [timing["total_frames"] + 1]
    for idx, shot in enumerate(shots):
        ts = T[shot["id"]]
        f0, f1 = starts[idx], starts[idx + 1] - 1
        frames = f1 - f0 + 1
        st = shot["set"]
        cin = cinematography.resolve_shot_cinematography(shot)
        mood = cin["mood"]
        key_dressing(st, shot.get("dressing") or CATALOG["sets"][st]["dressings"][0], f0, world, mood=mood)
        cinematography.apply_color_grading(bpy, sc, mood)

        # Procedural atmospheric, weather, and story VFX
        vfx_list = cin["vfx"]
        weather = cin["weather"]
        bounds = ((order[st] * SET_SPACING - 30.0, -30.0, 0.0), (order[st] * SET_SPACING + 30.0, 30.0, 15.0))

        if "fog" in vfx_list or "haze" in vfx_list:
            cinematography.setup_volumetric_fog(bpy, sc, mood, bounds, f0, f1)

        if weather in ("rain", "snow", "falling_leaves"):
            cinematography.build_weather_system(bpy, sc, weather, bounds, f0, f1, fps, seed=idx * 101 + 17)

        for v in vfx_list:
            if v in ("portal", "sparks", "energy_burst", "smoke_puff"):
                focus_pos = (order[st] * SET_SPACING, 0.0, 0.0)
                if shot.get("cast"):
                    c0 = shot["cast"][0]
                    p, _ = mark_world(st, c0["mark"], order)
                    focus_pos = (p.x + c0.get("dx", 0.0), p.y + c0.get("dy", 0.0), p.z)
                cinematography.build_story_vfx(bpy, sc, v, focus_pos, f0, f1, fps)

        # hold everyone's last state one frame before the cut
        if f0 > 1:
            sc.frame_set(f0 - 1)
            for rig in rigs.values():
                hold_rig(rig, f0 - 1)

        # positions + facing
        pos, yaw, start_world = {}, {}, {}
        for c in shot["cast"]:
            p, myaw = mark_world(st, c["mark"], order)
            start_world[c["name"]] = p.copy()
            pos[c["name"]] = p + Vector((c.get("dx", 0.0), c.get("dy", 0.0), 0))
            yaw[c["name"]] = myaw
        for c in shot["cast"]:
            n, fcg = c["name"], c.get("facing", "camera")
            if fcg in pos and fcg != n:
                y = lerp_angle(yaw_to(pos[n], pos[fcg]), 0.0, 0.35)
            elif fcg == "camera":
                y = 0.0
            elif fcg in ("left", "right", "away"):
                y = math.radians({"left": -90, "right": 90, "away": 180}[fcg])
            elif fcg in CATALOG["sets"][st]["marks"]:
                mp_, _ = mark_world(st, fcg, order)
                y = yaw_to(pos[n], mp_)
            else:
                y = yaw[n]
            yaw[n] = y

        # characters: object at the mark, everything else on the root bone
        present = {c["name"] for c in shot["cast"]}
        for n, rig in rigs.items():
            rig.location = start_world[n] if n in present else PARK
            rig.rotation_euler = (0, 0, 0)
            rig.keyframe_insert("location", frame=f0)
            rig.keyframe_insert("rotation_euler", frame=f0)

        # body points for framing (sitting / lying / scaled), floaters for camera follow
        bodies, floaters = {}, set()
        for c in shot["cast"]:
            n = c["name"]
            mk = CATALOG["sets"][st]["marks"].get(c["mark"], {})
            cc = dict(c); cc["_zoff"] = (mk.get("seat", 2.0) - SEAT_HEIGHT) if c.get("pose") == "sit" else 0.0
            bodies[n] = body_points(cc, pos[n], yaw[n])
            if c.get("action") == "float" or any(ch.get("action") == "float" for ch in c.get("changes", [])):
                floaters.add(n)

        # props standing in the set for this shot ("place"), optionally popping in / out
        PLACED.clear()
        for k, pl in enumerate(shot.get("place", [])):
            root = build_prop(pl["prop"], bpy.data.collections["EP_Props"], f"{shot['id']}_place{k}_{pl['prop'].split(':')[0]}")
            base, _ = mark_world(st, pl["mark"], order)
            target = base + Vector((pl.get("dx", 0.0), pl.get("dy", 0.0), pl.get("z", 0.0)))
            s = float(pl.get("scale", 1.0))
            h = place_in_world(root, target, pl.get("rot", 0.0), s)
            PLACED[pl.get("id", f"place{k}")] = (target, h * s)
            objs = prop_objects(root)
            for fr, hide in ((1, True), (f0, False), (f1 + 1, True)):
                if fr == f0 or fr < f0 or fr > f1:
                    for o in objs:
                        o.hide_render = o.hide_viewport = hide
                        o.keyframe_insert("hide_render", frame=fr)
                        o.keyframe_insert("hide_viewport", frame=fr)
            def kscale(fr, v):
                root.scale = (v, v, v); root.keyframe_insert("scale", frame=fr)
            if "pop_at" in pl:
                a = f0 + int(round(pl["pop_at"] * fps))
                kscale(f0, 0.001); kscale(max(f0, a - 1), 0.001); kscale(a + 4, s * 1.18); kscale(a + 7, s)
            if "poof_at" in pl:
                a = f0 + int(round(pl["poof_at"] * fps))
                kscale(a, s); kscale(a + 2, s * 1.15); kscale(a + 6, 0.001)

        # camera first (so "camera" facing can aim at it)
        cam_guess = shot_camera(shot, f0, frames, fps, idx, pos, yaw, order, {}, bodies, floaters)
        sc.frame_set(f0)
        campos = cam_guess.matrix_world.translation.copy()
        for c in shot["cast"]:
            if c.get("facing", "camera") == "camera":
                yaw[c["name"]] = yaw_to(pos[c["name"]], campos)

        dests = {}
        for j, c in enumerate(shot["cast"]):
            c = dict(c); c["_yaw"] = yaw[c["name"]]
            d = animate_char(rigs[c["name"]], c, shot, ts, fps, idx * 31 + j, order, f1,
                             start_world[c["name"]], ts.get("words", []))
            if d is not None:
                dests[c["name"]] = start_world[c["name"]] + Vector((d[0], d[1], 0))
        if shot.get("camera", {}).get("move") == "track" and dests:
            # rebuild the camera now that we know where the walker ends up
            sc.timeline_markers.remove(sc.timeline_markers[shot["id"]])
            bpy.data.objects.remove(cam_guess, do_unlink=True)
            shot_camera(shot, f0, frames, fps, idx, pos, yaw, order, dests, bodies, floaters)

        # props visibility
        for (cn, spec), objs in props.items():
            entry = next((c for c in shot["cast"] if c["name"] == cn), None)
            want = bool(entry) and spec in entry.get("props", [])
            for o in objs:
                o.hide_render = o.hide_viewport = not want
                o.keyframe_insert("hide_render", frame=f0)
                o.keyframe_insert("hide_viewport", frame=f0)
            if entry:
                for ch in entry.get("changes", []):
                    if "props" in ch:
                        fr = max(f0, min(f1, f0 + int(round(ch["at"] * fps))))
                        for o in objs:
                            o.hide_render = o.hide_viewport = spec not in ch["props"]
                            o.keyframe_insert("hide_render", frame=fr)
                            o.keyframe_insert("hide_viewport", frame=fr)

        # tint fx (shot-level, animated)
        for fx in shot.get("fx", []):
            if fx.get("type") == "tint" and fx.get("target") in rigs:
                rig = rigs[fx["target"]]
                a = f0 + int(round(fx.get("at", 0) * fps))
                key_tint(rig, fx.get("color"), fx.get("from", 0.0), a)
                key_tint(rig, fx.get("color"), fx.get("amount", 0.8), a + max(1, int(round(fx.get("over", 0.4) * fps))))

    # hard cuts: placement, dressing, visibility and faces never blend
    for rig in rigs.values():
        interp_all(rig, ["location", "rotation_euler", '["face"]'], 'CONSTANT')
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            interp_all(o.data, ["energy", "color"], 'CONSTANT')
            interp_all(o, ["rotation_euler"], 'CONSTANT')
        interp_all(o, ["hide_"], 'CONSTANT')
    for m in bpy.data.materials:
        if m.node_tree and m.node_tree.animation_data and m.get("set") is not None:
            interp_all(m.node_tree, ["nodes"], 'CONSTANT')
    interp_all(world.node_tree, ["nodes"], 'CONSTANT')
    # but bone motion inside a shot stays smooth: re-enable bezier on pose bones except root location
    for rig in rigs.values():
        for fc in fcurves_of(rig):
            if fc.data_path.startswith("pose.bones") and not fc.data_path.startswith('pose.bones["root"].location'):
                for kp in fc.keyframe_points:
                    if kp.interpolation == 'CONSTANT':
                        kp.interpolation = 'BEZIER'

    # ---- output: raw video, no audio (edit.py adds sound + captions)
    r = sc.render
    try:
        r.image_settings.media_type = 'VIDEO'
    except Exception:
        pass
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'
    r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'HIGH'
    r.ffmpeg.audio_codec = 'NONE'
    (ep / "render").mkdir(exist_ok=True)
    r.filepath = str(ep / "render" / "raw.mp4")
    sc.frame_set(1)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=str(ep / f"{data['episode']}.blend"))
    print("BUILT", ep / f"{data['episode']}.blend", sc.frame_end, "frames")
    return sc


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build(argv[0])
