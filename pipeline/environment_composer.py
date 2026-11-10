"""
Roblox Environment Composition Module & Town-Square Showcase Builder.

Supports:
  - Placing assets into existing or new sets using asset_catalog.json metadata
  - Grouping architecture, environment, interiors, and fantasy assets into reusable collections
  - World-space 2D AABB footprint calculation under translation, rotation, and scale
  - Automatic collision / overlap detection and collision-free nudging
  - Navigable character path & stage-mark clearance verification
  - Foreground, midground, and background depth-layer composition
  - Building the 'town_square' showcase environment (day, sunset, night dressings)
"""
import json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd()
PIPE = ROOT / "pipeline"
RBX = ROOT / "public" / "roblox"
ASSET_CATALOG_PATH = RBX / "asset_catalog.json"

if str(PIPE) not in sys.path:
    sys.path.insert(0, str(PIPE))

import assets as A  # noqa: E402


def load_asset_metadata():
    if ASSET_CATALOG_PATH.exists():
        try:
            return json.loads(ASSET_CATALOG_PATH.read_text(encoding="utf-8")).get("assets", {})
        except Exception:
            pass
    return {}


def transform_footprint_2d(local_fp, location, rotation_deg=0.0, scale=1.0):
    """
    Transform local 2D footprint [xmin, ymin, xmax, ymax] by (location, rotation_deg, scale)
    into world-space AABB [w_xmin, w_ymin, w_xmax, w_ymax].
    """
    x0, y0, x1, y1 = [float(v) * float(scale) for v in local_fp]
    rad = math.radians(float(rotation_deg))
    cr, sr = math.cos(rad), math.sin(rad)
    lx, ly = float(location[0]), float(location[1])
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    wx = [lx + cx * cr - cy * sr for cx, cy in corners]
    wy = [ly + cx * sr + cy * cr for cx, cy in corners]
    return [round(min(wx), 3), round(min(wy), 3), round(max(wx), 3), round(max(wy), 3)]


def footprints_overlap(fp_a, fp_b, clearance=0.0):
    """Return True if 2D AABBs fp_a and fp_b overlap (including `clearance` margin)."""
    ax0, ay0, ax1, ay1 = fp_a
    bx0, by0, bx1, by1 = fp_b
    return not (
        ax1 + clearance <= bx0
        or bx1 + clearance <= ax0
        or ay1 + clearance <= by0
        or by1 + clearance <= ay0
    )


def point_in_footprint(x, y, fp, radius=1.0):
    """Return True if a circle of `radius` at (x, y) intersects 2D AABB `fp`."""
    x0, y0, x1, y1 = fp
    return (x0 - radius) < x < (x1 + radius) and (y0 - radius) < y < (y1 + radius)


def segment_intersects_footprint(p0, p1, fp, radius=0.85, steps=16):
    """Sample points along segment p0 -> p1 and check if any point hits `fp` within `radius`."""
    for i in range(steps + 1):
        u = i / steps
        x = p0[0] + (p1[0] - p0[0]) * u
        y = p0[1] + (p1[1] - p0[1]) * u
        if point_in_footprint(x, y, fp, radius=radius):
            return True
    return False


class EnvironmentComposer:
    """
    Metadata-driven environment composer with collision/footprint tracking,
    depth-layer grouping (foreground, midground, background), and navigable path checks.
    """

    def __init__(self, set_name, ns=None, coll=None, catalog_meta=None):
        self.set_name = set_name
        self.ns = ns
        self.coll = coll
        self.meta = catalog_meta if catalog_meta is not None else load_asset_metadata()
        self.placements = []     # list of dicts recording placed assets & world footprints
        self.obstacles = []      # non-walkable world footprints: {id, asset_id, layer, bounds_2d, height}
        self.marks = {}          # name -> {pos: [x,y,z], facing: deg, seat: optional}

    def _local_footprint(self, asset_id):
        if asset_id in self.meta:
            return self.meta[asset_id]["ground_contact"]["footprint_2d"]
        return [-2.0, -2.0, 2.0, 2.0]

    def _is_walkable(self, asset_id):
        if asset_id in self.meta:
            return bool(self.meta[asset_id]["collision_proxy"]["walkable"])
        return bool(A.ASSET_DEFINITIONS.get(asset_id, {}).get("walkable", False))

    def _height(self, asset_id, scale=1.0):
        if asset_id in self.meta:
            return round(float(self.meta[asset_id]["dimensions"][2]) * float(scale), 3)
        return round(4.0 * float(scale), 3)

    def _ground_z_offset(self, asset_id, scale=1.0):
        """Compute vertical offset so grounded assets sit cleanly on the target surface z."""
        if asset_id == "fan_floating_platform" or "window" in asset_id or "shelf" in asset_id:
            return 0.0
        if asset_id in self.meta:
            z_min = float(self.meta[asset_id]["ground_contact"]["z_min"]) * float(scale)
            if z_min < -0.05:
                return round(-z_min, 3)
        return 0.0

    def place_asset(self, asset_id, instance_id, location=(0.0, 0.0, 0.0), rotation_deg=0.0,
                    scale=1.0, layer="midground", allow_overlap=False, clearance=0.25,
                    nudge_if_overlap=True, **builder_kwargs):
        """
        Place `asset_id` at `location` with collision checking against existing solid obstacles.
        When `self.coll` and `self.ns` are provided (inside Blender), instantiates the 3D geometry
        and derives the exact world bounding box.
        """
        if asset_id not in A.ASSET_DEFINITIONS:
            raise KeyError(f"Unknown asset_id {asset_id!r}")
        spec = A.ASSET_DEFINITIONS[asset_id]
        sc_cfg = spec["scale_constraints"]
        scale = max(sc_cfg["min"], min(sc_cfg["max"], float(scale)))

        z_lift = self._ground_z_offset(asset_id, scale)
        loc = [float(location[0]), float(location[1]), float(location[2]) + z_lift]
        walkable = self._is_walkable(asset_id)
        local_fp = self._local_footprint(asset_id)
        world_fp = transform_footprint_2d(local_fp, loc, rotation_deg, scale)

        if not walkable and not allow_overlap:
            for obs in self.obstacles:
                if footprints_overlap(world_fp, obs["bounds_2d"], clearance=clearance):
                    if not nudge_if_overlap:
                        raise ValueError(
                            f"Collision detected placing {instance_id!r} ({asset_id}) at {world_fp} "
                            f"with existing obstacle {obs['id']!r} at {obs['bounds_2d']}"
                        )
                    # Nudge outward along X or Y away from the obstacle center
                    ox = 0.5 * (obs["bounds_2d"][0] + obs["bounds_2d"][2])
                    cx = 0.5 * (world_fp[0] + world_fp[2])
                    shift = (obs["bounds_2d"][2] - world_fp[0] + clearance + 0.2) if cx >= ox else -(world_fp[2] - obs["bounds_2d"][0] + clearance + 0.2)
                    loc[0] = round(loc[0] + shift, 2)
                    world_fp = transform_footprint_2d(local_fp, loc, rotation_deg, scale)

        height = self._height(asset_id, scale)
        if self.ns is not None and self.coll is not None:
            root_ob, created, local_b, world_b = A.instantiate_asset(
                self.ns, self.coll, asset_id, instance_name=instance_id,
                location=tuple(loc), rotation_deg=rotation_deg, scale=scale, **builder_kwargs
            )
            root_ob["layer"] = layer
            world_fp = [world_b["min"][0], world_b["min"][1], world_b["max"][0], world_b["max"][1]]
            height = world_b["dimensions"][2]

        rec = {
            "id": instance_id,
            "asset_id": asset_id,
            "category": spec["category"],
            "layer": layer,
            "location": [round(x, 3) for x in loc],
            "rotation_deg": round(float(rotation_deg), 2),
            "scale": round(float(scale), 3),
            "walkable": walkable,
            "bounds_2d": world_fp,
            "height": height,
        }
        self.placements.append(rec)
        if not walkable:
            self.obstacles.append({
                "id": instance_id,
                "asset_id": asset_id,
                "layer": layer,
                "bounds_2d": world_fp,
                "height": height,
            })
        return rec

    def add_mark(self, name, location, facing_deg=0.0, seat=None, check_clearance=True, radius=0.95):
        """
        Add a stage mark and verify it does not collide with any non-walkable obstacle
        (unless it is a seat mark intentionally positioned on a bench/chair/bed).
        """
        x, y, z = [round(float(v), 2) for v in location]
        if check_clearance and seat is None and not name.startswith("cam_"):
            for obs in self.obstacles:
                if point_in_footprint(x, y, obs["bounds_2d"], radius=radius):
                    raise ValueError(
                        f"Mark {name!r} at ({x}, {y}) collides with solid obstacle {obs['id']!r} ({obs['bounds_2d']})"
                    )
        info = {"pos": [x, y, z], "facing": round(float(facing_deg)) % 360}
        if seat is not None:
            info["seat"] = round(float(seat), 2)
        self.marks[name] = info
        if self.ns is not None and self.coll is not None:
            m_ob = self.ns["mark"](self.coll, self.set_name, name, (x, y, z), facing_deg)
            if seat is not None:
                m_ob["seat"] = float(seat)
        return info

    def verify_navigable_paths(self, mark_pairs, radius=0.8):
        """
        Verify that straight walking corridors between pairs of stage marks `(m_a, m_b)`
        do not intersect any non-walkable obstacle.
        """
        blocked = []
        for ma, mb in mark_pairs:
            if ma not in self.marks or mb not in self.marks:
                continue
            pa = self.marks[ma]["pos"]
            pb = self.marks[mb]["pos"]
            for obs in self.obstacles:
                if segment_intersects_footprint(pa, pb, obs["bounds_2d"], radius=radius):
                    blocked.append((ma, mb, obs["id"], obs["bounds_2d"]))
        return blocked


def compose_town_square_plan(ns=None, coll=None):
    """
    Compose the 'town_square' showcase environment using reusable assets across
    foreground, midground, and background layers.
    """
    comp = EnvironmentComposer("town_square", ns=ns, coll=coll)

    # 1. Ground, Plaza Sidewalks, Main Road & River (Walkable base surfaces)
    comp.place_asset("env_grass_patch", "ts_ground_lawn", location=(0, 18, -0.25), scale=1.0, layer="midground", allow_overlap=True, width=110.0, depth=95.0, with_flowers=False)
    comp.place_asset("env_road_segment", "ts_main_road", location=(0, -10.0, 0.0), scale=1.0, layer="foreground", allow_overlap=True, length=90.0, width=12.0)
    comp.place_asset("env_sidewalk_tile", "ts_plaza_center", location=(0, 2.5, 0.0), scale=1.0, layer="midground", allow_overlap=True, length=34.0, width=15.0)
    comp.place_asset("env_river_stream", "ts_river_east", location=(24.0, 4.0, 0.0), rotation_deg=90.0, scale=1.0, layer="midground", allow_overlap=True, length=55.0, width=6.5)
    comp.place_asset("arch_arched_bridge", "ts_river_bridge", location=(24.0, 2.0, 0.2), rotation_deg=0.0, scale=1.0, layer="midground", allow_overlap=True)

    # 2. Focal Landmark & Street Furniture (Midground)
    comp.place_asset("env_fountain_plaza", "ts_fountain", location=(0.0, 7.5, 0.3), scale=0.95, layer="midground")
    comp.place_asset("env_park_bench", "ts_bench_west", location=(-6.8, 8.2, 0.3), rotation_deg=20.0, scale=1.0, layer="midground")
    comp.place_asset("env_streetlight_classic", "ts_lamp_west", location=(-15.5, -2.5, 0.3), rotation_deg=0.0, scale=1.0, layer="foreground")
    comp.place_asset("env_streetlight_classic", "ts_lamp_east", location=(15.5, -2.5, 0.3), rotation_deg=0.0, scale=1.0, layer="foreground")
    comp.place_asset("env_fence_picket", "ts_fence_west", location=(-17.5, 9.5, 0.3), rotation_deg=0.0, scale=1.0, layer="midground")

    # 3. Buildings & Architecture (Background & Flanks)
    comp.place_asset("arch_clock_tower", "ts_clock_tower", location=(0.0, 21.0, 0.0), rotation_deg=0.0, scale=1.0, layer="background")
    comp.place_asset("arch_shop_bakery", "ts_bakery_shop", location=(-15.5, 19.5, 0.0), rotation_deg=12.0, scale=1.0, layer="background")
    comp.place_asset("arch_apartment_block", "ts_apartments", location=(17.5, 22.0, 0.0), rotation_deg=-10.0, scale=0.95, layer="background")
    comp.place_asset("arch_house_suburban", "ts_cottage_west", location=(-32.0, 18.0, 0.0), rotation_deg=20.0, scale=0.9, layer="background")
    comp.place_asset("arch_school_facade", "ts_school_east", location=(38.0, 22.0, 0.0), rotation_deg=-15.0, scale=0.85, layer="background")
    comp.place_asset("arch_town_gate", "ts_north_gate", location=(0.0, 32.0, 0.0), rotation_deg=0.0, scale=1.0, layer="background", allow_overlap=True)
    comp.place_asset("arch_stone_wall", "ts_wall_nw", location=(-13.0, 32.0, 0.0), rotation_deg=0.0, scale=1.0, layer="background")
    comp.place_asset("arch_stone_wall", "ts_wall_ne", location=(13.0, 32.0, 0.0), rotation_deg=0.0, scale=1.0, layer="background")

    # 4. Trees, Bushes, Rocks & Distant Vista (Background & Flanks)
    comp.place_asset("env_tree_oak", "ts_tree_nw", location=(-11.5, 11.5, 0.0), scale=0.95, layer="midground")
    comp.place_asset("env_tree_oak", "ts_tree_ne", location=(11.5, 11.5, 0.0), scale=0.95, layer="midground")
    comp.place_asset("env_bush_hedge", "ts_bush_w", location=(-6.5, 11.0, 0.3), scale=1.0, layer="midground")
    comp.place_asset("env_bush_hedge", "ts_bush_e", location=(6.5, 11.0, 0.3), scale=1.0, layer="midground")
    comp.place_asset("env_rock_cluster", "ts_river_rocks", location=(20.5, -4.5, 0.2), scale=1.0, layer="midground")
    comp.place_asset("env_terrain_hill", "ts_hill_vista", location=(-28.0, 48.0, 0.0), scale=1.8, layer="background", allow_overlap=True)
    comp.place_asset("arch_castle_keep", "ts_distant_castle", location=(-28.0, 48.0, 5.0), scale=0.85, layer="background", allow_overlap=True)
    comp.place_asset("env_mountain_peak", "ts_mountain_l", location=(-5.0, 68.0, 0.0), scale=1.8, layer="background", allow_overlap=True)
    comp.place_asset("env_mountain_peak", "ts_mountain_r", location=(28.0, 65.0, 0.0), scale=1.6, layer="background", allow_overlap=True)

    # 5. Fantasy Shrine Corner (East of the Plaza)
    comp.place_asset("fan_portal_arcane", "ts_arcane_portal", location=(13.5, 12.5, 0.3), rotation_deg=-22.0, scale=0.85, layer="midground", allow_overlap=True)
    comp.place_asset("fan_crystal_cluster", "ts_crystals", location=(18.5, 11.5, 0.3), scale=0.9, layer="midground")
    comp.place_asset("fan_magical_obelisk", "ts_obelisk", location=(-18.5, 8.0, 0.3), scale=0.85, layer="midground")
    comp.place_asset("fan_floating_platform", "ts_sky_island", location=(14.0, 36.0, 14.0), scale=1.1, layer="background", allow_overlap=True)
    comp.place_asset("fan_ancient_ruins", "ts_ruins_vista", location=(32.0, 38.0, 0.0), rotation_deg=-20.0, scale=0.9, layer="background", allow_overlap=True)

    # 6. Character Interaction Stage Marks & Cameras (Verified Collision-Free)
    comp.add_mark("center", (0.0, 0.5, 0.35), facing_deg=0.0)
    comp.add_mark("plaza_left", (-4.2, 0.5, 0.35), facing_deg=0.0)
    comp.add_mark("plaza_right", (4.2, 0.5, 0.35), facing_deg=0.0)
    comp.add_mark("fountain_front", (0.0, 1.8, 0.35), facing_deg=0.0)
    comp.add_mark("shop_front", (-12.5, 4.5, 0.35), facing_deg=0.0)
    comp.add_mark("bench_sit", (-6.8, 8.0, 0.35), facing_deg=20.0, seat=2.15, check_clearance=False)
    comp.add_mark("portal_spot", (10.2, 6.2, 0.35), facing_deg=0.0)
    comp.add_mark("bridge_top", (24.0, 2.0, 2.05), facing_deg=0.0, check_clearance=False)
    comp.add_mark("road", (0.0, -8.5, 0.3), facing_deg=0.0)
    comp.add_mark("cam_default", (0.0, -16.5, 5.2), facing_deg=0.0, check_clearance=False)
    comp.add_mark("cam_aerial", (0.0, -58.0, 42.0), facing_deg=0.0, check_clearance=False)

    # Verify main navigable character paths across the plaza
    corridors = [
        ("plaza_left", "center"),
        ("center", "plaza_right"),
        ("center", "fountain_front"),
        ("plaza_left", "shop_front"),
        ("plaza_right", "portal_spot"),
    ]
    blocked = comp.verify_navigable_paths(corridors, radius=0.75)
    if blocked:
        raise RuntimeError(f"Navigable path blocked in town_square: {blocked}")

    return comp


def build_town_square(ns, coll):
    """Blender set builder for 'town_square' (called by roblox_sets.build_set('town_square'))."""
    comp = compose_town_square_plan(ns=ns, coll=coll)
    ns["sun"](coll, "town_square", {
        "day":    (4.5, 48, 205, (1.0, 0.96, 0.88)),
        "sunset": (3.2, 14, 248, (1.0, 0.64, 0.40)),
        "night":  (0.45, 35, 200, (0.52, 0.64, 1.0)),
    })
    ns["light"](coll, "TS_PlazaFill", "AREA", (0, -2, 18.0), (0, 0, 0), (1.0, 0.96, 0.90),
                {"day": 3200, "sunset": 2200, "night": 950}, size=24)
    coll["obstacles_json"] = json.dumps(comp.obstacles)
    return comp
