# Phase 01: Reusable Roblox Environment Asset Library & Composer

- **Status:** Completed
- **Date:** 2026-11-10
- **Engine Target:** Blender 5.2.3 LTS (`D:\blender.exe`) + Python Pipeline (`D:\ai-video\ROBLOX ANIMATION`)

---

## 1. Audit of Existing Implementation

| File / Directory | Pre-Upgrade State | Audit Finding & Action |
|---|---|---|
| `pipeline/roblox_sets.py` | Contained 4 hardcoded set builders (`bedroom`, `street`, `kitchen`, `classroom`) plus inline helper functions (`bed`, `table`, `couch`, `shelf`, `door`, `window`, `house`, `tree`, `bush`, `street_lamp`, `picket_fence`). | Preserved all 4 existing set builders and primitive helpers unchanged. Added `town_square` set hook delegating to `pipeline/environment_composer.py`. |
| `pipeline/episode.py` | Links `Set_<name>` collections from `public/roblox/sets/<name>.blend`, applies dressing (`day`, `sunset`, `night`), and places characters/props on `mark` empties. | Fully compatible with new sets and assets; `SEAT_HEIGHT = 2.0` seat-mark behavior preserved. |
| `pipeline/catalog.py` | Scanned `public/roblox/sets/*.blend` and `public/roblox/characters/*.blend` into `public/roblox/catalog.json`, with a hardcoded legacy `ROOT` path. | Updated to resolve `ROOT` dynamically, include `bench_sit` seat height (`2.15`), export per-set `obstacles` footprints from `Set_<name>["obstacles_json"]`, and link `asset_library` summary metadata into `public/roblox/catalog.json`. |
| `pipeline/props.py` | Builds 13 handheld/tabletop props (`phone`, `mug`, `book`, `pencil`, `backpack`, `flashlight`, `key`, `crown`, `paper`, `baseball`, `trophy`, `cookie`, `plate`). | Kept separate from environment/architectural assets; zero duplication. |
| `public/roblox/catalog.json` | Contained 4 sets (`bedroom`, `classroom`, `kitchen`, `street`) and 8 characters. | Preserved all 4 existing sets and their marks/dressings verbatim; added `town_square` (11 marks, 3 dressings, obstacle footprints) and `asset_library` summary. |
| `public/roblox/sets/` | Contained `bedroom.blend`, `classroom.blend`, `kitchen.blend`, `street.blend` and their preview PNGs. | Preserved existing `.blend` files and added `town_square.blend`, `town_square_day.png`, `town_square_sunset.png`, `town_square_night.png`, and `town_square_showcase_sheet.png`. |
| `pipeline/validate.py` & `pipeline/vocab.py` | Validated `shots.json` against `catalog.json` and 10 cinematic checks. | Extended `pipeline/validate.py` Check 2 to warn when a standing character position collides with any solid 2D obstacle footprint in `cat["sets"][st]["obstacles"]`. |

---

## 2. Reusable Asset Library Organization (35 Assets across 4 Categories)

Constructed a modular package under `pipeline/assets/` that reuses `roblox_sets.py` material/primitive helpers (`blk`, `cyl`, `ball`, `house`, `tree`, `bush`, `street_lamp`, `picket_fence`, `bed`, `table`, `couch`, `shelf`, `door`, `window`) without duplicating existing builders:

### Architecture (`pipeline/assets/architecture.py` — 9 assets)
1. `arch_house_suburban` (`houses`) — Suburban gable-roof house with porch steps, windows, and front door.
2. `arch_apartment_block` (`apartments`) — 3-story residential apartment building with balconies, railings, and canopy entry.
3. `arch_shop_bakery` (`shops`) — Commercial storefront with striped red/white awning, display window, and signboard.
4. `arch_school_facade` (`schools`) — Red-brick civic school facade with columns, pediment, double entry doors, and wall clock.
5. `arch_clock_tower` (`towers`) — Tall civic clock tower landmark with stone shaft, belfry clock face, spire, and gold finial.
6. `arch_castle_keep` (`castles`) — Fortified stone keep with battlements/crenellations and 4 corner coned turrets.
7. `arch_stone_wall` (`walls`) — Modular perimeter stone wall segment with coping and end piers.
8. `arch_arched_bridge` (`bridges`) — Walkable arched wooden plank footbridge with stone posts and side rails.
9. `arch_town_gate` (`gates`) — Walkable stone entrance archway with iron side bars, golden crest, and glowing lanterns.

### Environment (`pipeline/assets/environment.py` — 13 assets)
10. `env_road_segment` (`roads`) — Walkable asphalt road segment with dashed yellow centerline markings.
11. `env_sidewalk_tile` (`sidewalks`) — Walkable concrete plaza/sidewalk slab with expansion seams.
12. `env_grass_patch` (`grass`) — Walkable lawn turf patch with optional blossom accents.
13. `env_tree_oak` (`trees`) — Multi-sphere Roblox oak tree with trunk and foliage cluster.
14. `env_bush_hedge` (`bushes`) — Lumpy green hedge shrub.
15. `env_mountain_peak` (`mountains`) — Distant rocky mountain peak with snow cap for background vistas.
16. `env_rock_cluster` (`rocks`) — 3-boulder natural rock cluster.
17. `env_river_stream` (`rivers`) — Water channel with stone banks and foam ripples.
18. `env_terrain_hill` (`terrain`) — Two-tier stepped grassy hill mound.
19. `env_streetlight_classic` (`streetlights`) — Streetlamp post with dressing-aware emissive bulb and point light.
20. `env_fence_picket` (`fences`) — White wooden picket fence span.
21. `env_park_bench` (`street_furniture`) — Wooden park bench with iron legs/armrests and `seat_center` attachment.
22. `env_fountain_plaza` (`street_furniture`) — Circular stone plaza fountain with glowing water pool, tiered bowl, and spout.

### Interiors (`pipeline/assets/interiors.py` — 8 assets)
23. `int_bed_single` (`beds`) — Wooden single bed with mattress, pillow, and folded blanket (wraps `roblox_sets.bed`).
24. `int_table_dining` (`tables`) — 4-legged wooden dining table (wraps `roblox_sets.table`).
25. `int_sofa_couch` (`sofas`) — 3-cushion living-room sofa (wraps `roblox_sets.couch`).
26. `int_cabinet_counter` (`cabinets`) — Mint kitchen cabinet with white countertop and gold handle.
27. `int_door_wooden` (`doors`) — Framed wooden interior door with panels and gold doorknob (wraps `roblox_sets.door`).
28. `int_window_framed` (`windows`) — Framed 4-pane window with sill and dressing-aware glass (wraps `roblox_sets.window`).
29. `int_shelf_books` (`shelves`) — Wall bookshelf populated with colorful books (wraps `roblox_sets.shelf`).
30. `int_kitchen_stove_fridge` (`kitchen_equipment`) — Combined refrigerator and 4-burner stove unit.

### Fantasy (`pipeline/assets/fantasy.py` — 5 assets)
31. `fan_portal_arcane` (`portals`) — Obsidian archway with glowing purple rune strips and cyan vortex field.
32. `fan_magical_obelisk` (`magical_structures`) — Tapered dark-stone monolith with levitating emissive energy rings and glowing apex.
33. `fan_crystal_cluster` (`crystals`) — Angled cluster of glowing magenta crystal shards on a rock base.
34. `fan_floating_platform` (`floating_platforms`) — Floating grassy sky-island with inverted rock cone and levitation crystal core.
35. `fan_ancient_ruins` (`ancient_structures`) — Weathered stone temple platform with columns, broken architrave beam, and glowing altar.

---

## 3. Asset Metadata Schema (`public/roblox/asset_catalog.json`)

All dimensions, bounding boxes, and ground-contact footprints are derived directly from the evaluated Blender mesh geometry (`compute_blender_bounds` in `pipeline/assets/__init__.py`):

```json
{
  "id": "arch_clock_tower",
  "category": "architecture",
  "subcategory": "towers",
  "tags": ["tower", "clock", "landmark", "civic", "town_square"],
  "blender_ref": {
    "collection": "Asset_arch_clock_tower",
    "root_object": "arch_clock_tower",
    "blend_file": "public/roblox/assets/assets_library.blend"
  },
  "dimensions": [9.2, 9.2, 32.4],
  "bounding_box": {
    "min": [-4.6, -4.6, 0.0],
    "max": [4.6, 4.6, 32.4]
  },
  "origin_pivot": [0.0, 0.0, 0.0],
  "ground_contact": {
    "z_min": 0.0,
    "grounded": true,
    "footprint_2d": [-4.6, -4.6, 4.6, 4.6]
  },
  "collision_proxy": {
    "type": "aabb",
    "walkable": false,
    "bounds_2d": [-4.6, -4.6, 4.6, 4.6],
    "height": 32.4
  },
  "allowed_surfaces": ["ground", "pavement", "plaza"],
  "scale_constraints": {"min": 0.7, "max": 1.6, "default": 1.0},
  "attachment_points": {
    "base_front": [0.0, -4.0, 0.0],
    "spire_top": [0.0, 0.0, 32.0]
  },
  "preview_image": "public/roblox/assets/previews/arch_clock_tower.png"
}
```

---

## 4. Environment Composition & Town-Square Showcase (`pipeline/environment_composer.py`)

`EnvironmentComposer` provides:
- **Metadata-Driven Placement (`place_asset`)**: Applies scale constraints, automatic ground Z-contact offset, and world-space 2D AABB footprint transformation under translation, rotation, and scale (`transform_footprint_2d`).
- **Collision Detection & Automatic Nudging**: Detects 2D AABB overlaps (`footprints_overlap`) against solid obstacles; either raises `ValueError` (`nudge_if_overlap=False`) or shifts the placement outside the obstacle footprint (`nudge_if_overlap=True`).
- **Stage Mark & Navigable Corridor Verification (`add_mark`, `verify_navigable_paths`)**: Rejects standing marks that intersect solid obstacles (`point_in_footprint`) and verifies straight-line walking corridors between marks (`segment_intersects_footprint`).
- **Depth-Layer Organization**: Tags every placed root Empty with `layer` (`foreground`, `midground`, `background`) and stores `obstacles_json` on the set collection so `pipeline/catalog.py` exports obstacle bounds into `public/roblox/catalog.json`.

### `town_square` Showcase Composition
- **Buildings**: `arch_clock_tower`, `arch_shop_bakery`, `arch_apartment_block`, `arch_house_suburban`, `arch_school_facade`, `arch_town_gate`, `arch_stone_wall` (×2), `arch_castle_keep`.
- **Pathways & Water**: `env_road_segment`, `env_sidewalk_tile`, `env_grass_patch`, `env_river_stream`, `arch_arched_bridge`.
- **Vegetation & Terrain**: `env_tree_oak` (×2), `env_bush_hedge` (×2), `env_rock_cluster`, `env_terrain_hill`, `env_mountain_peak` (×2).
- **Street Furniture & Landmark**: `env_fountain_plaza` (focal landmark), `env_park_bench` (interactive seat mark `bench_sit`), `env_streetlight_classic` (×2), `env_fence_picket`.
- **Fantasy Shrine Corner & Vista**: `fan_portal_arcane`, `fan_crystal_cluster`, `fan_magical_obelisk`, `fan_floating_platform`, `fan_ancient_ruins`.
- **11 Stage Marks**: `center`, `plaza_left`, `plaza_right`, `fountain_front`, `shop_front`, `bench_sit` (`seat: 2.15`), `portal_spot`, `bridge_top`, `road`, `cam_default`, `cam_aerial`.

---

## 5. Tests Run & Results

- `python pipeline/test_environment_assets.py` -> **7/7 tests passed (`OK`)**:
  - `test_01_asset_catalog_validity`: `ok`
  - `test_02_missing_asset_references`: `ok`
  - `test_03_bounding_box_calculation`: `ok`
  - `test_04_collision_and_overlap_detection`: `ok`
  - `test_05_ground_placement`: `ok`
  - `test_06_asset_loading_in_blender`: `ok`
  - `test_07_existing_set_compatibility`: `ok`
- `python pipeline/test_studio.py` -> **8/8 tests passed (`OK`)**
- `python pipeline/asset_catalog.py --validate` -> **`asset catalog validation: 0 error(s)`**

---

## 6. Visual Previews Inspected

- `public/roblox/assets_lineup.png`: 35-tile contact sheet showing every individual asset isolated with category and geometry-derived dimensions.
- `public/roblox/sets/town_square_showcase_sheet.png`: 6-panel multi-angle contact sheet (`01_plaza_wide_day`, `02_bakery_bench_day`, `03_portal_bridge_day`, `04_fountain_hero_day`, `05_sunset_plaza`, `06_night_lanterns_magic`) with 6 cast members (`Theo`, `Lily`, `King`, `Dad`, `Mom` sitting on `bench_sit`, `Noob` by `portal_spot`).
- `public/roblox/sets/town_square_day.png`, `public/roblox/sets/town_square_sunset.png`, `public/roblox/sets/town_square_night.png`.

---

## 7. Known Limitations & Remaining Work

- **2D AABB Collision Proxies**: Obstacle footprints use axis-aligned 2D bounding boxes (`[xmin, ymin, xmax, ymax]`) in world space. Diagonal walls rotated at 45° have conservative rectangular AABBs; oriented bounding boxes (OBBs) or navmesh triangulation can be added in a future phase if tight diagonal alleys are needed.
- **Straight-Line Corridor Sampling**: `verify_navigable_paths` checks straight line segments between stage marks (matching `roblox_motions.walk_to` / `run_to` linear interpolation). Automatic waypoint pathfinding around obstacles is not yet wired into `roblox_motions.py`.
- **Single-Level Ground Contact**: Ground placement aligns `z_min` to a target `z` height (`location[2]`); automatic raycast snapping onto sloped terrain meshes can be added in Phase 02.

---

## 8. Commands Reference

```powershell
# 1. Build the 35-asset Blender library, derive metadata, and render asset previews + lineup sheet
& "D:\blender.exe" -b --factory-startup -t 2 --python pipeline/asset_catalog.py -- --render-previews

# 2. Validate public/roblox/asset_catalog.json in Python
python pipeline/asset_catalog.py --validate

# 3. Build the town_square showcase set (without modifying existing sets)
& "D:\blender.exe" -b --factory-startup -t 2 --python pipeline/build_sets.py -- town_square

# 4. Scan all sets + asset library into public/roblox/catalog.json
& "D:\blender.exe" -b --factory-startup -t 2 --python pipeline/catalog.py

# 5. Render town_square dressing stills + 6-panel showcase contact sheet
& "D:\blender.exe" -b --factory-startup -t 2 --python pipeline/render_set_previews.py -- town_square --sheet

# 6. Run the automated test suites
python pipeline/test_environment_assets.py
python pipeline/test_studio.py
```
