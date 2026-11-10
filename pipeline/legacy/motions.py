"""
Body motion library for blocky_rig characters.

Load AFTER blocky_rig.py into the same namespace:
    ns = {}
    exec(open(".../pipeline/blocky_rig.py").read(), ns)
    exec(open(".../pipeline/motions.py").read(), ns)

Axes cheat-sheet (degrees, pose-bone XYZ euler):
  hips/spine/neck/head : X+ lean/nod forward, Y+ turn toward the character's left (+X), Z+ tilt toward -X
  arms/legs            : X- swing forward/up, X+ back;  Z- = left arm outward, Z+ = right arm outward
  lower_arm            : X- bends elbow (forearm up/forward)
  hips location        : (side, up, forward) in bone-local axes
"""
import math, random
from mathutils import Vector

ARM_BONES = ["upper_arm.L", "lower_arm.L", "hand.L", "upper_arm.R", "lower_arm.R", "hand.R"]
BODY_BONES = ["hips", "spine", "neck", "head"] + ARM_BONES

POSES = {
    "stand":        {},
    "relaxed":      {"upper_arm.L": (0, 0, -4), "upper_arm.R": (0, 0, 4),
                     "lower_arm.L": (-12, 0, 0), "lower_arm.R": (-12, 0, 0)},
    "arms_up":      {"upper_arm.L": (-170, 0, 14), "upper_arm.R": (-170, 0, -14), "spine": (-6, 0, 0), "head": (-12, 0, 0)},
    "point":        {"upper_arm.R": (-88, 0, 0), "spine": (0, -8, 0), "head": (0, -5, 0)},
    "wave":         {"upper_arm.L": (0, 0, -150), "lower_arm.L": (0, 0, 20), "head": (0, 8, -6)},
    "shrug":        {"upper_arm.L": (-15, 0, -28), "lower_arm.L": (-75, 0, 0), "upper_arm.R": (-15, 0, 28),
                     "lower_arm.R": (-75, 0, 0), "head": (0, 0, 10), "neck": (-6, 0, 0)},
    "facepalm":     {"upper_arm.R": (-62, -38, 0), "lower_arm.R": (-105, 0, 0), "head": (24, 0, 0), "spine": (8, 0, 0)},
    "think":        {"upper_arm.R": (-35, -28, 0), "lower_arm.R": (-125, 0, 0), "upper_arm.L": (-22, 45, 0),
                     "lower_arm.L": (-85, 0, 0), "head": (-8, 0, 8)},
    "scared":       {"upper_arm.L": (-28, 0, -20), "lower_arm.L": (-62, 0, 0), "upper_arm.R": (-28, 0, 20),
                     "lower_arm.R": (-62, 0, 0), "spine": (-8, 0, 0), "head": (6, 0, 0), "hips_loc": (0, -0.08, 0.15)},
    "arms_crossed": {"upper_arm.L": (-28, 0, 10), "lower_arm.L": (-100, 88, 0), "upper_arm.R": (-14, 0, -10),
                     "lower_arm.R": (-92, -88, 0), "spine": (-4, 0, 0), "head": (-6, 0, 0)},
    "hands_on_hips": {"upper_arm.L": (10, 0, -42), "lower_arm.L": (-10, 0, 88), "upper_arm.R": (10, 0, 42),
                      "lower_arm.R": (-10, 0, -88), "spine": (-4, 0, 0)},
    "explain":      {"upper_arm.L": (-20, 0, -14), "lower_arm.L": (-65, 0, 0), "upper_arm.R": (-8, 0, 6),
                     "lower_arm.R": (-20, 0, 0), "head": (0, 6, -4)},
    "sad_slump":    {"spine": (14, 0, 0), "head": (24, 0, 0), "upper_arm.L": (6, 0, 2), "upper_arm.R": (6, 0, -2)},
    "celebrate":    {"upper_arm.L": (-150, 0, 38), "upper_arm.R": (-150, 0, -38), "lower_arm.L": (0, 0, 15),
                     "lower_arm.R": (0, 0, -15), "head": (-15, 0, 0), "spine": (-8, 0, 0)},
}


def _key_bone(pb, frame, rot=True, loc=False):
    if rot:
        pb.keyframe_insert("rotation_euler", frame=frame)
    if loc:
        pb.keyframe_insert("location", frame=frame)


def pose(rig, name, frame, extra=None):
    """Key a full upper-body pose (unlisted bones go back to rest)."""
    spec = dict(POSES[name])
    if extra:
        spec.update(extra)
    pbs = rig.pose.bones
    for b in BODY_BONES:
        r = spec.get(b, (0, 0, 0))
        pbs[b].rotation_euler = [math.radians(a) for a in r]
        _key_bone(pbs[b], frame)
    pbs["hips"].location = spec.get("hips_loc", (0, 0, 0))
    _key_bone(pbs["hips"], frame, rot=False, loc=True)


def offset_bone(rig, bone, frame, rot=(0, 0, 0)):
    """Key one bone rotation (degrees) without touching others."""
    pb = rig.pose.bones[bone]
    pb.rotation_euler = [math.radians(a) for a in rot]
    _key_bone(pb, frame)


def nod(rig, frame, times=2, amount=14, rate=5):
    pb = rig.pose.bones["head"]
    base = tuple(math.degrees(a) for a in pb.rotation_euler)
    f = frame
    for _ in range(times):
        for d in (amount, 0):
            pb.rotation_euler = [math.radians(base[0] + d), math.radians(base[1]), math.radians(base[2])]
            _key_bone(pb, f); f += rate
    return f


def shake_head(rig, frame, times=2, amount=18, rate=4):
    pb = rig.pose.bones["head"]
    base = tuple(math.degrees(a) for a in pb.rotation_euler)
    f = frame
    for _ in range(times):
        for d in (amount, -amount):
            pb.rotation_euler = [math.radians(base[0]), math.radians(base[1] + d), math.radians(base[2])]
            _key_bone(pb, f); f += rate
    pb.rotation_euler = [math.radians(a) for a in base]
    _key_bone(pb, f)
    return f


def idle(rig, start, end, period=48, seed=0):
    """Subtle breathing + weight shift so characters never freeze."""
    rnd = random.Random(seed)
    pbs = rig.pose.bones
    f = start
    i = 0
    while f <= end:
        s = 1 if i % 2 == 0 else -1
        pbs["spine"].rotation_euler = (math.radians(-1.5 * s), 0, math.radians(1.2 * s))
        pbs["head"].rotation_euler = (math.radians(1.5 * s + rnd.uniform(-1, 1)), math.radians(rnd.uniform(-4, 4)), math.radians(-1.5 * s))
        pbs["upper_arm.L"].rotation_euler = (math.radians(2 * s), 0, math.radians(-3 - 1.5 * s))
        pbs["upper_arm.R"].rotation_euler = (math.radians(-2 * s), 0, math.radians(3 + 1.5 * s))
        pbs["hips"].location = (0.03 * s, 0.015 * s, 0)
        for b in ("spine", "head", "upper_arm.L", "upper_arm.R"):
            _key_bone(pbs[b], f)
        _key_bone(pbs["hips"], f, rot=False, loc=True)
        f += period // 2
        i += 1


def talk_gestures(rig, start, end, seed=0, every=(14, 26)):
    """Explaining-style arm/head beats while talking (pair with talk())."""
    rnd = random.Random(seed)
    pbs = rig.pose.bones
    f = start
    while f < end:
        side = rnd.choice("LR")
        sx = -1 if side == "L" else 1
        ua = pbs[f"upper_arm.{side}"]; la = pbs[f"lower_arm.{side}"]
        ua.rotation_euler = (math.radians(rnd.uniform(-35, -10)), 0, math.radians(sx * rnd.uniform(4, 18)))
        la.rotation_euler = (math.radians(rnd.uniform(-80, -40)), 0, 0)
        pbs["head"].rotation_euler = (math.radians(rnd.uniform(-6, 8)), math.radians(rnd.uniform(-10, 10)), math.radians(rnd.uniform(-6, 6)))
        pbs["spine"].rotation_euler = (math.radians(rnd.uniform(-3, 4)), math.radians(rnd.uniform(-5, 5)), 0)
        for pb in (ua, la, pbs["head"], pbs["spine"]):
            _key_bone(pb, f)
        o = "R" if side == "L" else "L"
        pbs[f"upper_arm.{o}"].rotation_euler = (0, 0, math.radians(-sx * 4))
        pbs[f"lower_arm.{o}"].rotation_euler = (math.radians(-12), 0, 0)
        _key_bone(pbs[f"upper_arm.{o}"], f); _key_bone(pbs[f"lower_arm.{o}"], f)
        f += rnd.randint(*every)


def _foot_local(rig, side, world_off):
    m = rig.data.bones["foot_ik." + side].matrix_local.to_3x3()
    return m.transposed() @ Vector(world_off)


def set_feet(rig, frame, l=(0, 0, 0), r=(0, 0, 0)):
    """Place IK feet (offsets in root space: x side, y back(+)/forward(-), z up)."""
    for side, off in (("L", l), ("R", r)):
        pb = rig.pose.bones["foot_ik." + side]
        pb.location = _foot_local(rig, side, off)
        _key_bone(pb, frame, rot=False, loc=True)


def walk(rig, start, frames, stride=1.4, period=20, heading_deg=0.0, arm_swing=28, lift=0.35):
    """Walk forward (character's -Y, rotated by heading) for `frames` frames.
    Moves the root bone; feet stay planted thanks to IK. Returns end frame."""
    pbs = rig.pose.bones
    root = pbs["root"]
    h = math.radians(heading_deg)
    fwd = Vector((math.sin(h), -math.cos(h), 0))
    root.rotation_euler = (0, 0, h)
    start_loc = Vector(root.location)
    speed = stride / (period / 2)
    for f in range(start, start + frames + 1, 2):
        t = f - start
        ph = (t % period) / period
        root.location = start_loc + fwd * (speed * t)
        _key_bone(root, f, rot=True, loc=True)
        offs = {}
        for side, p0 in (("L", 0.0), ("R", 0.5)):
            p = (ph + p0) % 1.0
            if p < 0.5:
                y = -stride / 2 + stride * (p / 0.5)
                z = 0.0
            else:
                q = (p - 0.5) / 0.5
                y = stride / 2 - stride * q
                z = lift * math.sin(math.pi * q)
            offs[side] = (0, y, z)
        set_feet(rig, f, offs["L"], offs["R"])
        sw = math.sin(2 * math.pi * ph)
        pbs["upper_arm.L"].rotation_euler = (math.radians(arm_swing * sw), 0, math.radians(-4))
        pbs["upper_arm.R"].rotation_euler = (math.radians(-arm_swing * sw), 0, math.radians(4))
        pbs["lower_arm.L"].rotation_euler = (math.radians(-15 - 10 * max(0, -sw)), 0, 0)
        pbs["lower_arm.R"].rotation_euler = (math.radians(-15 - 10 * max(0, sw)), 0, 0)
        pbs["spine"].rotation_euler = (math.radians(3), math.radians(5 * sw), 0)
        pbs["hips"].location = (0, -0.08 + 0.08 * abs(math.cos(2 * math.pi * ph)), 0)
        for b in ("upper_arm.L", "upper_arm.R", "lower_arm.L", "lower_arm.R", "spine"):
            _key_bone(pbs[b], f)
        _key_bone(pbs["hips"], f, rot=False, loc=True)
    end = start + frames
    set_feet(rig, end + 4)
    pose(rig, "relaxed", end + 4)
    return end + 4


def jump(rig, frame, height=1.2, air=12):
    """Anticipation squat -> jump -> land. Returns end frame."""
    pbs = rig.pose.bones
    root = pbs["root"]
    base = Vector(root.location)
    seq = [
        (frame, 0, 0.0, "relaxed"),
        (frame + 5, 0, -0.4, "scared"),
        (frame + 8, 0.2, 0.0, "arms_up"),
        (frame + 8 + air // 2, height, 0.0, "arms_up"),
        (frame + 8 + air, 0.0, 0.0, "relaxed"),
        (frame + 8 + air + 4, 0, -0.3, "relaxed"),
        (frame + 8 + air + 10, 0, 0.0, "relaxed"),
    ]
    for f, up, squat, p in seq:
        root.location = base + Vector((0, 0, up))
        _key_bone(root, f, rot=False, loc=True)
        pose(rig, p, f, {"hips_loc": (0, squat, 0)})
    return seq[-1][0]


def surprise_hop(rig, frame):
    """Classic shocked reaction: tiny hop + arms flinch + wide eyes."""
    pbs = rig.pose.bones
    root = pbs["root"]
    base = Vector(root.location)
    for f, up, p in ((frame, 0, "relaxed"), (frame + 3, 0.35, "scared"), (frame + 7, 0, "scared")):
        root.location = base + Vector((0, 0, up))
        _key_bone(root, f, rot=False, loc=True)
        pose(rig, p, f)
    set_expression(rig, "neutral", frame)
    set_expression(rig, "shocked", frame + 2)
    return frame + 7
