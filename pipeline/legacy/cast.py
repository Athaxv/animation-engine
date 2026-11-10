"""
Cast list: recipes for every character. Rebuild any of them with
    build_character(**CAST["Maya"])  (after loading blocky_rig.py + wardrobe.py)

Skin tones (sRGB)
"""
SKIN = {
    "light":  (1.0, 0.87, 0.72),
    "peach":  (1.0, 0.83, 0.66),
    "tan":    (0.87, 0.66, 0.47),
    "brown":  (0.63, 0.43, 0.29),
    "dark":   (0.42, 0.27, 0.18),
}

CAST = {
    "Hero": dict(skin=SKIN["peach"], hair=(0.55, 0.32, 0.17), hair_style="spiky", outfit="jacket",
                 top=(0.86, 0.22, 0.17), top2=(0.97, 0.96, 0.93), pants=(0.16, 0.18, 0.26),
                 accent=(0.98, 0.78, 0.2), eye_color=(0.18, 0.35, 0.75), hair_seed=1),

    # --- main friends
    "Maya": dict(skin=SKIN["tan"], hair=(0.13, 0.08, 0.07), hair_style="long", outfit="hoodie",
                 top=(0.6, 0.38, 0.9), top2=(0.97, 0.97, 0.97), pants=(0.2, 0.22, 0.3), shoes=(0.95, 0.95, 0.95),
                 accent=(1.0, 0.75, 0.85), eye_color=(0.35, 0.22, 0.12), lashes=True),
    "Leo": dict(skin=SKIN["dark"], hair=(0.08, 0.06, 0.05), hair_style="curly", outfit="tshirt",
                top=(0.25, 0.7, 0.35), top2=(1.0, 1.0, 1.0), pants=(0.25, 0.35, 0.6), shoes=(0.95, 0.4, 0.2),
                accent=(1.0, 0.85, 0.2), eye_color=(0.3, 0.18, 0.1), hair_seed=4),
    "Kenji": dict(skin=SKIN["light"], hair=(0.07, 0.07, 0.09), hair_style="side_part", outfit="hoodie",
                  top=(0.22, 0.45, 0.85), top2=(0.95, 0.95, 0.95), pants=(0.15, 0.15, 0.18), shoes=(0.9, 0.9, 0.9),
                  accent=(0.95, 0.95, 0.95), eye_color=(0.2, 0.15, 0.12), accessories=("glasses",)),
    "Sofia": dict(skin=SKIN["peach"], hair=(0.98, 0.82, 0.42), hair_style="ponytail", outfit="dress",
                  top=(1.0, 0.55, 0.7), top2=(1.0, 1.0, 1.0), pants=(1.0, 0.86, 0.72), shoes=(0.95, 0.3, 0.45),
                  accent=(1.0, 1.0, 1.0), eye_color=(0.2, 0.55, 0.85), lashes=True),
    "Zoe": dict(skin=SKIN["light"], hair=(0.85, 0.32, 0.15), hair_style="bun", outfit="tshirt",
                top=(1.0, 0.82, 0.25), top2=(1.0, 1.0, 1.0), pants=(0.3, 0.35, 0.55), shoes=(0.95, 0.95, 0.95),
                accent=(0.95, 0.35, 0.3), eye_color=(0.25, 0.6, 0.35), lashes=True),
    "Max": dict(skin=SKIN["brown"], hair=(0.1, 0.07, 0.05), hair_style="cap", outfit="hoodie",
                top=(1.0, 0.55, 0.15), top2=(1.0, 1.0, 1.0), pants=(0.12, 0.12, 0.14), shoes=(0.2, 0.2, 0.22),
                accent=(0.85, 0.15, 0.15), eye_color=(0.3, 0.2, 0.1)),
    "Ava": dict(skin=SKIN["dark"], hair=(0.1, 0.07, 0.06), hair_style="long", outfit="jacket",
                top=(0.2, 0.62, 0.55), top2=(1.0, 0.95, 0.85), pants=(0.85, 0.82, 0.75), shoes=(0.95, 0.95, 0.95),
                accent=(0.95, 0.85, 0.5), eye_color=(0.35, 0.22, 0.12), lashes=True),

    # --- adults / authority
    "Captain": dict(skin=SKIN["peach"], hair=(0.08, 0.08, 0.1), hair_style="short", outfit="uniform",
                    top=(0.97, 0.97, 0.97), top2=(1.0, 1.0, 1.0), pants=(0.97, 0.97, 0.97), shoes=(0.1, 0.1, 0.12),
                    accent=(0.95, 0.72, 0.18), eye_color=(0.2, 0.3, 0.5)),
    "Grandpa": dict(skin=SKIN["light"], hair=(0.82, 0.82, 0.85), hair_style="buzz", outfit="jacket",
                    top=(0.52, 0.35, 0.22), top2=(0.9, 0.86, 0.75), pants=(0.4, 0.38, 0.35), shoes=(0.3, 0.2, 0.15),
                    accent=(0.75, 0.6, 0.35), eye_color=(0.4, 0.5, 0.6), accessories=("glasses", "mustache")),
    "Agent": dict(skin=SKIN["tan"], hair=(0.06, 0.06, 0.07), hair_style="buzz", outfit="suit",
                  top=(0.1, 0.1, 0.12), top2=(1.0, 1.0, 1.0), pants=(0.1, 0.1, 0.12), shoes=(0.05, 0.05, 0.06),
                  accent=(0.1, 0.1, 0.12), eye_color=(0.2, 0.2, 0.25), accessories=("sunglasses",)),
}
NEW_10 = ["Maya", "Leo", "Kenji", "Sofia", "Zoe", "Max", "Ava", "Captain", "Grandpa", "Agent"]
