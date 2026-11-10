"""
Reusable Roblox Procedural Asset Library Registry & Geometry-Driven Metadata Builder.

Categories:
  - architecture (9 assets)
  - environment  (13 assets)
  - interiors    (8 assets)
  - fantasy      (5 assets)

Total: 35 modular procedural Roblox assets.
"""
import math
from pathlib import Path
import sys

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import architecture as ARCH  # noqa: E402
import environment as ENV    # noqa: E402
import interiors as INT      # noqa: E402
import fantasy as FAN        # noqa: E402


ASSET_DEFINITIONS = {
    # ---------------- ARCHITECTURE (9) ----------------
    "arch_house_suburban": {
        "category": "architecture",
        "subcategory": "houses",
        "tags": ["house", "suburban", "residential", "building", "home"],
        "allowed_surfaces": ["ground", "grass", "terrain"],
        "scale_constraints": {"min": 0.7, "max": 1.6, "default": 1.0},
        "walkable": False,
        "attachment_points": {"front_door": [0.0, -7.2, 0.4]},
        "builder": ARCH.build_arch_house_suburban,
    },
    "arch_apartment_block": {
        "category": "architecture",
        "subcategory": "apartments",
        "tags": ["apartment", "city", "residential", "building", "multistory"],
        "allowed_surfaces": ["ground", "pavement"],
        "scale_constraints": {"min": 0.75, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {"entry": [0.0, -7.2, 0.0]},
        "builder": ARCH.build_arch_apartment_block,
    },
    "arch_shop_bakery": {
        "category": "architecture",
        "subcategory": "shops",
        "tags": ["shop", "bakery", "storefront", "commercial", "town"],
        "allowed_surfaces": ["ground", "pavement"],
        "scale_constraints": {"min": 0.75, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {"shop_door": [-4.2, -6.2, 0.0], "window_display": [2.4, -6.2, 1.5]},
        "builder": ARCH.build_arch_shop_bakery,
    },
    "arch_school_facade": {
        "category": "architecture",
        "subcategory": "schools",
        "tags": ["school", "education", "civic", "brick", "building"],
        "allowed_surfaces": ["ground", "pavement"],
        "scale_constraints": {"min": 0.7, "max": 1.4, "default": 1.0},
        "walkable": False,
        "attachment_points": {"main_entrance": [0.0, -8.0, 0.0]},
        "builder": ARCH.build_arch_school_facade,
    },
    "arch_clock_tower": {
        "category": "architecture",
        "subcategory": "towers",
        "tags": ["tower", "clock", "landmark", "civic", "town_square"],
        "allowed_surfaces": ["ground", "pavement", "plaza"],
        "scale_constraints": {"min": 0.7, "max": 1.6, "default": 1.0},
        "walkable": False,
        "attachment_points": {"base_front": [0.0, -4.0, 0.0], "spire_top": [0.0, 0.0, 32.0]},
        "builder": ARCH.build_arch_clock_tower,
    },
    "arch_castle_keep": {
        "category": "architecture",
        "subcategory": "castles",
        "tags": ["castle", "keep", "fortress", "medieval", "royal"],
        "allowed_surfaces": ["ground", "terrain", "hill"],
        "scale_constraints": {"min": 0.7, "max": 1.8, "default": 1.0},
        "walkable": False,
        "attachment_points": {"gate": [0.0, -7.2, 0.0]},
        "builder": ARCH.build_arch_castle_keep,
    },
    "arch_stone_wall": {
        "category": "architecture",
        "subcategory": "walls",
        "tags": ["wall", "stone", "boundary", "perimeter", "barrier"],
        "allowed_surfaces": ["ground", "grass", "pavement", "terrain"],
        "scale_constraints": {"min": 0.6, "max": 2.0, "default": 1.0},
        "walkable": False,
        "attachment_points": {"end_left": [-6.0, 0.0, 0.0], "end_right": [6.0, 0.0, 0.0]},
        "builder": ARCH.build_arch_stone_wall,
    },
    "arch_arched_bridge": {
        "category": "architecture",
        "subcategory": "bridges",
        "tags": ["bridge", "crossing", "river", "pathway", "wooden"],
        "allowed_surfaces": ["water", "ground", "river"],
        "scale_constraints": {"min": 0.75, "max": 1.6, "default": 1.0},
        "walkable": True,
        "attachment_points": {"deck_center": [0.0, 0.0, 1.85], "approach_left": [-7.0, 0.0, 0.0], "approach_right": [7.0, 0.0, 0.0]},
        "builder": ARCH.build_arch_arched_bridge,
    },
    "arch_town_gate": {
        "category": "architecture",
        "subcategory": "gates",
        "tags": ["gate", "archway", "entrance", "town_square", "landmark"],
        "allowed_surfaces": ["ground", "pavement", "grass"],
        "scale_constraints": {"min": 0.75, "max": 1.6, "default": 1.0},
        "walkable": True,
        "attachment_points": {"passage_center": [0.0, 0.0, 0.0]},
        "builder": ARCH.build_arch_town_gate,
    },

    # ---------------- ENVIRONMENT (13) ----------------
    "env_road_segment": {
        "category": "environment",
        "subcategory": "roads",
        "tags": ["road", "asphalt", "street", "highway", "walkable"],
        "allowed_surfaces": ["ground", "terrain"],
        "scale_constraints": {"min": 0.5, "max": 3.0, "default": 1.0},
        "walkable": True,
        "attachment_points": {},
        "builder": ENV.build_env_road_segment,
    },
    "env_sidewalk_tile": {
        "category": "environment",
        "subcategory": "sidewalks",
        "tags": ["sidewalk", "pavement", "plaza", "walkway", "walkable"],
        "allowed_surfaces": ["ground", "terrain"],
        "scale_constraints": {"min": 0.5, "max": 3.0, "default": 1.0},
        "walkable": True,
        "attachment_points": {},
        "builder": ENV.build_env_sidewalk_tile,
    },
    "env_grass_patch": {
        "category": "environment",
        "subcategory": "grass",
        "tags": ["grass", "lawn", "turf", "park", "walkable"],
        "allowed_surfaces": ["ground", "terrain"],
        "scale_constraints": {"min": 0.5, "max": 4.0, "default": 1.0},
        "walkable": True,
        "attachment_points": {},
        "builder": ENV.build_env_grass_patch,
    },
    "env_tree_oak": {
        "category": "environment",
        "subcategory": "trees",
        "tags": ["tree", "oak", "foliage", "nature", "park"],
        "allowed_surfaces": ["ground", "grass", "terrain"],
        "scale_constraints": {"min": 0.6, "max": 2.2, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": ENV.build_env_tree_oak,
    },
    "env_bush_hedge": {
        "category": "environment",
        "subcategory": "bushes",
        "tags": ["bush", "hedge", "shrub", "foliage", "nature"],
        "allowed_surfaces": ["ground", "grass", "terrain"],
        "scale_constraints": {"min": 0.5, "max": 2.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": ENV.build_env_bush_hedge,
    },
    "env_mountain_peak": {
        "category": "environment",
        "subcategory": "mountains",
        "tags": ["mountain", "peak", "snow", "vista", "background"],
        "allowed_surfaces": ["ground", "terrain"],
        "scale_constraints": {"min": 0.8, "max": 4.0, "default": 1.0},
        "walkable": False,
        "attachment_points": {"summit": [0.0, 0.0, 24.0]},
        "builder": ENV.build_env_mountain_peak,
    },
    "env_rock_cluster": {
        "category": "environment",
        "subcategory": "rocks",
        "tags": ["rock", "boulder", "stone", "nature"],
        "allowed_surfaces": ["ground", "grass", "terrain", "river"],
        "scale_constraints": {"min": 0.5, "max": 2.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": ENV.build_env_rock_cluster,
    },
    "env_river_stream": {
        "category": "environment",
        "subcategory": "rivers",
        "tags": ["river", "stream", "water", "canal", "nature"],
        "allowed_surfaces": ["ground", "terrain"],
        "scale_constraints": {"min": 0.6, "max": 3.0, "default": 1.0},
        "walkable": False,
        "attachment_points": {"bridge_anchor": [0.0, 0.0, 0.25]},
        "builder": ENV.build_env_river_stream,
    },
    "env_terrain_hill": {
        "category": "environment",
        "subcategory": "terrain",
        "tags": ["terrain", "hill", "mound", "landscape", "background"],
        "allowed_surfaces": ["ground"],
        "scale_constraints": {"min": 0.6, "max": 3.5, "default": 1.0},
        "walkable": True,
        "attachment_points": {"hill_crest": [0.0, 0.0, 5.5]},
        "builder": ENV.build_env_terrain_hill,
    },
    "env_streetlight_classic": {
        "category": "environment",
        "subcategory": "streetlights",
        "tags": ["streetlight", "lamp", "light", "street_furniture"],
        "allowed_surfaces": ["ground", "pavement", "sidewalk", "grass"],
        "scale_constraints": {"min": 0.75, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {"bulb": [0.0, -1.4, 11.6]},
        "builder": ENV.build_env_streetlight_classic,
    },
    "env_fence_picket": {
        "category": "environment",
        "subcategory": "fences",
        "tags": ["fence", "picket", "boundary", "yard"],
        "allowed_surfaces": ["ground", "grass", "pavement"],
        "scale_constraints": {"min": 0.6, "max": 2.0, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": ENV.build_env_fence_picket,
    },
    "env_park_bench": {
        "category": "environment",
        "subcategory": "street_furniture",
        "tags": ["bench", "seat", "park", "street_furniture", "town_square"],
        "allowed_surfaces": ["ground", "pavement", "sidewalk", "grass"],
        "scale_constraints": {"min": 0.8, "max": 1.4, "default": 1.0},
        "walkable": False,
        "attachment_points": {"seat_center": [0.0, 0.0, 2.0]},
        "builder": ENV.build_env_park_bench,
    },
    "env_fountain_plaza": {
        "category": "environment",
        "subcategory": "street_furniture",
        "tags": ["fountain", "plaza", "landmark", "water", "town_square"],
        "allowed_surfaces": ["ground", "pavement", "plaza"],
        "scale_constraints": {"min": 0.7, "max": 1.8, "default": 1.0},
        "walkable": False,
        "attachment_points": {"fountain_rim": [0.0, -4.6, 0.0]},
        "builder": ENV.build_env_fountain_plaza,
    },

    # ---------------- INTERIORS (8) ----------------
    "int_bed_single": {
        "category": "interiors",
        "subcategory": "beds",
        "tags": ["bed", "bedroom", "sleep", "furniture"],
        "allowed_surfaces": ["floor"],
        "scale_constraints": {"min": 0.8, "max": 1.3, "default": 1.0},
        "walkable": False,
        "attachment_points": {"mattress_top": [0.0, 0.0, 3.0], "sit_edge": [2.4, -1.0, 2.6]},
        "builder": INT.build_int_bed_single,
    },
    "int_table_dining": {
        "category": "interiors",
        "subcategory": "tables",
        "tags": ["table", "dining", "desk", "furniture", "kitchen"],
        "allowed_surfaces": ["floor", "pavement"],
        "scale_constraints": {"min": 0.7, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {"table_top": [0.0, 0.0, 3.38]},
        "builder": INT.build_int_table_dining,
    },
    "int_sofa_couch": {
        "category": "interiors",
        "subcategory": "sofas",
        "tags": ["sofa", "couch", "living_room", "seat", "furniture"],
        "allowed_surfaces": ["floor"],
        "scale_constraints": {"min": 0.75, "max": 1.4, "default": 1.0},
        "walkable": False,
        "attachment_points": {"seat_center": [0.0, -0.3, 2.4]},
        "builder": INT.build_int_sofa_couch,
    },
    "int_cabinet_counter": {
        "category": "interiors",
        "subcategory": "cabinets",
        "tags": ["cabinet", "counter", "storage", "kitchen", "furniture"],
        "allowed_surfaces": ["floor"],
        "scale_constraints": {"min": 0.75, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {"counter_top": [0.0, 0.0, 3.72]},
        "builder": INT.build_int_cabinet_counter,
    },
    "int_door_wooden": {
        "category": "interiors",
        "subcategory": "doors",
        "tags": ["door", "entry", "interior", "wooden"],
        "allowed_surfaces": ["wall", "floor"],
        "scale_constraints": {"min": 0.8, "max": 1.3, "default": 1.0},
        "walkable": True,
        "attachment_points": {"knob": [1.45, -0.3, 3.65]},
        "builder": INT.build_int_door_wooden,
    },
    "int_window_framed": {
        "category": "interiors",
        "subcategory": "windows",
        "tags": ["window", "glass", "wall", "interior"],
        "allowed_surfaces": ["wall"],
        "scale_constraints": {"min": 0.6, "max": 1.6, "default": 1.0},
        "walkable": False,
        "attachment_points": {"sill": [0.0, 0.0, 0.9]},
        "builder": INT.build_int_window_framed,
    },
    "int_shelf_books": {
        "category": "interiors",
        "subcategory": "shelves",
        "tags": ["shelf", "bookshelf", "books", "wall", "furniture"],
        "allowed_surfaces": ["wall", "floor"],
        "scale_constraints": {"min": 0.7, "max": 1.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": INT.build_int_shelf_books,
    },
    "int_kitchen_stove_fridge": {
        "category": "interiors",
        "subcategory": "kitchen_equipment",
        "tags": ["kitchen", "stove", "fridge", "appliance", "cooking"],
        "allowed_surfaces": ["floor"],
        "scale_constraints": {"min": 0.8, "max": 1.3, "default": 1.0},
        "walkable": False,
        "attachment_points": {"burner_front": [2.2, -0.6, 3.7]},
        "builder": INT.build_int_kitchen_stove_fridge,
    },

    # ---------------- FANTASY (5) ----------------
    "fan_portal_arcane": {
        "category": "fantasy",
        "subcategory": "portals",
        "tags": ["portal", "magic", "teleporter", "arcane", "fantasy"],
        "allowed_surfaces": ["ground", "pavement", "plaza", "terrain"],
        "scale_constraints": {"min": 0.7, "max": 2.0, "default": 1.0},
        "walkable": True,
        "attachment_points": {"portal_center": [0.0, 0.0, 5.2], "step_front": [0.0, -2.0, 0.0]},
        "builder": FAN.build_fan_portal_arcane,
    },
    "fan_magical_obelisk": {
        "category": "fantasy",
        "subcategory": "magical_structures",
        "tags": ["obelisk", "monolith", "magic", "shrine", "fantasy"],
        "allowed_surfaces": ["ground", "pavement", "terrain", "plaza"],
        "scale_constraints": {"min": 0.6, "max": 2.2, "default": 1.0},
        "walkable": False,
        "attachment_points": {"apex": [0.0, 0.0, 12.1]},
        "builder": FAN.build_fan_magical_obelisk,
    },
    "fan_crystal_cluster": {
        "category": "fantasy",
        "subcategory": "crystals",
        "tags": ["crystal", "gem", "glowing", "magic", "fantasy"],
        "allowed_surfaces": ["ground", "grass", "terrain", "rock"],
        "scale_constraints": {"min": 0.5, "max": 2.5, "default": 1.0},
        "walkable": False,
        "attachment_points": {},
        "builder": FAN.build_fan_crystal_cluster,
    },
    "fan_floating_platform": {
        "category": "fantasy",
        "subcategory": "floating_platforms",
        "tags": ["floating", "island", "platform", "sky", "fantasy"],
        "allowed_surfaces": ["air", "ground", "water"],
        "scale_constraints": {"min": 0.6, "max": 2.5, "default": 1.0},
        "walkable": True,
        "attachment_points": {"platform_top": [0.0, 0.0, 6.0]},
        "builder": FAN.build_fan_floating_platform,
    },
    "fan_ancient_ruins": {
        "category": "fantasy",
        "subcategory": "ancient_structures",
        "tags": ["ruins", "temple", "ancient", "columns", "altar", "fantasy"],
        "allowed_surfaces": ["ground", "grass", "terrain"],
        "scale_constraints": {"min": 0.7, "max": 2.0, "default": 1.0},
        "walkable": True,
        "attachment_points": {"altar_front": [0.0, -1.8, 0.6]},
        "builder": FAN.build_fan_ancient_ruins,
    },
}


def compute_blender_bounds(objs):
    """
    Compute exact world-space bounding box, dimensions, and ground contact
    directly from the evaluated Blender mesh objects in `objs`.
    """
    import bpy
    from mathutils import Vector

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    xs, ys, zs = [], [], []
    for ob in objs:
        if ob is None or ob.type not in ("MESH", "CURVE", "FONT", "SURFACE", "META"):
            continue
        ev = ob.evaluated_get(dg)
        mw = ev.matrix_world
        for corner in ev.bound_box:
            wpt = mw @ Vector(corner)
            xs.append(wpt.x)
            ys.append(wpt.y)
            zs.append(wpt.z)
    if not xs:
        return {
            "min": [-0.5, -0.5, 0.0],
            "max": [0.5, 0.5, 1.0],
            "dimensions": [1.0, 1.0, 1.0],
        }
    xmin, xmax = round(min(xs), 3), round(max(xs), 3)
    ymin, ymax = round(min(ys), 3), round(max(ys), 3)
    zmin, zmax = round(min(zs), 3), round(max(zs), 3)
    return {
        "min": [xmin, ymin, zmin],
        "max": [xmax, ymax, zmax],
        "dimensions": [round(xmax - xmin, 3), round(ymax - ymin, 3), round(zmax - zmin, 3)],
    }


def instantiate_asset(ns, coll, asset_id, instance_name=None, location=(0.0, 0.0, 0.0),
                      rotation_deg=0.0, scale=1.0, **builder_kwargs):
    """
    Instantiate `asset_id` into Blender collection `coll`, parent all parts under a root Empty
    with pivot at (0, 0, 0), apply transform (location, rotation_deg, scale), and attach
    computed geometry bounds onto the root object.
    """
    import bpy
    from mathutils import Vector

    if asset_id not in ASSET_DEFINITIONS:
        raise KeyError(f"Unknown asset_id {asset_id!r}; available: {sorted(ASSET_DEFINITIONS)}")
    spec = ASSET_DEFINITIONS[asset_id]
    sc_cfg = spec["scale_constraints"]
    scale = max(sc_cfg["min"], min(sc_cfg["max"], float(scale)))

    inst_name = instance_name or f"{asset_id}"
    root_empty = bpy.data.objects.new(inst_name, None)
    root_empty.empty_display_type = "PLAIN_AXES"
    root_empty.empty_display_size = 1.0
    coll.objects.link(root_empty)

    grp, created = spec["builder"](ns, coll, name=inst_name, **builder_kwargs)
    for o in created:
        if o is not root_empty and o.parent is None:
            o.parent = root_empty

    # Compute local bounds before moving root_empty
    local_bounds = compute_blender_bounds(created)

    root_empty.location = Vector(location)
    root_empty.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))
    root_empty.scale = (scale, scale, scale)
    root_empty["asset_id"] = asset_id
    root_empty["category"] = spec["category"]
    root_empty["walkable"] = spec["walkable"]

    world_bounds = compute_blender_bounds(created)
    return root_empty, created, local_bounds, world_bounds
