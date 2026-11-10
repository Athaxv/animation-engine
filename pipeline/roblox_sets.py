"""
Bright Roblox-style locations for "In this town" stories (look: @kr.editzx0, see STYLE_REFERENCE.md).

Load AFTER roblox_rig.py (uses new_mat / add_bump / rbox / Canvas / _cyl_mesh / _sphere_mesh):
    ns = {}
    exec(open(r".../pipeline/roblox_rig.py", encoding="utf-8").read(), ns)
    exec(open(r".../pipeline/roblox_sets.py", encoding="utf-8").read(), ns)
    coll = ns["build_set"]("bedroom")            # -> collection "Set_bedroom"
    ns["apply_dressing"]("bedroom", "night")
    ns["place_at_mark"](rig, "bedroom", "bedside")

Conventions (same as the old sets.py, so the episode builder keeps working)
  * 1 unit = 1 stud. Characters are ~5.9 tall and face -Y. The camera usually sits at -Y looking +Y.
  * Marks are empties  mark_<set>_<name>; rotation z = default facing (0 = toward -Y/camera).
    A mark's z is the floor height there (bed marks sit on the mattress).
  * Lights carry  dress_<dressing> = energy; anything with  only_dressing  shows in that dressing only.
  * Window glass materials carry  dress_<dressing> = (r, g, b, emission).
"""
import bpy, bmesh, math, random
from mathutils import Vector

SET_NAMES = ["bedroom", "street", "kitchen", "classroom"]
DRESSINGS = {
    "bedroom": ["day", "night"],
    "street": ["day", "sunset"],
    "kitchen": ["day"],
    "classroom": ["day"],
}
# sky seen by the camera (sRGB) and the light it gives, per dressing
WORLDS = {
    "day":    ((0.42, 0.72, 1.0), (0.85, 0.92, 1.0), 0.55),
    "sunset": ((1.0, 0.62, 0.42), (1.0, 0.8, 0.65), 0.45),
    "night":  ((0.06, 0.08, 0.2), (0.3, 0.36, 0.65), 0.35),
}


# ---------------------------------------------------------------- materials
def _nodes(m):
    return m.node_tree.nodes, m.node_tree.links


def plastic(name, rgb, rough=0.42, bump=0.03):
    m = new_mat(f"S_{name}", rgb, rough, 0.45)
    return add_bump(m, 25, bump, 2) if bump else m


def matte(name, rgb, rough=0.85):
    return add_bump(new_mat(f"S_{name}", rgb, rough, 0.2), 40, 0.05, 3, tint=0.04)


def fabric(name, rgb):
    return add_bump(new_mat(f"S_{name}", rgb, 0.9, 0.15), 120, 0.25, 6, tint=0.08)


def wood(name, rgb, plank=1.6, along="X"):
    """Planks: dark seams every `plank` studs + grain."""
    m = new_mat(f"S_{name}", rgb, 0.55, 0.35)
    N, L = _nodes(m)
    b = _bsdf(m)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sep.inputs[0])
    ax = sep.outputs["Y" if along == "X" else "X"]
    wv = N.new("ShaderNodeTexWave"); wv.wave_profile = 'SAW'
    wv.inputs["Scale"].default_value = 1.0 / plank; wv.inputs["Distortion"].default_value = 0.0
    comb = N.new("ShaderNodeCombineXYZ"); L.new(ax, comb.inputs[0])
    try:
        wv.bands_direction = 'X'
    except Exception:
        pass
    L.new(comb.outputs[0], wv.inputs["Vector"])
    seam = N.new("ShaderNodeMapRange")
    seam.inputs["From Min"].default_value = 0.0; seam.inputs["From Max"].default_value = 0.04
    L.new(wv.outputs["Fac"], seam.inputs["Value"])
    grain = N.new("ShaderNodeTexNoise"); grain.inputs["Scale"].default_value = 3.0; grain.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Object"], grain.inputs["Vector"])
    base = tuple(b.inputs["Base Color"].default_value)
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = tuple(c * 0.78 for c in base[:3]) + (1,)
    ramp.color_ramp.elements[1].color = base
    L.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    mix = N.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    L.new(seam.outputs["Result"], mix.inputs["Factor"])
    mix.inputs[6].default_value = tuple(c * 0.45 for c in base[:3]) + (1,)
    L.new(ramp.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.25
    L.new(seam.outputs["Result"], bp.inputs["Height"])
    L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def brick(name, rgb, mortar=(0.93, 0.9, 0.86), scale=0.6):
    m = new_mat(f"S_{name}", rgb, 0.8, 0.2)
    N, L = _nodes(m)
    b = _bsdf(m)
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Object"], sep.inputs[0])
    add = N.new("ShaderNodeMath"); add.operation = 'ADD'
    L.new(sep.outputs["X"], add.inputs[0]); L.new(sep.outputs["Y"], add.inputs[1])
    comb = N.new("ShaderNodeCombineXYZ"); L.new(add.outputs[0], comb.inputs[0]); L.new(sep.outputs["Z"], comb.inputs[1])
    br = N.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = scale
    c = b.inputs["Base Color"].default_value
    br.inputs["Color1"].default_value = c
    br.inputs["Color2"].default_value = tuple(x * 0.85 for x in c[:3]) + (1,)
    br.inputs["Mortar"].default_value = (*srgb(mortar), 1)
    br.inputs["Mortar Size"].default_value = 0.025
    br.inputs["Brick Width"].default_value = 0.5; br.inputs["Row Height"].default_value = 0.25
    L.new(comb.outputs[0], br.inputs["Vector"])
    L.new(br.outputs["Color"], b.inputs["Base Color"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; bp.invert = True
    L.new(br.outputs["Fac"], bp.inputs["Height"])
    L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def checker(name, c1, c2, size=2.0):
    m = new_mat(f"S_{name}", c1, 0.35, 0.5)
    N, L = _nodes(m)
    b = _bsdf(m)
    tc = N.new("ShaderNodeTexCoord")
    ck = N.new("ShaderNodeTexChecker"); ck.inputs["Scale"].default_value = 1.0 / size
    ck.inputs["Color1"].default_value = (*srgb(c1), 1); ck.inputs["Color2"].default_value = (*srgb(c2), 1)
    L.new(tc.outputs["Object"], ck.inputs["Vector"])
    L.new(ck.outputs["Color"], b.inputs["Base Color"])
    return m


def grass_mat():
    return add_bump(new_mat("S_Grass", (0.36, 0.78, 0.3), 0.9, 0.2), 8, 0.3, 6, tint=0.25)


def asphalt_mat():
    return add_bump(new_mat("S_Asphalt", (0.27, 0.28, 0.31), 0.85, 0.2), 30, 0.25, 8, tint=0.2)


def glass(name, day=(0.55, 0.82, 1.0), night=(0.05, 0.08, 0.2), glow_day=0.9, glow_night=0.25, interior=True):
    """Window glass. Interior windows glow like the sky outside; exterior ones are glossy blue."""
    m = new_mat(f"S_{name}", day, 0.05 if not interior else 0.3, 0.8)
    b = _bsdf(m)
    if interior:
        b.inputs["Emission Color"].default_value = (*srgb(day), 1)
        b.inputs["Emission Strength"].default_value = glow_day
    m["dress_day"] = (*day, glow_day)
    m["dress_sunset"] = (1.0, 0.75, 0.55, glow_day * 0.8)
    m["dress_night"] = (*night, glow_night)
    m["interior"] = interior
    return m


def face_image(name, draw, size=512):
    """Paint a small texture with the rig's Canvas (clock faces, posters...)."""
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.new(name, size, size, alpha=True)
    c = Canvas(size)
    draw(c)
    img.pixels.foreach_set(c.rgba.astype(np.float32).ravel())
    img.update(); img.pack()
    return img


def image_mat(name, img, base_rgb=(1, 1, 1), rough=0.4):
    m = new_mat(f"S_{name}", base_rgb, rough, 0.4)
    N, L = _nodes(m)
    b = _bsdf(m)
    tx = N.new("ShaderNodeTexImage"); tx.image = img; tx.extension = 'CLIP'
    mix = N.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    L.new(tx.outputs["Alpha"], mix.inputs["Factor"])
    mix.inputs[6].default_value = b.inputs["Base Color"].default_value
    L.new(tx.outputs["Color"], mix.inputs[7])
    L.new(mix.outputs[2], b.inputs["Base Color"])
    return m


# ---------------------------------------------------------------- geometry helpers
def blk(coll, name, size, center, mat, bevel=0.05, rot=None):
    ob = rbox(name, coll, size, center, mat, bevel, 3)
    if rot:
        ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def cyl(coll, name, r, depth, center, mat, rot=(0, 0, 0), segs=32, r2=None):
    ob = bpy.data.objects.new(name, _cyl_mesh(name, r, r if r2 is None else r2, depth, segs))
    coll.objects.link(ob)
    ob.location = center; ob.rotation_euler = [math.radians(a) for a in rot]
    ob.data.materials.append(mat)
    return ob


def ball(coll, name, r, center, mat, scale=(1, 1, 1), lumpy=0.0, seed=0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=r)
    if lumpy:
        rnd = random.Random(seed)
        bumps = [(Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.3, 1))).normalized(), rnd.uniform(0.5, 1.0))
                 for _ in range(9)]
        for v in bm.verts:
            n = v.co.normalized()
            k = sum(max(0.0, n.dot(d)) ** 6 * s for d, s in bumps)
            v.co *= 1 + lumpy * k
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    ob.location = center; ob.scale = scale
    me.materials.append(mat)
    return ob


def mark(coll, set_name, name, loc, facing_deg=0.0):
    e = bpy.data.objects.new(f"mark_{set_name}_{name}", None)
    e.empty_display_type = 'SINGLE_ARROW'; e.empty_display_size = 1.5
    e.location = loc; e.rotation_euler = (0, 0, math.radians(facing_deg))
    e["mark"] = name
    coll.objects.link(e)
    return e


def light(coll, name, kind, loc, rot=(0, 0, 0), color=(1, 1, 1), dress=None, size=1.0, spot_deg=45):
    ld = bpy.data.lights.new(name, kind)
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    elif kind == 'SPOT':
        ld.spot_size = math.radians(spot_deg); ld.spot_blend = 0.5; ld.shadow_soft_size = size
    elif kind == 'POINT':
        ld.shadow_soft_size = size
    elif kind == 'SUN':
        ld.angle = math.radians(size)
    ob = bpy.data.objects.new(name, ld); coll.objects.link(ob)
    ob.location = loc; ob.rotation_euler = [math.radians(a) for a in rot]
    for k, v in (dress or {}).items():
        ob[f"dress_{k}"] = v
    return ob


def sun(coll, set_name, dress):
    """Shared sun: dress = {dressing: (energy, elevation_deg, azimuth_deg, color)}"""
    s = light(coll, f"{set_name}_Sun", 'SUN', (0, 0, 30), size=3)
    for k, (e, el, az, col) in dress.items():
        s[f"dress_{k}"] = e
        s[f"dress_rot_{k}"] = [90 - el, 0, az]
        s[f"dress_col_{k}"] = col
    return s


# ---------------------------------------------------------------- props
def window(coll, n, center, w, h, frame_mat, glass_mat, axis="X", sill=True, curtains=None):
    """Window in a wall plane. axis = direction the wall runs ('X' -> wall faces Y)."""
    x, y, z = center
    t = 0.35
    if axis == "X":
        S = lambda sx, sz, d=t: (sx, d, sz)
    else:
        S = lambda sx, sz, d=t: (d, sx, sz)
    off = (lambda dx, dz, dy=0: (x + dx, y + dy, z + dz)) if axis == "X" else (lambda dx, dz, dy=0: (x + dy, y + dx, z + dz))
    blk(coll, f"{n}_Glass", S(w, h, 0.08), center, glass_mat, 0.0)
    fw = 0.35
    blk(coll, f"{n}_FrT", S(w + 2 * fw, fw), off(0, h / 2 + fw / 2), frame_mat, 0.06)
    blk(coll, f"{n}_FrB", S(w + 2 * fw, fw), off(0, -h / 2 - fw / 2), frame_mat, 0.06)
    blk(coll, f"{n}_FrL", S(fw, h), off(-w / 2 - fw / 2, 0), frame_mat, 0.06)
    blk(coll, f"{n}_FrR", S(fw, h), off(w / 2 + fw / 2, 0), frame_mat, 0.06)
    blk(coll, f"{n}_FrV", S(0.2, h, 0.25), off(0, 0), frame_mat, 0.04)
    blk(coll, f"{n}_FrH", S(w, 0.2, 0.25), off(0, 0), frame_mat, 0.04)
    if sill:
        blk(coll, f"{n}_Sill", S(w + 1.0, 0.25, 0.9), off(0, -h / 2 - fw - 0.1), frame_mat, 0.06)
    if curtains:
        for s in (-1, 1):
            blk(coll, f"{n}_Curtain{s}", S(1.3, h + 1.6, 0.25), off(s * (w / 2 + 0.9), -0.1, -0.3), curtains, 0.2)
        blk(coll, f"{n}_Rod", S(w + 4.5, 0.15, 0.15), off(0, h / 2 + 0.9, -0.35), frame_mat, 0.04)


def door(coll, n, center, mat, knob_mat, axis="X", w=4.0, h=7.6, sign=-1):
    x, y, z = center
    if axis == "X":
        blk(coll, n, (w, 0.35, h), (x, y, z + h / 2), mat, 0.06)
        for k, zz in enumerate((h * 0.72, h * 0.3)):
            blk(coll, f"{n}_Panel{k}", (w - 1.2, 0.1, h * 0.32), (x, y + sign * 0.2, z + zz), mat, 0.04)
        ball(coll, f"{n}_Knob", 0.2, (x + w / 2 - 0.55, y + sign * 0.3, z + h * 0.48), knob_mat)
    else:
        blk(coll, n, (0.35, w, h), (x, y, z + h / 2), mat, 0.06)
        for k, zz in enumerate((h * 0.72, h * 0.3)):
            blk(coll, f"{n}_Panel{k}", (0.1, w - 1.2, h * 0.32), (x + sign * 0.2, y, z + zz), mat, 0.04)
        ball(coll, f"{n}_Knob", 0.2, (x + sign * 0.3, y + w / 2 - 0.55, z + h * 0.48), knob_mat)


def clock_image(name="ClockFace", hour=7, minute=0):
    def draw(c):
        c.ellipse(0.5, 0.5, 0.48, 0.48, (0.08, 0.08, 0.1))
        c.ellipse(0.5, 0.5, 0.44, 0.44, (1, 1, 1))
        for k in range(12):
            a = math.pi / 2 - 2 * math.pi * k / 12
            r0, r1 = (0.33, 0.41) if k % 3 else (0.3, 0.41)
            c.line([(0.5 + r0 * math.cos(a), 0.5 + r0 * math.sin(a)), (0.5 + r1 * math.cos(a), 0.5 + r1 * math.sin(a))],
                   0.012 if k % 3 else 0.02, (0.08, 0.08, 0.1))
        ah = math.pi / 2 - 2 * math.pi * ((hour % 12) + minute / 60) / 12
        am = math.pi / 2 - 2 * math.pi * minute / 60
        c.line([(0.5, 0.5), (0.5 + 0.2 * math.cos(ah), 0.5 + 0.2 * math.sin(ah))], 0.022, (0.08, 0.08, 0.1))
        c.line([(0.5, 0.5), (0.5 + 0.32 * math.cos(am), 0.5 + 0.32 * math.sin(am))], 0.014, (0.08, 0.08, 0.1))
        c.ellipse(0.5, 0.5, 0.03, 0.03, (0.9, 0.15, 0.15))
    return face_image(name, draw)


def wall_clock(coll, n, center, r=1.3, axis="X", rim=(0.95, 0.3, 0.3), hour=7):
    rot = (90, 0, 0) if axis == "X" else (90, 0, 90)
    cyl(coll, f"{n}_Rim", r, 0.35, center, plastic(f"{n}Rim", rim), rot, 48)
    dial = cyl(coll, f"{n}_Dial", r * 0.88, 0.4, center, image_mat(f"{n}Dial", clock_image(f"{n}Face", hour)), rot, 48)
    # planar UV for the dial cap
    me = dial.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 + v.x / (2 * r * 0.88), 0.5 + v.y / (2 * r * 0.88))


def alarm_clock(coll, n, center, col=(0.95, 0.2, 0.2)):
    x, y, z = center
    body = plastic(f"{n}Body", col)
    metal = new_mat("S_Chrome", (0.85, 0.85, 0.88), 0.15, 0.8); _bsdf(metal).inputs["Metallic"].default_value = 1.0
    cyl(coll, f"{n}_Body", 0.75, 0.55, (x, y, z + 0.8), body, (90, 0, 0), 40)
    d = cyl(coll, f"{n}_Dial", 0.62, 0.6, (x, y - 0.02, z + 0.8), image_mat(f"{n}Dial", clock_image(f"{n}Face", 7)), (90, 0, 0), 40)
    me = d.data; uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 + v.x / 1.24, 0.5 + v.y / 1.24)
    for s in (-1, 1):
        ball(coll, f"{n}_Bell{s}", 0.32, (x + s * 0.45, y + 0.05, z + 1.55), metal, (1, 1, 0.75))
        blk(coll, f"{n}_Leg{s}", (0.12, 0.12, 0.35), (x + s * 0.45, y, z + 0.12), metal, 0.03, (0, s * 20, 0))
    blk(coll, f"{n}_Hammer", (0.08, 0.08, 0.35), (x, y + 0.05, z + 1.65), metal, 0.02)


def bed(coll, n, x, y, frame_col=(0.82, 0.55, 0.32), blanket=(1.0, 0.72, 0.28), length=8.0, width=5.6):
    """Bed along Y, headboard at +Y. Mattress top at z = 3.0."""
    fr = wood(f"{n}Frame", frame_col, 0.8)
    blk(coll, f"{n}_Base", (width, length, 1.6), (x, y, 1.0), fr, 0.15)
    for s in (-1, 1):
        blk(coll, f"{n}_Leg{s}", (0.6, 0.6, 0.6), (x + s * (width / 2 - 0.4), y - length / 2 + 0.4, 0.3), fr, 0.08)
    blk(coll, f"{n}_Head", (width + 0.4, 0.6, 5.0), (x, y + length / 2, 2.5), fr, 0.25)
    blk(coll, f"{n}_Foot", (width + 0.4, 0.5, 2.6), (x, y - length / 2, 1.3), fr, 0.2)
    blk(coll, f"{n}_Mattress", (width - 0.3, length - 0.6, 1.0), (x, y, 2.4), fabric(f"{n}Mattress", (0.97, 0.97, 0.98)), 0.3)
    blk(coll, f"{n}_Blanket", (width + 0.1, length * 0.62, 0.35), (x, y - length * 0.17, 2.95), fabric(f"{n}Blanket", blanket), 0.18)
    blk(coll, f"{n}_Fold", (width + 0.15, 0.9, 0.45), (x, y + length * 0.12, 3.0), fabric(f"{n}Fold", (0.98, 0.98, 0.98)), 0.2)
    blk(coll, f"{n}_Pillow", (width * 0.7, 1.6, 0.7), (x, y + length / 2 - 1.3, 3.2), fabric(f"{n}Pillow", (1, 1, 1)), 0.35)


def nightstand(coll, n, x, y, col=(0.98, 0.98, 0.98)):
    m = plastic(f"{n}Body", col)
    blk(coll, f"{n}_Body", (2.6, 2.4, 2.6), (x, y, 1.3), m, 0.12)
    blk(coll, f"{n}_Drawer", (2.2, 0.1, 0.9), (x, y - 1.22, 1.6), plastic(f"{n}Drawer", (0.93, 0.93, 0.95)), 0.05)
    ball(coll, f"{n}_Knob", 0.13, (x, y - 1.32, 1.6), plastic("Gold", (1.0, 0.8, 0.3)))


def lamp(coll, n, x, y, z, shade_col=(1.0, 0.85, 0.55), dress=None):
    cyl(coll, f"{n}_Base", 0.45, 0.15, (x, y, z + 0.08), plastic(f"{n}Base", (0.95, 0.95, 0.95)))
    cyl(coll, f"{n}_Pole", 0.08, 1.2, (x, y, z + 0.7), plastic(f"{n}Base", (0.95, 0.95, 0.95)))
    sh = new_mat(f"S_{n}Shade", shade_col, 0.7, 0.2)
    _bsdf(sh).inputs["Emission Color"].default_value = (*srgb(shade_col), 1)
    _bsdf(sh).inputs["Emission Strength"].default_value = 0.0
    sh["dress_night"] = (*shade_col, 3.0)
    sh["dress_day"] = (*shade_col, 0.0)
    cyl(coll, f"{n}_Shade", 0.75, 0.9, (x, y, z + 1.6), sh, segs=32, r2=0.45)
    light(coll, f"{n}_Light", 'POINT', (x, y, z + 1.5), color=(1.0, 0.75, 0.45), dress=dress or {"night": 700}, size=0.4)


def shelf(coll, n, x, y, z, axis="Y", length=6.0, seed=1):
    rnd = random.Random(seed)
    m = wood(f"{n}Board", (0.9, 0.68, 0.45), 2.0)
    cols = [(0.9, 0.25, 0.25), (0.25, 0.55, 0.95), (1.0, 0.8, 0.25), (0.35, 0.8, 0.45), (0.75, 0.45, 0.95), (1.0, 0.55, 0.3)]
    for row in range(2):
        zz = z + row * 2.4
        if axis == "Y":
            blk(coll, f"{n}_B{row}", (1.4, length, 0.2), (x, y, zz), m, 0.04)
        else:
            blk(coll, f"{n}_B{row}", (length, 1.4, 0.2), (x, y, zz), m, 0.04)
        t = -length / 2 + 0.4
        k = 0
        while t < length / 2 - 0.6:
            w = rnd.uniform(0.3, 0.5); h = rnd.uniform(1.2, 1.9)
            mat = plastic(f"Book{rnd.randrange(len(cols))}", cols[rnd.randrange(len(cols))], 0.6, 0)
            if axis == "Y":
                blk(coll, f"{n}_Bk{row}_{k}", (1.0, w, h), (x, y + t + w / 2, zz + 0.1 + h / 2), mat, 0.03)
            else:
                blk(coll, f"{n}_Bk{row}_{k}", (w, 1.0, h), (x + t + w / 2, y, zz + 0.1 + h / 2), mat, 0.03)
            t += w + 0.05; k += 1


def rug(coll, n, x, y, r, col, oval=1.0):
    cyl(coll, n, r, 0.12, (x, y, 0.06), fabric(n, col), segs=48).scale = (1, oval, 1)


def plush_duck(coll, n, x, y, z, s=1.0):
    yel = plastic("DuckYellow", (1.0, 0.86, 0.2), 0.6)
    ora = plastic("DuckBeak", (1.0, 0.5, 0.15), 0.5)
    blk_ = plastic("Ink", (0.04, 0.04, 0.05), 0.3)
    ball(coll, f"{n}_Body", 0.9 * s, (x, y, z + 0.8 * s), yel, (1, 1.1, 0.85))
    ball(coll, f"{n}_Head", 0.6 * s, (x, y - 0.35 * s, z + 1.75 * s), yel)
    ball(coll, f"{n}_Beak", 0.3 * s, (x, y - 0.95 * s, z + 1.65 * s), ora, (1.1, 0.8, 0.45))
    for sx in (-1, 1):
        ball(coll, f"{n}_Eye{sx}", 0.09 * s, (x + sx * 0.22 * s, y - 0.88 * s, z + 1.92 * s), blk_)


def poster(coll, n, center, w, h, col, axis="X", accent=(1, 1, 1)):
    x, y, z = center
    if axis == "X":
        blk(coll, n, (w, 0.12, h), center, plastic(n, col, 0.6, 0), 0.03)
        blk(coll, f"{n}_Art", (w * 0.6, 0.14, h * 0.45), (x, y - 0.02, z + h * 0.1), plastic(n + "A", accent, 0.6, 0), 0.08)
    else:
        blk(coll, n, (0.12, w, h), center, plastic(n, col, 0.6, 0), 0.03)
        blk(coll, f"{n}_Art", (0.14, w * 0.6, h * 0.45), (x - 0.02, y, z + h * 0.1), plastic(n + "A", accent, 0.6, 0), 0.08)


def table(coll, n, x, y, w=8.0, d=5.0, h=3.2, col=(0.92, 0.7, 0.45)):
    m = wood(f"{n}Top", col, 1.2)
    blk(coll, f"{n}_Top", (w, d, 0.35), (x, y, h), m, 0.1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            blk(coll, f"{n}_Leg{sx}{sy}", (0.45, 0.45, h - 0.2), (x + sx * (w / 2 - 0.6), y + sy * (d / 2 - 0.6), (h - 0.2) / 2), m, 0.06)


def chair(coll, n, x, y, facing=0, col=(0.98, 0.98, 0.98), h=2.0):
    """facing 0 -> sitter faces -Y (backrest at +Y)."""
    m = plastic(f"{n}Seat", col)
    a = math.radians(facing)
    R = lambda dx, dy: (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
    seat = blk(coll, f"{n}_Seat", (2.4, 2.4, 0.3), (*R(0, 0), h - 0.15), m, 0.1, (0, 0, facing))
    blk(coll, f"{n}_Back", (2.4, 0.3, 2.6), (*R(0, 1.05), h + 1.3), m, 0.1, (0, 0, facing))
    for sx in (-1, 1):
        for sy in (-1, 1):
            blk(coll, f"{n}_Leg{sx}{sy}", (0.25, 0.25, h - 0.3), (*R(sx * 0.95, sy * 0.95), (h - 0.3) / 2), m, 0.04)


def couch(coll, n, x, y, col=(0.98, 0.5, 0.45), w=9.0, facing=0):
    m = fabric(f"{n}", col)
    m2 = fabric(f"{n}Cush", tuple(min(1, c * 1.08) for c in col))
    blk(coll, f"{n}_Base", (w, 3.6, 1.6), (x, y, 1.0), m, 0.3)
    blk(coll, f"{n}_Back", (w, 1.0, 3.2), (x, y + 1.3, 2.2), m, 0.4)
    for s in (-1, 1):
        blk(coll, f"{n}_Arm{s}", (1.0, 3.6, 2.4), (x + s * (w / 2 - 0.5), y, 1.6), m, 0.4)
    for k in (-1, 1):
        blk(coll, f"{n}_Cush{k}", (w / 2 - 1.1, 2.8, 0.7), (x + k * (w / 4 - 0.25), y - 0.3, 2.05), m2, 0.3)


def plant(coll, n, x, y, s=1.0, pot=(0.95, 0.5, 0.3)):
    cyl(coll, f"{n}_Pot", 0.9 * s, 1.6 * s, (x, y, 0.8 * s), plastic(f"{n}Pot", pot), r2=1.1 * s)
    g = plastic("Leaf", (0.3, 0.75, 0.32), 0.6)
    for k in range(5):
        a = 2 * math.pi * k / 5
        ball(coll, f"{n}_Leaf{k}", 0.75 * s, (x + math.cos(a) * 0.6 * s, y + math.sin(a) * 0.6 * s, (2.4 + 0.3 * (k % 2)) * s), g,
             (1, 1, 1.3))
    ball(coll, f"{n}_LeafTop", 0.8 * s, (x, y, 3.1 * s), g)


def tree(coll, n, x, y, s=1.0, seed=0):
    rnd = random.Random(seed)
    cyl(coll, f"{n}_Trunk", 0.7 * s, 6 * s, (x, y, 3 * s), wood("Bark", (0.55, 0.36, 0.2), 0.5, "Y"), segs=12)
    greens = [plastic("TreeA", (0.3, 0.72, 0.28), 0.7), plastic("TreeB", (0.38, 0.8, 0.32), 0.7)]
    for k in range(3):
        ball(coll, f"{n}_Leaves{k}", (3.2 - 0.6 * k) * s,
             (x + rnd.uniform(-1, 1) * s, y + rnd.uniform(-1, 1) * s, (7.5 + 2.2 * k) * s), greens[k % 2], lumpy=0.25, seed=seed * 7 + k)


def bush(coll, n, x, y, s=1.0, seed=0):
    ball(coll, n, 1.4 * s, (x, y, 1.0 * s), plastic("Bush", (0.28, 0.68, 0.3), 0.7), (1.3, 1, 0.85), lumpy=0.3, seed=seed)


def flowers(coll, n, x, y, seed=0, count=6):
    rnd = random.Random(seed)
    cols = [(1.0, 0.4, 0.55), (1.0, 0.85, 0.2), (1.0, 1.0, 1.0), (0.7, 0.45, 1.0)]
    stem = plastic("Stem", (0.3, 0.7, 0.3), 0.6)
    for k in range(count):
        fx, fy = x + rnd.uniform(-1.5, 1.5), y + rnd.uniform(-0.8, 0.8)
        cyl(coll, f"{n}_Stem{k}", 0.06, 1.2, (fx, fy, 0.6), stem, segs=6)
        ball(coll, f"{n}_Bloom{k}", 0.3, (fx, fy, 1.25), plastic(f"Bloom{k % 4}", cols[k % 4], 0.5), (1, 1, 0.6))


def picket_fence(coll, n, x0, x1, y, col=(0.98, 0.98, 0.98), h=2.8):
    m = plastic("Picket", col, 0.5, 0)
    k, x = 0, x0
    while x <= x1:
        blk(coll, f"{n}_P{k}", (0.5, 0.25, h), (x, y, h / 2), m, 0.06)
        x += 1.0; k += 1
    for z in (0.8, h - 0.7):
        blk(coll, f"{n}_Rail{z}", (x1 - x0 + 0.5, 0.2, 0.3), ((x0 + x1) / 2, y + 0.2, z), m, 0.04)


def street_lamp(coll, n, x, y, facing=0, dress=None):
    m = plastic("LampPost", (0.18, 0.2, 0.25), 0.4)
    cyl(coll, f"{n}_Pole", 0.25, 12, (x, y, 6), m, segs=12)
    a = math.radians(facing)
    hx, hy = x - math.sin(a) * 1.4, y - math.cos(a) * 1.4
    blk(coll, f"{n}_Arm", (0.25, 2.8, 0.25), ((x + hx) / 2, (y + hy) / 2, 11.9), m, 0.05, (0, 0, facing))
    bulb = new_mat("S_LampBulb", (1.0, 0.95, 0.8), 0.3, 0.3)
    _bsdf(bulb).inputs["Emission Color"].default_value = (*srgb((1.0, 0.9, 0.65)), 1)
    bulb["dress_sunset"] = (1.0, 0.9, 0.65, 4.0); bulb["dress_day"] = (1.0, 0.95, 0.8, 0.0)
    blk(coll, f"{n}_Head", (1.2, 1.6, 0.5), (hx, hy, 11.6), bulb, 0.15, (0, 0, facing))


def mailbox(coll, n, x, y, col=(0.25, 0.45, 0.95)):
    cyl(coll, f"{n}_Post", 0.18, 3.2, (x, y, 1.6), wood("Post", (0.85, 0.65, 0.45), 1.0, "Y"), segs=8)
    blk(coll, f"{n}_Box", (1.0, 1.8, 1.0), (x, y, 3.6), plastic(f"{n}", col), 0.35)
    blk(coll, f"{n}_Flag", (0.1, 0.25, 0.8), (x + 0.55, y + 0.3, 3.9), plastic("FlagRed", (0.95, 0.2, 0.2)), 0.03)


def car(coll, n, x, y, col=(0.95, 0.25, 0.25), facing=90):
    """Blocky toy car; facing 90 drives along +X."""
    body = plastic(f"Car{n}", col, 0.25)
    _bsdf(body).inputs["Coat Weight"].default_value = 0.6
    tire = plastic("Tire", (0.08, 0.08, 0.09), 0.6, 0)
    rim = plastic("Rim", (0.85, 0.85, 0.88), 0.3, 0)
    gl = glass("CarGlass", (0.25, 0.4, 0.6), interior=False)
    grp = bpy.data.objects.new(f"{n}", None); coll.objects.link(grp)
    grp.location = (x, y, 0); grp.rotation_euler = (0, 0, math.radians(facing - 90))
    parts = [
        blk(coll, f"{n}_Body", (9.0, 4.2, 1.8), (0, 0, 1.9), body, 0.45),
        blk(coll, f"{n}_Cabin", (5.0, 3.8, 1.8), (-0.6, 0, 3.5), body, 0.45),
        blk(coll, f"{n}_GlassF", (0.2, 3.4, 1.3), (1.95, 0, 3.5), gl, 0.05, (0, -20, 0)),
        blk(coll, f"{n}_GlassS", (4.2, 3.9, 1.2), (-0.6, 0, 3.55), gl, 0.05),
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cyl(coll, f"{n}_Tire{sx}{sy}", 0.95, 0.8, (sx * 2.9, sy * 2.0, 0.95), tire, (90, 0, 0), 24))
            parts.append(cyl(coll, f"{n}_Rim{sx}{sy}", 0.5, 0.85, (sx * 2.9, sy * 2.0, 0.95), rim, (90, 0, 0), 16))
        parts.append(blk(coll, f"{n}_Light{sx}", (0.15, 0.8, 0.5), (4.5, sx * 1.4, 2.1), plastic("Headlight", (1, 0.95, 0.7), 0.2, 0), 0.05))
    for p in parts:
        p.parent = grp


def house(coll, n, x, y_front, w=18, d=14, h=11, wall=(1.0, 0.62, 0.32), roof="flat", roof_col=(0.95, 0.95, 0.95),
          door_col=(0.95, 0.95, 0.95), trim=(1, 1, 1), brick_wall=False, facing=0, seed=0):
    """Suburban house. facing 0: front faces -Y (toward the street at lower y)."""
    rnd = random.Random(seed)
    grp = bpy.data.objects.new(n, None); coll.objects.link(grp)
    grp.location = (x, y_front, 0); grp.rotation_euler = (0, 0, math.radians(facing))
    wm = brick(f"{n}Wall", wall) if brick_wall else matte(f"{n}Wall", wall)
    tm = plastic(f"{n}Trim", trim, 0.5)
    gl = glass("HouseGlass", (0.45, 0.72, 0.95), interior=False)
    _bsdf(gl).inputs["Roughness"].default_value = 0.05
    parts = [blk(coll, f"{n}_Walls", (w, d, h), (0, d / 2, h / 2), wm, 0.1)]
    parts.append(blk(coll, f"{n}_Base", (w + 0.4, d + 0.4, 0.8), (0, d / 2, 0.4), plastic(f"{n}Base", (0.8, 0.8, 0.82), 0.7), 0.05))
    if roof == "flat":
        parts.append(blk(coll, f"{n}_Roof", (w + 1.2, d + 1.2, 1.0), (0, d / 2, h + 0.5), tm, 0.15))
    else:
        rm = plastic(f"{n}Roof", roof_col, 0.6)
        me = bpy.data.meshes.new(f"{n}_Roof")
        bm = bmesh.new()
        rh = 5.0
        pts = [(-w / 2 - 1, -1, h), (w / 2 + 1, -1, h), (w / 2 + 1, d + 1, h), (-w / 2 - 1, d + 1, h),
               (-w / 2 - 1, d / 2, h + rh), (w / 2 + 1, d / 2, h + rh)]
        vs = [bm.verts.new(p) for p in pts]
        for f in ((0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)):
            bm.faces.new([vs[i] for i in f])
        bm.to_mesh(me); bm.free()
        ro = bpy.data.objects.new(f"{n}_Roof", me); coll.objects.link(ro); me.materials.append(rm)
        so = ro.modifiers.new("Solid", "SOLIDIFY"); so.thickness = 0.4
        parts.append(ro)
        # gable infill (wall colour) front/back
        for yy in (0.0, d):
            me2 = bpy.data.meshes.new(f"{n}_Gable{yy}")
            bm = bmesh.new()
            vs = [bm.verts.new(p) for p in ((-w / 2, yy, h), (w / 2, yy, h), (0, yy, h + rh - 0.6))]
            bm.faces.new(vs); bm.to_mesh(me2); bm.free()
            go = bpy.data.objects.new(f"{n}_Gable{yy}", me2); coll.objects.link(go); me2.materials.append(wm)
            parts.append(go)
    # front: door + porch + windows
    dm = plastic(f"{n}Door", door_col, 0.4)
    door(coll, f"{n}_Door", (-w * 0.18, -0.18, 0.8), dm, plastic("Gold", (1.0, 0.8, 0.3)), "X")
    parts += [o for o in coll.objects if o.name.startswith(f"{n}_Door")]
    parts.append(blk(coll, f"{n}_Step", (5.0, 2.0, 0.8), (-w * 0.18, -1.0, 0.4), plastic(f"{n}Base", (0.8, 0.8, 0.82), 0.7), 0.05))
    before = set(coll.objects)
    for k, wx in enumerate((w * 0.22, w * 0.38) if w > 16 else (w * 0.26,)):
        window(coll, f"{n}_WinF{k}", (wx - (w * 0.08 if w > 16 else 0), -0.12, h * 0.42), 3.2, 3.6, tm, gl, "X", sill=True)
    if roof == "flat" or h > 9:
        window(coll, f"{n}_WinU", (-w * 0.18, -0.12, h * 0.78), 3.0, 2.2, tm, gl, "X", sill=False)
    parts += [o for o in coll.objects if o not in before]
    for p in parts:
        if p.parent is None and p is not grp:
            p.parent = grp
    return grp


# ---------------------------------------------------------------- room shell
def room(coll, n, W, D, H, wall_mat, floor_mat, ceil_col=(0.98, 0.98, 0.98), base_col=(1, 1, 1)):
    """Closed box room: x in [-W/2, W/2], y in [-D/2, D/2], floor at z=0."""
    t = 0.6
    blk(coll, f"{n}_Floor", (W + 2 * t, D + 2 * t, 0.4), (0, 0, -0.2), floor_mat, 0.02)
    blk(coll, f"{n}_Ceiling", (W + 2 * t, D + 2 * t, 0.4), (0, 0, H + 0.2), matte(f"{n}Ceil", ceil_col), 0.02)
    walls = {
        "back": blk(coll, f"{n}_WallBack", (W, t, H), (0, D / 2 + t / 2, H / 2), wall_mat, 0.0),
        "front": blk(coll, f"{n}_WallFront", (W, t, H), (0, -D / 2 - t / 2, H / 2), wall_mat, 0.0),
        "left": blk(coll, f"{n}_WallLeft", (t, D + 2 * t, H), (-W / 2 - t / 2, 0, H / 2), wall_mat, 0.0),
        "right": blk(coll, f"{n}_WallRight", (t, D + 2 * t, H), (W / 2 + t / 2, 0, H / 2), wall_mat, 0.0),
    }
    walls["front"]["camera_wall"] = True
    bm = plastic(f"{n}Baseboard", base_col, 0.5, 0)
    blk(coll, f"{n}_BaseB", (W, 0.3, 0.7), (0, D / 2 - 0.15, 0.35), bm, 0.04)
    blk(coll, f"{n}_BaseF", (W, 0.3, 0.7), (0, -D / 2 + 0.15, 0.35), bm, 0.04)
    blk(coll, f"{n}_BaseL", (0.3, D, 0.7), (-W / 2 + 0.15, 0, 0.35), bm, 0.04)
    blk(coll, f"{n}_BaseR", (0.3, D, 0.7), (W / 2 - 0.15, 0, 0.35), bm, 0.04)
    return walls


# ---------------------------------------------------------------- sets
def build_bedroom(coll):
    S = "bedroom"
    W, D, H = 28, 22, 14
    room(coll, "Bed", W, D, H, matte("BedroomWall", (0.62, 0.8, 1.0)), wood("BedroomFloor", (0.9, 0.62, 0.38), 1.6))
    gl = glass("BedroomGlass")
    white = plastic("WhiteTrim", (1, 1, 1), 0.45, 0)
    # back wall: bed (left), nightstand + lamp + alarm, window (right), clock above bed
    bed(coll, "Bed", -7.0, D / 2 - 4.6)
    nightstand(coll, "Night", -1.9, D / 2 - 1.7)
    alarm_clock(coll, "Alarm", (-2.4, D / 2 - 2.0, 2.6))
    lamp(coll, "Lamp", -1.2, D / 2 - 1.3, 2.6)
    window(coll, "BedWin", (6.5, D / 2 - 0.05, 7.2), 6.0, 5.0, white, gl, "X", curtains=fabric("Curtain", (1.0, 0.62, 0.7)))
    wall_clock(coll, "WallClock", (-7.0, D / 2 - 0.15, 10.6), 1.4, "X", hour=7)
    # right wall: shelf + desk with a monitor
    shelf(coll, "Shelf", W / 2 - 0.9, 2.0, 7.0, "Y", 7.0, seed=3)
    table(coll, "Desk", W / 2 - 2.6, -4.5, 4.0, 7.0, 3.3, (1, 1, 1))
    chair(coll, "DeskChair", W / 2 - 5.5, -4.5, facing=-90, col=(0.3, 0.55, 0.95))
    blk(coll, "Monitor", (0.4, 3.6, 2.2), (W / 2 - 1.6, -4.5, 5.0), plastic("Monitor", (0.1, 0.1, 0.12), 0.3), 0.08)
    blk(coll, "Screen", (0.1, 3.2, 1.8), (W / 2 - 1.85, -4.5, 5.0), glass("Screen", (0.35, 0.6, 1.0), (0.35, 0.6, 1.0), 1.2, 1.2), 0.0)
    # left wall: posters, plush toy on the bed
    poster(coll, "PosterA", (-W / 2 + 0.1, 0.5, 7.5), 3.4, 4.4, (1.0, 0.85, 0.3), "Y", (0.95, 0.35, 0.35))
    poster(coll, "PosterB", (-W / 2 + 0.1, -4.5, 8.0), 3.0, 3.0, (0.45, 0.85, 0.6), "Y", (1, 1, 1))
    plush_duck(coll, "Duck", -9.2, D / 2 - 2.6, 3.0, 0.8)
    rug(coll, "Rug", 1.5, -1.5, 5.0, (1.0, 0.7, 0.8), 0.7)
    door(coll, "BedDoor", (-W / 2 + 0.05, -6.5, 0), plastic("DoorWhite", (0.98, 0.98, 0.98), 0.4), plastic("Gold", (1.0, 0.8, 0.3)), "Y", sign=1)
    # light
    sun(coll, S, {"day": (4.0, 40, 200, (1.0, 0.95, 0.85)), "night": (0.35, 35, 200, (0.55, 0.65, 1.0))})
    light(coll, "BedFill", 'AREA', (0, -4, H - 1.0), (0, 0, 0), (1.0, 0.97, 0.92), {"day": 3500, "night": 700}, size=14)
    light(coll, "BedWinLight", 'AREA', (6.5, D / 2 - 1.0, 7.2), (-90, 0, 0), (0.85, 0.92, 1.0), {"day": 900, "night": 60}, size=6)
    # marks
    mark(coll, S, "bed", (-7.0, D / 2 - 8.0, 3.0), 0)          # lie: use pose "lie" (head goes to +Y = pillow)
    mark(coll, S, "bed_sit", (-4.6, D / 2 - 6.0, 0.0), -90)
    mark(coll, S, "bedside", (-3.0, D / 2 - 8.0, 0.0), 0)
    mark(coll, S, "center", (1.0, -1.5, 0.0), 0)
    mark(coll, S, "window", (6.5, D / 2 - 3.5, 0.0), 180)
    mark(coll, S, "desk", (W / 2 - 5.5, -4.5, 0.0), -90)
    mark(coll, S, "door", (-W / 2 + 3.0, -6.5, 0.0), -90)
    mark(coll, S, "cam_default", (0, -D / 2 + 1.0, 4.5), 0)


def build_kitchen(coll):
    S = "kitchen"
    W, D, H = 36, 24, 14
    room(coll, "Kit", W, D, H, matte("KitchenWall", (1.0, 0.86, 0.7)), wood("KitchenFloor", (0.88, 0.62, 0.4), 1.8))
    blk(coll, "KitTiles", (14, 10, 0.06), (-10, 6, 0.03), checker("KitTile", (0.98, 0.98, 0.98), (0.5, 0.75, 0.95), 1.5), 0.0)
    gl = glass("KitchenGlass")
    white = plastic("WhiteTrim", (1, 1, 1), 0.45, 0)
    cab = plastic("Cabinet", (0.55, 0.85, 0.75), 0.4)
    top = plastic("Counter", (0.97, 0.97, 0.97), 0.25)
    # back wall kitchen run (left half)
    for k, x in enumerate((-16, -12, -8, -4)):
        blk(coll, f"Cab{k}", (3.9, 3.0, 3.4), (x, D / 2 - 1.6, 1.7), cab, 0.08)
        blk(coll, f"CabH{k}", (1.2, 0.15, 0.2), (x, D / 2 - 3.15, 2.9), plastic("Gold", (1.0, 0.8, 0.3)), 0.05)
        blk(coll, f"Upper{k}", (3.9, 2.0, 3.0), (x, D / 2 - 1.0, 10.0), cab, 0.08)
    blk(coll, "Countertop", (16.4, 3.4, 0.35), (-10, D / 2 - 1.7, 3.55), top, 0.06)
    blk(coll, "Stove", (3.6, 0.2, 0.5), (-12, D / 2 - 3.2, 3.0), plastic("StoveDark", (0.12, 0.12, 0.14)), 0.03)
    for k, (dx, dy) in enumerate(((-0.8, -0.6), (0.8, -0.6), (-0.8, 0.6), (0.8, 0.6))):
        cyl(coll, f"Burner{k}", 0.6, 0.05, (-12 + dx, D / 2 - 1.7 + dy, 3.75), plastic("StoveDark", (0.12, 0.12, 0.14)))
    pan = plastic("Pan", (0.15, 0.15, 0.17), 0.3)
    cyl(coll, "Pan", 0.9, 0.3, (-12.8, D / 2 - 2.3, 3.95), pan)
    blk(coll, "PanHandle", (1.6, 0.25, 0.15), (-14.3, D / 2 - 2.3, 4.0), pan, 0.05)
    # fridge
    fr = plastic("Fridge", (0.95, 0.95, 0.97), 0.25)
    blk(coll, "Fridge", (4.4, 3.6, 10.0), (-W / 2 + 2.6, D / 2 - 6.0, 5.0), fr, 0.3)
    blk(coll, "FridgeLine", (0.1, 3.4, 0.1), (-W / 2 + 4.85, D / 2 - 6.0, 7.0), plastic("Gray", (0.7, 0.7, 0.72)), 0.0)
    for z in (5.0, 8.5):
        blk(coll, f"FridgeH{z}", (0.25, 0.25, 1.6), (-W / 2 + 4.95, D / 2 - 7.4, z), plastic("Gray", (0.7, 0.7, 0.72)), 0.06)
    window(coll, "KitWin", (-8.0, D / 2 - 0.05, 7.6), 5.0, 3.4, white, gl, "X")
    wall_clock(coll, "KitClock", (2.0, D / 2 - 0.15, 9.5), 1.3, "X", rim=(0.3, 0.55, 0.95), hour=8)
    # dining table + chairs + pancakes
    table(coll, "Dining", -4.0, -1.0, 9.0, 5.5, 3.3, (0.95, 0.75, 0.5))
    for k, (cx, cy, f) in enumerate(((-6.5, 2.6, 0), (-1.5, 2.6, 0), (-6.5, -4.6, 180), (-1.5, -4.6, 180))):
        chair(coll, f"DChair{k}", cx, cy, facing=f, col=(1.0, 0.62, 0.4))
    plate = plastic("Plate", (1, 1, 1), 0.2, 0)
    pc = plastic("Pancake", (0.92, 0.66, 0.35), 0.55)
    for k, px in enumerate((-6.5, -1.5)):
        cyl(coll, f"Plate{k}", 1.0, 0.1, (px, -1.0 + (0.9 if k == 0 else 0.9), 3.55), plate, segs=32)
    for j in range(6):
        cyl(coll, f"Pancake{j}", 0.75, 0.16, (-6.5, -0.1, 3.7 + 0.17 * j), pc, segs=32)
    cyl(coll, "Butter", 0.25, 0.2, (-6.5, -0.1, 4.8), plastic("Butter", (1.0, 0.92, 0.5)), segs=4)
    cyl(coll, "Syrup", 0.72, 0.05, (-6.5, -0.1, 4.73), plastic("Syrup", (0.65, 0.33, 0.1), 0.15), segs=32)
    cyl(coll, "Juice", 0.35, 1.0, (-2.6, -0.5, 4.0), glass("Juice", (1.0, 0.65, 0.15), interior=False), segs=24)
    # living area (right half): couch facing a TV on the right wall
    couch(coll, "Couch", 10.0, -6.0, (0.98, 0.5, 0.45), 9.0)
    rug(coll, "LivingRug", 10.0, -0.5, 6.0, (0.6, 0.8, 1.0), 0.6)
    blk(coll, "TVStand", (8.0, 2.2, 2.2), (10.0, D / 2 - 1.3, 1.1), plastic("TVStand", (0.98, 0.98, 0.98), 0.4), 0.1)
    blk(coll, "TV", (8.0, 0.5, 4.6), (10.0, D / 2 - 0.9, 5.4), plastic("TVBlack", (0.06, 0.06, 0.07), 0.25), 0.1)
    blk(coll, "TVScreen", (7.5, 0.1, 4.1), (10.0, D / 2 - 1.18, 5.4), glass("TVScreen", (0.4, 0.7, 1.0), (0.4, 0.7, 1.0), 0.9, 0.9), 0.0)
    plant(coll, "PlantA", W / 2 - 2.0, D / 2 - 2.0, 1.2)
    poster(coll, "KitPoster", (W / 2 - 0.1, 2.0, 7.5), 4.0, 3.0, (0.95, 0.95, 0.95), "Y", (1.0, 0.6, 0.3))
    door(coll, "KitDoor", (W / 2 - 0.05, -7.0, 0), plastic("DoorWood", (0.85, 0.55, 0.32), 0.45), plastic("Gold", (1.0, 0.8, 0.3)), "Y", sign=-1)
    sun(coll, S, {"day": (4.0, 45, 200, (1.0, 0.95, 0.85))})
    light(coll, "KitFill", 'AREA', (0, -2, H - 1.0), (0, 0, 0), (1.0, 0.97, 0.92), {"day": 4600}, size=18)
    light(coll, "KitWinLight", 'AREA', (-8.0, D / 2 - 1.0, 7.6), (-90, 0, 0), (0.85, 0.92, 1.0), {"day": 600}, size=5)
    mark(coll, S, "table_a", (-6.5, 2.6, 0.0), 0)       # seat behind the table, facing camera
    mark(coll, S, "table_b", (-1.5, 2.6, 0.0), 0)
    mark(coll, S, "table_front", (-4.0, -4.6, 0.0), 180)
    mark(coll, S, "stove", (-12.0, D / 2 - 5.0, 0.0), 180)
    mark(coll, S, "fridge", (-W / 2 + 7.0, D / 2 - 6.0, 0.0), 90)
    mark(coll, S, "couch", (10.0, -6.3, 0.0), 180)      # sitting, facing the TV
    mark(coll, S, "center", (4.0, -1.0, 0.0), 0)
    mark(coll, S, "door", (W / 2 - 3.0, -7.0, 0.0), 90)
    mark(coll, S, "cam_default", (0, -D / 2 + 1.0, 4.5), 0)


def build_classroom(coll):
    S = "classroom"
    W, D, H = 40, 30, 15
    room(coll, "Class", W, D, H, matte("ClassWall", (1.0, 0.93, 0.62)), wood("ClassFloor", (0.85, 0.62, 0.42), 2.0))
    gl = glass("ClassGlass")
    white = plastic("WhiteTrim", (1, 1, 1), 0.45, 0)
    # chalkboard (back wall)
    blk(coll, "BoardFrame", (18.4, 0.3, 7.4), (0, D / 2 - 0.2, 7.5), wood("BoardWood", (0.8, 0.55, 0.32), 1.0), 0.1)
    blk(coll, "Board", (17.6, 0.2, 6.6), (0, D / 2 - 0.3, 7.5), matte("Chalkboard", (0.16, 0.42, 0.3), 0.9), 0.02)
    blk(coll, "Chalk", (16.0, 0.6, 0.2), (0, D / 2 - 0.6, 4.1), wood("BoardWood", (0.8, 0.55, 0.32), 1.0), 0.05)
    chalk = matte("ChalkWhite", (0.95, 0.95, 0.95))
    for k, (x0, x1, z) in enumerate(((-7, -1, 9.5), (-7, 3, 8.2), (-7, 0, 6.9), (2, 6.5, 6.9))):
        blk(coll, f"Scribble{k}", (x1 - x0, 0.05, 0.22), ((x0 + x1) / 2, D / 2 - 0.42, z), chalk, 0.0)
    blk(coll, "Formula", (2.2, 0.05, 2.2), (5.5, D / 2 - 0.42, 9.0), chalk, 0.0)
    wall_clock(coll, "ClassClock", (12.5, D / 2 - 0.15, 11.5), 1.4, "X", rim=(0.2, 0.2, 0.25), hour=9)
    # teacher desk
    blk(coll, "TeacherDesk", (8.0, 3.6, 3.4), (-8.0, D / 2 - 6.0, 1.7), wood("TeacherDesk", (0.75, 0.5, 0.3), 1.2), 0.12)
    ball(coll, "Apple", 0.45, (-6.0, D / 2 - 6.0, 3.85), plastic("Apple", (0.95, 0.15, 0.15), 0.3))
    blk(coll, "Books", (1.6, 1.2, 0.8), (-10.0, D / 2 - 6.0, 3.8), plastic("BookBlue", (0.25, 0.55, 0.95), 0.6, 0), 0.05)
    # student desks: 3 columns x 3 rows, facing the board (+Y) -> students face away from camera
    dk = plastic("StudentDesk", (0.98, 0.98, 0.98), 0.4)
    top_m = wood("DeskTop", (0.95, 0.75, 0.5), 1.0)
    k = 0
    for row, y in enumerate((2.0, -4.5, -11.0)):
        for col, x in enumerate((-10.0, 0.0, 10.0)):
            blk(coll, f"SDeskTop{k}", (5.0, 3.0, 0.3), (x, y, 3.2), top_m, 0.08)
            blk(coll, f"SDeskBox{k}", (4.6, 2.6, 1.0), (x, y, 2.5), dk, 0.06)
            for sx in (-1, 1):
                blk(coll, f"SDeskLeg{k}{sx}", (0.3, 0.3, 2.0), (x + sx * 2.1, y, 1.0), dk, 0.04)
            chair(coll, f"SChair{k}", x, y - 2.8, facing=180, col=[(0.3, 0.55, 0.95), (1.0, 0.6, 0.3), (0.45, 0.8, 0.5)][(row + col) % 3])
            mark(coll, S, f"desk_{k + 1}", (x, y - 2.8, 0.0), 180)
            k += 1
    # left wall windows, right wall door + posters
    for k, y in enumerate((8.0, -1.0, -10.0)):
        window(coll, f"ClassWin{k}", (-W / 2 + 0.05, y, 8.0), 6.0, 5.4, white, gl, "Y")
    door(coll, "ClassDoor", (W / 2 - 0.05, -9.0, 0), plastic("DoorWood", (0.85, 0.55, 0.32), 0.45), plastic("Gold", (1.0, 0.8, 0.3)), "Y", sign=-1)
    poster(coll, "ClassPosterA", (W / 2 - 0.1, 2.0, 8.0), 4.0, 5.0, (0.45, 0.75, 1.0), "Y", (1.0, 0.85, 0.3))
    poster(coll, "ClassPosterB", (W / 2 - 0.1, 9.0, 8.0), 4.0, 5.0, (1.0, 0.6, 0.65), "Y", (1, 1, 1))
    plant(coll, "ClassPlant", -W / 2 + 2.0, D / 2 - 2.0, 1.1)
    sun(coll, S, {"day": (4.5, 40, 120, (1.0, 0.95, 0.85))})
    light(coll, "ClassFill", 'AREA', (0, -3, H - 1.0), (0, 0, 0), (1.0, 0.98, 0.94), {"day": 6500}, size=22)
    for k, y in enumerate((8.0, -1.0, -10.0)):
        light(coll, f"ClassWinLight{k}", 'AREA', (-W / 2 + 1.0, y, 8.0), (0, -90, 0), (0.85, 0.92, 1.0), {"day": 500}, size=5)
    mark(coll, S, "teacher", (-4.0, D / 2 - 3.5, 0.0), 0)
    mark(coll, S, "board", (2.0, D / 2 - 2.5, 0.0), 0)
    mark(coll, S, "door", (W / 2 - 3.0, -9.0, 0.0), 90)
    mark(coll, S, "center", (0.0, 7.5, 0.0), 0)
    mark(coll, S, "cam_default", (4.0, -D / 2 + 1.0, 7.5), 0)     # in the aisle, over the desks


def build_street(coll):
    S = "street"
    L = 170
    grass = grass_mat()
    blk(coll, "Ground", (L + 120, 220, 0.4), (0, 0, -0.25), grass, 0.0)
    # road along X between y=-14 and y=-2, sidewalks either side
    blk(coll, "Road", (L + 120, 12, 0.3), (0, -8, -0.1), asphalt_mat(), 0.0)
    lm = plastic("RoadYellow", (1.0, 0.85, 0.2), 0.5, 0)
    x = -L / 2 - 50
    k = 0
    while x < L / 2 + 50:
        blk(coll, f"Lane{k}", (4.0, 0.35, 0.05), (x, -8, 0.06), lm, 0.0)
        x += 8; k += 1
    side = plastic("Sidewalk", (0.86, 0.86, 0.88), 0.8, 0.05)
    for y in (2.0, -18.0):
        blk(coll, f"Walk{y}", (L + 120, 8, 0.5), (0, y + (0 if y > 0 else 0), 0.05), side, 0.05)
        x = -L / 2 - 50; j = 0
        while x < L / 2 + 50:
            blk(coll, f"Joint{y}_{j}", (0.12, 8, 0.05), (x, y, 0.32), plastic("Joint", (0.7, 0.7, 0.73), 0.8, 0), 0.0)
            x += 4; j += 1
    # houses on the far side (front at y=16) and the near side (front at y=-32, facing +Y)
    palette = [((1.0, 0.62, 0.32), "flat", (1, 1, 1)), ((0.45, 0.72, 1.0), "gable", (0.95, 0.3, 0.3)),
               ((1.0, 0.65, 0.78), "flat", (1, 1, 1)), ((1.0, 0.86, 0.38), "gable", (0.35, 0.45, 0.6)),
               ((0.55, 0.9, 0.72), "flat", (1, 1, 1)), ((0.98, 0.98, 0.98), "gable", (0.9, 0.35, 0.3))]
    doors = [(0.3, 0.55, 0.95), (0.98, 0.98, 0.98), (0.95, 0.3, 0.35), (0.35, 0.75, 0.5), (1.0, 0.6, 0.2), (0.45, 0.35, 0.8)]
    xs = [-75, -45, -15, 15, 45, 75]
    for i, hx in enumerate(xs):
        wall, roof, rc = palette[i % len(palette)]
        house(coll, f"HouseN{i}", hx, 16, 20, 15, 11 if roof == "flat" else 10, wall, roof, rc, doors[i], seed=i)
        picket_fence(coll, f"FenceN{i}", hx - 12, hx - 4, 7.0)
        picket_fence(coll, f"FenceN{i}b", hx + 4, hx + 12, 7.0)
        mailbox(coll, f"MailN{i}", hx + 3, 6.0, doors[i])
        tree(coll, f"TreeN{i}", hx + 13.5, 11, 0.9, seed=i)
        bush(coll, f"BushN{i}", hx - 8, 14.0, 1.0, seed=i)
        flowers(coll, f"FlowersN{i}", hx + 6, 14.5, seed=i)
        wall2, roof2, rc2 = palette[(i + 3) % len(palette)]
        house(coll, f"HouseS{i}", hx, -32, 20, 15, 11 if roof2 == "flat" else 10, wall2, roof2, rc2, doors[(i + 2) % 6],
              facing=180, seed=i + 10)
        tree(coll, f"TreeS{i}", hx - 13.5, -27, 0.9, seed=i + 20)
        bush(coll, f"BushS{i}", hx + 8, -29.0, 1.0, seed=i + 5)
    for i, lx in enumerate(range(-80, 90, 32)):
        street_lamp(coll, f"LampN{i}", lx, 3.5, facing=0)
        street_lamp(coll, f"LampS{i}", lx + 16, -19.5, facing=180)
    car(coll, "CarA", 22, -11.0, (0.95, 0.25, 0.25), 90)
    car(coll, "CarB", -38, -5.0, (0.3, 0.55, 0.95), 270)
    # distant hills ring for wide shots
    for k in range(10):
        a = 2 * math.pi * k / 10
        ball(coll, f"Hill{k}", 40, (math.cos(a) * 150, math.sin(a) * 120 + 20, -12), plastic("Hill", (0.4, 0.75, 0.38), 0.9),
             (1.6, 1.0, 0.6), lumpy=0.15, seed=k)
    sun(coll, S, {"day": (4.5, 50, 210, (1.0, 0.96, 0.88)), "sunset": (3.0, 12, 250, (1.0, 0.65, 0.4))})
    mark(coll, S, "sidewalk_a", (-6.0, 2.0, 0.25), 0)
    mark(coll, S, "sidewalk_b", (0.0, 2.0, 0.25), 0)
    mark(coll, S, "sidewalk_c", (6.0, 2.0, 0.25), 0)
    mark(coll, S, "house_door", (-15 - 3.6, 13.5, 0.4), 0)
    mark(coll, S, "lawn", (-15 + 5, 10.5, 0.0), 0)
    mark(coll, S, "road", (0.0, -8.0, 0.0), 0)
    mark(coll, S, "far_walk", (0.0, -18.0, 0.25), 180)
    mark(coll, S, "cam_default", (0, -16.0, 5.0), 0)
    mark(coll, S, "cam_aerial", (0, -70.0, 55.0), 0)


BUILDERS = {"bedroom": build_bedroom, "street": build_street, "kitchen": build_kitchen, "classroom": build_classroom}


# ---------------------------------------------------------------- public API
def _world(dressing):
    sky, lightc, strength = WORLDS[dressing]
    w = bpy.data.worlds.get(f"World_{dressing}") or bpy.data.worlds.new(f"World_{dressing}")
    w.use_nodes = True
    N, L = w.node_tree.nodes, w.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_WORLD':
            N.remove(n)
    out = next(n for n in N if n.type == 'OUTPUT_WORLD')
    lp = N.new("ShaderNodeLightPath")
    cam_bg = N.new("ShaderNodeBackground"); cam_bg.inputs[0].default_value = (*srgb(sky), 1); cam_bg.inputs[1].default_value = 1.0
    light_bg = N.new("ShaderNodeBackground"); light_bg.inputs[0].default_value = (*srgb(lightc), 1); light_bg.inputs[1].default_value = strength
    mix = N.new("ShaderNodeMixShader")
    L.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    L.new(light_bg.outputs[0], mix.inputs[1]); L.new(cam_bg.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return w


def build_set(name, scene=None):
    scene = scene or bpy.context.scene
    cname = f"Set_{name}"
    old = bpy.data.collections.get(cname)
    if old:
        for o in list(old.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    coll = bpy.data.collections.new(cname)
    scene.collection.children.link(coll)
    coll["set_name"] = name
    coll["dressings"] = ",".join(DRESSINGS[name])
    BUILDERS[name](coll)
    for o in coll.objects:
        if o.type == 'EMPTY' and o.name.startswith("mark_"):
            o.hide_render = True
    apply_dressing(name, DRESSINGS[name][0], scene)
    return coll


def apply_dressing(set_name, dressing, scene=None):
    scene = scene or bpy.context.scene
    coll = bpy.data.collections[f"Set_{set_name}"]
    objs = [o for o in coll.all_objects if o is not None]
    for o in objs:
        if o.type == 'LIGHT':
            e = o.get(f"dress_{dressing}", 0.0)
            o.data.energy = e
            o.hide_render = o.hide_viewport = (e == 0)
            r = o.get(f"dress_rot_{dressing}")
            if r is not None:
                o.rotation_euler = [math.radians(a) for a in r]
            c = o.get(f"dress_col_{dressing}")
            if c is not None:
                o.data.color = tuple(c)
        only = o.get("only_dressing")
        if only is not None:
            o.hide_render = o.hide_viewport = (only != dressing)
    seen = set()
    for o in objs:
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if not m or m.name in seen or f"dress_{dressing}" not in m:
                continue
            seen.add(m.name)
            r, g, bl, em = m[f"dress_{dressing}"]
            b = _bsdf(m)
            if m.get("interior", True):
                b.inputs["Base Color"].default_value = (*srgb((r, g, bl)), 1)
            b.inputs["Emission Color"].default_value = (*srgb((r, g, bl)), 1)
            b.inputs["Emission Strength"].default_value = em
    scene.world = _world(dressing)
    scene["dressing"] = dressing
    return scene.world


def get_marks(set_name):
    coll = bpy.data.collections[f"Set_{set_name}"]
    return {o["mark"]: o for o in coll.objects if o is not None and o.get("mark")}


def place_at_mark(rig, set_name, mark_name, facing_deg=None):
    bpy.context.view_layer.update()          # fresh marks have a stale matrix_world until an update
    m = get_marks(set_name)[mark_name]
    rig.location = m.matrix_world.translation
    rig.rotation_euler = (0, 0, m.rotation_euler.z if facing_deg is None else math.radians(facing_deg))


def set_offset(set_name, offset):
    """Move a whole set (all sets live in one file side by side)."""
    coll = bpy.data.collections[f"Set_{set_name}"]
    for o in coll.objects:
        if o.parent is None:
            o.location = Vector(o.location) + Vector(offset)
