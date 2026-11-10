"""
Modular Roblox Interior & Furniture Assets (reusing roblox_sets.py primitives without duplication):
  - Beds                (int_bed_single)
  - Tables              (int_table_dining)
  - Sofas               (int_sofa_couch)
  - Cabinets            (int_cabinet_counter)
  - Doors               (int_door_wooden)
  - Windows             (int_window_framed)
  - Shelves             (int_shelf_books)
  - Kitchen equipment   (int_kitchen_stove_fridge)
"""


def build_int_bed_single(ns, coll, name="BedSingle"):
    before = set(coll.objects)
    ns["bed"](coll, name, 0.0, 0.0)
    return None, [o for o in coll.objects if o not in before]


def build_int_table_dining(ns, coll, name="TableDining"):
    before = set(coll.objects)
    ns["table"](coll, name, 0.0, 0.0, w=8.0, d=5.0, h=3.2)
    return None, [o for o in coll.objects if o not in before]


def build_int_sofa_couch(ns, coll, name="SofaCouch"):
    before = set(coll.objects)
    ns["couch"](coll, name, 0.0, 0.0)
    return None, [o for o in coll.objects if o not in before]


def build_int_cabinet_counter(ns, coll, name="CabinetCounter"):
    blk, plastic = ns["blk"], ns["plastic"]
    before = set(coll.objects)
    cab = plastic(f"{name}_Cab", (0.55, 0.85, 0.75), 0.4)
    top = plastic(f"{name}_Top", (0.97, 0.97, 0.97), 0.25)
    gold = plastic(f"{name}_Gold", (1.0, 0.8, 0.3), 0.3)
    blk(coll, f"{name}_Body", (4.0, 3.0, 3.4), (0, 0, 1.7), cab, 0.08)
    blk(coll, f"{name}_Counter", (4.2, 3.3, 0.35), (0, 0, 3.55), top, 0.06)
    blk(coll, f"{name}_Handle", (1.2, 0.15, 0.2), (0, -1.55, 2.9), gold, 0.04)
    return None, [o for o in coll.objects if o not in before]


def build_int_door_wooden(ns, coll, name="DoorWooden"):
    plastic, door = ns["plastic"], ns["door"]
    before = set(coll.objects)
    door(coll, name, (0, 0, 0), plastic(f"{name}_Wood", (0.85, 0.55, 0.32), 0.45),
         plastic(f"{name}_Gold", (1.0, 0.8, 0.3)), "X", w=4.0, h=7.6)
    return None, [o for o in coll.objects if o not in before]


def build_int_window_framed(ns, coll, name="WindowFramed"):
    plastic, glass, window = ns["plastic"], ns["glass"], ns["window"]
    before = set(coll.objects)
    window(coll, name, (0, 0, 3.0), 4.8, 4.2,
           plastic(f"{name}_Frame", (1, 1, 1), 0.45, 0),
           glass(f"{name}_Glass"), "X", sill=True)
    return None, [o for o in coll.objects if o not in before]


def build_int_shelf_books(ns, coll, name="ShelfBooks"):
    before = set(coll.objects)
    ns["shelf"](coll, name, 0.0, 0.0, 1.5, axis="X", length=6.0, seed=3)
    return None, [o for o in coll.objects if o not in before]


def build_int_kitchen_stove_fridge(ns, coll, name="KitchenEquipment"):
    blk, cyl, plastic = ns["blk"], ns["cyl"], ns["plastic"]
    before = set(coll.objects)
    fr = plastic(f"{name}_Fridge", (0.95, 0.95, 0.97), 0.25)
    dark = plastic(f"{name}_Stove", (0.14, 0.14, 0.16), 0.35)
    cab = plastic(f"{name}_Base", (0.55, 0.85, 0.75), 0.4)
    # Fridge on left, Stove on right
    blk(coll, f"{name}_FridgeBody", (4.2, 3.4, 9.2), (-2.4, 0, 4.6), fr, 0.25)
    blk(coll, f"{name}_StoveBase", (4.0, 3.2, 3.4), (2.2, 0, 1.7), cab, 0.08)
    blk(coll, f"{name}_StoveTop", (3.8, 3.0, 0.25), (2.2, 0, 3.5), dark, 0.04)
    for k, (dx, dy) in enumerate(((-0.8, -0.6), (0.8, -0.6), (-0.8, 0.6), (0.8, 0.6))):
        cyl(coll, f"{name}_Burner_{k}", 0.55, 0.06, (2.2 + dx, dy, 3.65), dark)
    return None, [o for o in coll.objects if o not in before]
