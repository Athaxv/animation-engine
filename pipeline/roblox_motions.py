"""
Pose + motion library for roblox_rig (R6) characters.

Load AFTER roblox_rig.py into the same namespace:
    ns = {}
    exec(open(r".../pipeline/roblox_rig.py", encoding="utf-8").read(), ns)
    exec(open(r".../pipeline/roblox_motions.py", encoding="utf-8").read(), ns)
    ns["pose"](rig, "wave", frame=1)
    end = ns["walk"](rig, start=1, frames=60)

R6 = rigid parts, no elbows/knees: every pose is shoulders, hips, waist (spine) and head only,
like the real Roblox R6 animations. Times are frames (scene fps, 30 by default).

Axes cheat-sheet (degrees, pose-bone XYZ euler):
  hips/spine/head : X+ lean/nod forward, Y+ turn toward the character's left (+X), Z+ tilt toward -X
  arms/legs       : X- swing forward/up, X+ back;  L: Z- outward, Z+ inward;  R: Z+ outward, Z- inward
                    (once an arm is raised past horizontal, X < -90, the Z sign flips: L Z+ = outward)
  root            : location = world offset (x, y, z); rotation Z = heading (0 faces -Y / camera)
"""
import math, random
from mathutils import Vector

BODY_BONES = ["hips", "spine", "head", "upper_arm.L", "upper_arm.R", "upper_leg.L", "upper_leg.R"]
ARMS = ["upper_arm.L", "upper_arm.R"]
LEGS = ["upper_leg.L", "upper_leg.R"]

# ---------------------------------------------------------------- static poses (degrees)
# special keys: "root_z" (extra height), "root_rx" (tip the whole body about X)
POSES = {
    "stand":        {},
    "relaxed":      {"upper_arm.L": (0, 0, -3), "upper_arm.R": (0, 0, 3)},
    "hand_up":      {"upper_arm.L": (-172, 0, -12), "head": (-6, 0, 6), "spine": (0, 0, 3)},
    "arms_up":      {"upper_arm.L": (-176, 0, 12), "upper_arm.R": (-176, 0, -12), "spine": (-5, 0, 0), "head": (-12, 0, 0)},
    "celebrate":    {"upper_arm.L": (-150, 0, 38), "upper_arm.R": (-150, 0, -38), "spine": (-8, 0, 0), "head": (-15, 0, 0)},
    "point":        {"upper_arm.R": (-90, 0, 0), "spine": (0, -8, 0), "head": (0, -6, 0)},
    "point_side":   {"upper_arm.R": (-8, 0, 88), "head": (0, -25, 0), "spine": (0, -6, 0)},
    "point_up":     {"upper_arm.R": (-160, 0, 8), "head": (-22, 0, 0)},
    "wave":         {"upper_arm.L": (-10, 0, -158), "head": (0, 8, -6)},
    "shrug":        {"upper_arm.L": (-25, 0, -38), "upper_arm.R": (-25, 0, 38), "head": (0, 0, 12), "spine": (-3, 0, 0)},
    "explain":      {"upper_arm.L": (-38, 0, -10), "upper_arm.R": (-12, 0, 6), "head": (0, 6, -4)},
    "think":        {"upper_arm.R": (-128, 0, 34), "upper_arm.L": (-45, 0, 30), "head": (-8, 0, 8), "spine": (2, 0, 0)},
    "facepalm":     {"upper_arm.R": (-148, 0, 30), "head": (18, 0, 0), "spine": (8, 0, 0)},
    "hands_face":   {"upper_arm.L": (-150, 0, -26), "upper_arm.R": (-150, 0, 26), "head": (14, 0, 0), "spine": (6, 0, 0)},
    "arms_crossed": {"upper_arm.L": (-72, 0, 38), "upper_arm.R": (-78, 0, -38), "spine": (-4, 0, 0), "head": (-6, 0, 0)},
    "hands_hips":   {"upper_arm.L": (12, 0, -28), "upper_arm.R": (12, 0, 28), "spine": (-4, 0, 0), "head": (-5, 0, 0)},
    "scared":       {"upper_arm.L": (-62, 0, -22), "upper_arm.R": (-62, 0, 22), "spine": (-10, 0, 0), "head": (6, 0, 0),
                     "upper_leg.L": (-6, 0, -4), "upper_leg.R": (4, 0, 4)},
    "shocked":      {"upper_arm.L": (-25, 0, -55), "upper_arm.R": (-25, 0, 55), "spine": (-10, 0, 0), "head": (-10, 0, 0)},
    "sad":          {"spine": (14, 0, 0), "head": (24, 0, 0), "upper_arm.L": (6, 0, 2), "upper_arm.R": (6, 0, -2)},
    "angry":        {"upper_arm.L": (-15, 0, -20), "upper_arm.R": (-15, 0, 20), "spine": (10, 0, 0), "head": (-6, 0, 0)},
    "stop":         {"upper_arm.R": (-95, 0, 0), "spine": (-4, 0, 0), "head": (-4, 0, 0)},
    "hold":         {"upper_arm.L": (-50, 20, 0), "upper_arm.R": (-50, -20, 0)},     # holding a prop in front of the belly
    "yawn":         {"upper_arm.L": (-170, 0, 30), "upper_arm.R": (-170, 0, -30), "spine": (-12, 0, 0), "head": (-22, 0, 0)},
    "sit":          {"upper_leg.L": (-90, 0, 0), "upper_leg.R": (-90, 0, 0), "upper_arm.L": (-35, 0, 0), "upper_arm.R": (-35, 0, 0)},
    "lie":          {"root_rx": -90, "root_z": 0.5, "upper_arm.L": (0, 0, -4), "upper_arm.R": (0, 0, 4)},
    "run":          {"upper_arm.L": (55, 0, -6), "upper_arm.R": (-60, 0, 6), "upper_leg.L": (-50, 0, 0),
                     "upper_leg.R": (40, 0, 0), "spine": (12, 0, 0), "head": (-8, 0, 0)},
    "jump":         {"upper_arm.L": (-170, 0, 20), "upper_arm.R": (-170, 0, -20), "upper_leg.L": (-25, 0, 0),
                     "upper_leg.R": (10, 0, 0), "root_z": 1.2},
    # Phase 03: Storytelling & interaction poses
    "reach_forward": {"upper_arm.R": (-85, 0, 0), "head": (-4, 0, 0)},
    "receive_prop":  {"upper_arm.L": (-55, 25, 0), "upper_arm.R": (-55, -25, 0), "head": (-6, 0, 0)},
    "embrace":       {"upper_arm.L": (-75, 42, -10), "upper_arm.R": (-75, -42, 10), "spine": (6, 0, 0), "head": (12, -10, 0)},
    "handshake":     {"upper_arm.R": (-65, -8, 0), "spine": (0, 0, 0), "head": (0, -4, 0)},
    "push":          {"upper_arm.L": (-85, 12, 0), "upper_arm.R": (-85, -12, 0), "spine": (12, 0, 0)},
    "pickup":        {"upper_arm.R": (-25, -10, 0), "spine": (22, 0, 0), "head": (14, 0, 0)},
}
SEAT_HEIGHT = 1.5   # sitting: the legs' underside is this far above the root


# ---------------------------------------------------------------- key helpers
def _fcurves(rig):
    ad = rig.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if len(getattr(act, "fcurves", []) or []):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def _key(pb, frame, rot=True, loc=False):
    if rot:
        pb.keyframe_insert("rotation_euler", frame=frame)
    if loc:
        pb.keyframe_insert("location", frame=frame)


def set_interp(rig, bone, frame, mode='LINEAR', prop="location"):
    path = f'pose.bones["{bone}"].{prop}'
    for fc in _fcurves(rig):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.01:
                    kp.interpolation = mode


def _deg(t):
    return [math.radians(a) for a in t]


def _root_state(rig):
    r = rig.pose.bones["root"]
    if "base_loc" not in rig:
        rig["base_loc"] = list(r.location)
    return r


def pose(rig, name, frame, extra=None, keep_root=False):
    """Key a full-body pose; bones the pose doesn't list go back to rest."""
    spec = dict(POSES[name])
    if extra:
        spec.update(extra)
    pbs = rig.pose.bones
    for b in BODY_BONES:
        pbs[b].rotation_euler = _deg(spec.get(b, (0, 0, 0)))
        _key(pbs[b], frame)
    if not keep_root:
        root = pbs["root"]
        loc = Vector(rig.get("ground", (0.0, 0.0, 0.0)))
        root.location = (root.location.x, root.location.y, loc.z + spec.get("root_z", 0.0))
        heading = rig.get("heading", 0.0)
        root.rotation_euler = (math.radians(spec.get("root_rx", 0)), math.radians(spec.get("root_ry", 0)), heading)
        _key(root, frame, rot=True, loc=True)


def bone(rig, name, frame, rot=(0, 0, 0)):
    """Key one bone (degrees) without touching the others."""
    pb = rig.pose.bones[name]
    pb.rotation_euler = _deg(rot)
    _key(pb, frame)


def place(rig, frame, x=None, y=None, heading=None, z=None):
    """Put the character somewhere (world-ish offsets from the rig object) and key it."""
    root = rig.pose.bones["root"]
    if x is not None: root.location.x = x
    if y is not None: root.location.y = y
    if z is not None:
        root.location.z = z
        rig["ground"] = (0.0, 0.0, z)
    if heading is not None:
        rig["heading"] = math.radians(heading)
        root.rotation_euler.z = math.radians(heading)
    _key(root, frame, rot=True, loc=True)


def face(rig, name, frame):
    set_face(rig, name, frame)          # from roblox_rig.py


# ---------------------------------------------------------------- loops
def idle(rig, start, end, period=50, seed=0, base="relaxed"):
    """Breathing + tiny weight shifts so characters never freeze."""
    rnd = random.Random(seed)
    spec = POSES[base]
    pbs = rig.pose.bones
    f, i = start, 0
    while f <= end:
        s = 1 if i % 2 == 0 else -1
        def b(name, d):
            r = spec.get(name, (0, 0, 0))
            pbs[name].rotation_euler = _deg((r[0] + d[0], r[1] + d[1], r[2] + d[2]))
            _key(pbs[name], f)
        b("spine", (-1.2 * s, 0, 0.8 * s))
        b("head", (1.5 * s + rnd.uniform(-1.5, 1.5), rnd.uniform(-5, 5), -1.2 * s))
        b("upper_arm.L", (1.5 * s, 0, -1.5 - 1.2 * s))
        b("upper_arm.R", (-1.5 * s, 0, 1.5 + 1.2 * s))
        f += period // 2
        i += 1


def talk_gestures(rig, start, end, seed=0, every=(12, 22), energy=1.0):
    """Explaining arm/head beats while talking (pair with roblox_rig.talk for the mouth)."""
    rnd = random.Random(seed)
    pbs = rig.pose.bones
    f = start
    while f < end:
        side = rnd.choice("LR")
        sx = -1 if side == "L" else 1          # outward sign for Z
        o = "R" if side == "L" else "L"
        bone(rig, f"upper_arm.{side}", f, (rnd.uniform(-60, -20) * energy, 0, sx * rnd.uniform(4, 20) * energy))
        bone(rig, f"upper_arm.{o}", f, (rnd.uniform(-8, 0), 0, -sx * 4))
        bone(rig, "head", f, (rnd.uniform(-6, 8), rnd.uniform(-10, 10), rnd.uniform(-6, 6)))
        bone(rig, "spine", f, (rnd.uniform(-3, 4), rnd.uniform(-6, 6), 0))
        f += rnd.randint(*every)


def shiver(rig, start, end, amount=3.0, rate=2, base="scared", seed=0):
    """Fast tremble on top of a pose (scared / cold)."""
    rnd = random.Random(seed)
    spec = POSES[base]
    pbs = rig.pose.bones
    for f in range(start, end + 1, rate):
        for name in ("spine", "head", "upper_arm.L", "upper_arm.R"):
            r = spec.get(name, (0, 0, 0))
            pbs[name].rotation_euler = _deg((r[0] + rnd.uniform(-amount, amount), r[1] + rnd.uniform(-amount, amount),
                                             r[2] + rnd.uniform(-amount, amount)))
            _key(pbs[name], f)


# ---------------------------------------------------------------- locomotion
def _move(rig, start, frames, dist, heading_deg, period, swing_arm, swing_leg, lean, bob):
    pbs = rig.pose.bones
    root = pbs["root"]
    h = math.radians(heading_deg)
    rig["heading"] = h
    fwd = Vector((math.sin(h), -math.cos(h), 0))       # heading 0 walks toward -Y (the camera side)
    p0 = Vector(root.location)
    ground = p0.z
    # root: straight line, linear in time
    root.rotation_euler = (0, 0, h)
    root.location = p0
    _key(root, start, rot=True, loc=True)
    set_interp(rig, "root", start)
    p1 = p0 + fwd * dist
    root.location = p1
    _key(root, start + frames, rot=True, loc=True)
    # limbs: sine swing keyed at quarter phases (bezier makes it smooth)
    q = period / 4.0
    k = 0
    t = 0.0
    while t <= frames + 0.01:
        f = start + round(t)
        ph = (k % 4)
        s = (0, 1, 0, -1)[ph]
        bone(rig, "upper_leg.L", f, (-swing_leg * s, 0, 0))
        bone(rig, "upper_leg.R", f, (swing_leg * s, 0, 0))
        bone(rig, "upper_arm.L", f, (swing_arm * s, 0, -3))
        bone(rig, "upper_arm.R", f, (-swing_arm * s, 0, 3))
        bone(rig, "spine", f, (lean, 4 * s, 0))
        bone(rig, "head", f, (-lean * 0.5, -2 * s, 0))
        if bob:
            # bob on top of the linear root path (hips carry it)
            pbs["hips"].location = (0, bob * (1 - abs(s)), 0)
            _key(pbs["hips"], f, rot=False, loc=True)
        t += q
        k += 1
    end = start + frames
    set_interp(rig, "root", end)
    # settle
    pose(rig, "relaxed", end + 5)
    pbs["hips"].location = (0, 0, 0)
    _key(pbs["hips"], end + 5, rot=False, loc=True)
    return end + 5


def walk(rig, start, frames, speed=6.0, heading=0.0, period=20, fps=30):
    """R6 walk: stiff legs and arms swinging opposite. speed in studs/second. Returns the settle frame."""
    return _move(rig, start, frames, speed * frames / fps, heading, period, 32, 34, 2, 0.06)


def run(rig, start, frames, speed=14.0, heading=0.0, period=12, fps=30):
    return _move(rig, start, frames, speed * frames / fps, heading, period, 60, 52, 12, 0.15)


def walk_to(rig, start, x, y, speed=6.0, fps=30, running=False):
    """Walk from where the root is now to (x, y). Turns to face the target first."""
    root = rig.pose.bones["root"]
    d = Vector((x, y, 0)) - Vector((root.location.x, root.location.y, 0))
    if d.length < 1e-3:
        return start
    heading = math.degrees(math.atan2(d.x, -d.y))
    frames = max(4, round(d.length / (14.0 if running else speed) * fps))
    turn(rig, start, heading, 4)
    fn = run if running else walk
    return fn(rig, start + 4, frames, (14.0 if running else speed), heading, fps=fps)


def turn(rig, frame, heading, dur=6):
    root = rig.pose.bones["root"]
    _key(root, frame, rot=True, loc=False)
    rig["heading"] = math.radians(heading)
    root.rotation_euler.z = math.radians(heading)
    _key(root, frame + dur, rot=True, loc=False)
    return frame + dur


def jump(rig, frame, height=2.2, air=14):
    """Roblox jump: arms shoot up, hang in the air, land. Returns end frame."""
    root = rig.pose.bones["root"]
    z0 = root.location.z
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "jump", frame + 3, keep_root=True)
    for f, up in ((frame, 0), (frame + 3, 0), (frame + 3 + air // 2, height), (frame + 3 + air, 0)):
        root.location.z = z0 + up
        _key(root, f, rot=False, loc=True)
    end = frame + 3 + air
    pose(rig, "relaxed", end + 6, keep_root=True)
    return end + 6


def sit_down(rig, frame, seat_z, dur=8):
    """Sit on a seat whose top is at world height seat_z (relative to the rig object)."""
    root = rig.pose.bones["root"]
    pose(rig, "relaxed", frame, keep_root=True)
    _key(root, frame, rot=False, loc=True)
    pose(rig, "sit", frame + dur, keep_root=True)
    root.location.z = seat_z - SEAT_HEIGHT
    _key(root, frame + dur, rot=False, loc=True)
    return frame + dur


def stand_up(rig, frame, ground_z=0.0, dur=8):
    root = rig.pose.bones["root"]
    _key(root, frame, rot=False, loc=True)
    pose(rig, "relaxed", frame + dur, keep_root=True)
    root.location.z = ground_z
    _key(root, frame + dur, rot=False, loc=True)
    return frame + dur


def fall_back(rig, frame, dur=10):
    """Faint / fall flat on the back. Returns end frame."""
    root = rig.pose.bones["root"]
    z0 = root.location.z
    _key(root, frame, rot=True, loc=True)
    pose(rig, "shocked", frame + 3, keep_root=True)
    root.rotation_euler.x = math.radians(-90)
    root.location.z = z0 + 0.5
    _key(root, frame + dur, rot=True, loc=True)
    pose(rig, "lie", frame + dur + 2, keep_root=True)
    # small bounce on impact
    root.location.z = z0 + 0.65
    _key(root, frame + dur + 3, rot=False, loc=True)
    root.location.z = z0 + 0.5
    _key(root, frame + dur + 6, rot=False, loc=True)
    return frame + dur + 6


# ---------------------------------------------------------------- reactions / gestures
def wave(rig, frame, times=3, rate=5):
    pose(rig, "wave", frame, keep_root=True)
    f = frame + 4
    for i in range(times * 2):
        bone(rig, "upper_arm.L", f, (-10, 0, -140 if i % 2 == 0 else -172))
        f += rate
    pose(rig, "relaxed", f + 4, keep_root=True)
    return f + 4


def nod(rig, frame, times=2, amount=14, rate=5):
    pb = rig.pose.bones["head"]
    base = [math.degrees(a) for a in pb.rotation_euler]
    f = frame
    _key(pb, f)
    for _ in range(times):
        for d in (amount, 0):
            f += rate
            bone(rig, "head", f, (base[0] + d, base[1], base[2]))
    return f


def shake_head(rig, frame, times=2, amount=20, rate=4):
    pb = rig.pose.bones["head"]
    base = [math.degrees(a) for a in pb.rotation_euler]
    f = frame
    _key(pb, f)
    for _ in range(times):
        for d in (amount, -amount):
            f += rate
            bone(rig, "head", f, (base[0], base[1] + d, base[2]))
    f += rate
    bone(rig, "head", f, base)
    return f


def look_around(rig, frame, rate=10):
    f = frame
    for y in (0, 35, 35, -35, -35, 0):
        bone(rig, "head", f, (0, y, 0))
        f += rate // 2 if y == 0 else rate
    return f


def surprise_hop(rig, frame, height=0.6):
    """Shock reaction: tiny hop, arms flinch out, face goes 'shocked'."""
    root = rig.pose.bones["root"]
    z0 = root.location.z
    pose(rig, "relaxed", frame, keep_root=True)
    for f, up in ((frame, 0), (frame + 3, height), (frame + 7, 0)):
        root.location.z = z0 + up
        _key(root, f, rot=False, loc=True)
    pose(rig, "shocked", frame + 3, keep_root=True)
    face(rig, "shocked", frame + 2)
    return frame + 7


def laugh(rig, frame, dur=30, rate=4):
    """Lean back and bounce, face 'laugh'."""
    face(rig, "laugh", frame)
    f, i = frame, 0
    while f <= frame + dur:
        b = 1 if i % 2 == 0 else 0
        bone(rig, "spine", f, (-10 - 4 * b, 0, 0))
        bone(rig, "head", f, (-16 - 6 * b, 0, 0))
        bone(rig, "upper_arm.L", f, (-20, 0, 18 + 6 * b))
        bone(rig, "upper_arm.R", f, (-20, 0, -18 - 6 * b))
        f += rate; i += 1
    return f


def cry(rig, frame, dur=36, rate=3, seed=0):
    face(rig, "cry", frame)
    pose(rig, "hands_face", frame, keep_root=True)
    shiver(rig, frame + 4, frame + dur, 2.5, rate, "hands_face", seed)
    return frame + dur


def celebrate(rig, frame, hops=2):
    face(rig, "laugh", frame)
    f = frame
    for _ in range(hops):
        f = jump(rig, f, height=1.4, air=10) - 4
    pose(rig, "celebrate", f, keep_root=True)
    return f


def sleep(rig, frame, end, rate=40):
    """Lying asleep with slow breathing."""
    pose(rig, "lie", frame)
    face(rig, "sleep", frame)
    pbs = rig.pose.bones
    f, i = frame, 0
    while f <= end:
        pbs["spine"].rotation_euler = (math.radians(-2 if i % 2 else 0), 0, 0)
        _key(pbs["spine"], f)
        f += rate // 2; i += 1


# ---------------------------------------------------------------- Phase 03: Interactions & Choreography
def pickup(rig, frame, dur=18):
    """Bend waist, reach right arm down to prop/surface, lift up into hold pose."""
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "pickup", frame + max(4, dur // 3), keep_root=True)
    pose(rig, "hold", frame + dur, keep_root=True)
    return frame + dur


def drop(rig, frame, dur=12):
    """Release prop from hold pose down to relaxed."""
    pose(rig, "hold", frame, keep_root=True)
    pose(rig, "relaxed", frame + dur, keep_root=True)
    return frame + dur


def pass_prop(rig, frame, dur=22):
    """Extend arm forward offering held prop, hold for contact, recover to relaxed."""
    pose(rig, "hold", frame, keep_root=True)
    pose(rig, "reach_forward", frame + 8, keep_root=True)
    pose(rig, "relaxed", frame + dur, keep_root=True)
    return frame + dur


def catch_prop(rig, frame, dur=22):
    """Extend arms forward in receiving pose, receive prop into hold pose."""
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "receive_prop", frame + 6, keep_root=True)
    pose(rig, "hold", frame + 14, keep_root=True)
    return frame + dur


def handshake(rig, frame, dur=24):
    """Reach right arm forward, perform 3-cycle shake rhythm, recover to relaxed."""
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "handshake", frame + 6, keep_root=True)
    f = frame + 8
    for i in range(3):
        d = 4 if i % 2 == 0 else -4
        bone(rig, "upper_arm.R", f, (-65 + d, -8, 0))
        f += 4
    pose(rig, "relaxed", frame + dur, keep_root=True)
    return frame + dur


def hug(rig, frame, dur=28):
    """Open arms and wrap around partner in warm embrace, hold, then step back."""
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "embrace", frame + 8, keep_root=True)
    pose(rig, "relaxed", frame + dur, keep_root=True)
    return frame + dur


def approach(rig, start, x, y, speed=6.0, fps=30):
    """Walk to target with smooth deceleration and turn to face."""
    return walk_to(rig, start, x, y, speed=speed, fps=fps, running=False)


def push_prop(rig, frame, dur=24):
    """Hands braced forward pushing an object, leaning forward with spine."""
    pose(rig, "relaxed", frame, keep_root=True)
    pose(rig, "push", frame + 6, keep_root=True)
    pose(rig, "relaxed", frame + dur, keep_root=True)
    return frame + dur

