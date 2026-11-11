"""
Visual & Motion QA Report Generator: combines static cinematic validation (validate.py)
with start/middle/end motion sampling (render/motion_sheet/) into:
  - episodes/<ep>/render/motion_sheet.png   (3-column start/mid/end strip per shot)
  - episodes/<ep>/render/visual_qa.json     (structured QA report with 6-part telemetry, warnings & fixes)

    python pipeline/visual_qa.py episodes/<ep>

Distinguishes:
  1. Root transform displacement (start_to_mid, mid_to_end, start_to_end, max_displacement in studs)
  2. Pose changes (bone rotation delta in degrees across R6 body bones + configured pose transitions)
  3. Action state transitions (locomotion, reactive one-shots, expressive loops, vs idle)
  4. Facial expression changes (sampled face decal at start/mid/end + configured transitions)
  5. Prop state changes (hand props & world placed props across start/mid/end)
  6. Camera movement (translation studs & rotation degrees, separated from character animation)

Note: Performs deterministic rule-based, pixel-diff, and 3D scene-telemetry checks
(does not claim AI vision inspection).
"""
import argparse, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate as VA  # noqa: E402


def _pixel_mad(path_a, path_b):
    """Mean absolute pixel difference (0..255 scale) between two rendered PNG stills."""
    try:
        a = np.asarray(Image.open(path_a).convert("RGB"), dtype=np.float32)
        b = np.asarray(Image.open(path_b).convert("RGB"), dtype=np.float32)
        if a.shape != b.shape:
            return None
        return round(float(np.mean(np.abs(a - b))), 3)
    except Exception:
        return None


def _dist3(p1, p2):
    if not p1 or not p2:
        return 0.0
    return round(math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(p1, p2))), 3)


def _bone_rot_delta_deg(rots_a, rots_b):
    """Total L1 angular change (degrees) across all sampled R6 body bones between two frames."""
    if not rots_a or not rots_b:
        return 0.0
    total = 0.0
    for bname, euler_a in rots_a.items():
        euler_b = rots_b.get(bname)
        if euler_b and len(euler_a) == 3 and len(euler_b) == 3:
            for a, b in zip(euler_a, euler_b):
                d = abs(float(a) - float(b)) % 360.0
                total += min(d, 360.0 - d)
    return round(total, 2)


def stitch_motion_sheet(ep, shots_data, ms_info):
    """Build render/motion_sheet.png with [START | MID | END] side by side per shot."""
    if not ms_info:
        return None
    text_map = {s["id"]: s.get("text", "") for s in shots_data.get("shots", [])}
    first_png = ms_info[0]["samples"]["mid"]["png"]
    if not Path(first_png).exists():
        return None
    w, h = Image.open(first_png).size
    cols = 3
    lab_h = 44
    row_w = w * cols
    row_h = h + lab_h
    canvas = Image.new("RGB", (row_w, row_h * len(ms_info)), (20, 20, 24))
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)

    for r_idx, item in enumerate(ms_info):
        sid = item["id"]
        y0 = r_idx * row_h
        for c_idx, tag in enumerate(("start", "mid", "end")):
            samp = item["samples"].get(tag, {})
            p = samp.get("png")
            x0 = c_idx * w
            if p and Path(p).exists():
                im = Image.open(p).convert("RGB")
                canvas.paste(im, (x0, y0))
                draw.text((x0 + 6, y0 + 4), f"{sid} {tag.upper()} (f{samp.get('frame')})", fill=(255, 230, 80), font=font)
        caption = f"{sid}: {text_map.get(sid, '')}"
        draw.text((6, y0 + h + 6), caption[:110], fill=(235, 235, 235), font=font)
        if len(caption) > 110:
            draw.text((6, y0 + h + 22), caption[110:220], fill=(200, 200, 200), font=font)

    out_path = ep / "render" / "motion_sheet.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path


def generate_visual_qa(ep_dir):
    ep = Path(ep_dir).resolve()
    shots_data = json.loads((ep / "shots.json").read_text(encoding="utf-8"))
    val_detail = VA.validate_detailed(ep)

    ms_json = ep / "render" / "motion_sheet" / "motion_sheet.json"
    ms_map = {}
    ms_list = []
    if ms_json.exists():
        try:
            ms_list = json.loads(ms_json.read_text(encoding="utf-8"))
            ms_map = {item["id"]: item for item in ms_list if "id" in item}
        except Exception:
            pass

    motion_sheet_png = stitch_motion_sheet(ep, shots_data, ms_list) if ms_list else None

    qa_shots = []
    total_motion_warns = 0

    for s in shots_data.get("shots", []):
        sid = s["id"]
        st_val = val_detail["shots"].get(sid, {"errors": [], "warnings": [], "suggestions": []})
        warnings = list(st_val["warnings"])
        suggestions = list(st_val["suggestions"])

        # Extract configured transitions from shots.json
        configured_actions = {}
        configured_poses = {}
        configured_faces = {}
        configured_props = {}
        for c in s.get("cast", []):
            cn = c["name"]
            chgs = sorted(c.get("changes", []), key=lambda x: x.get("at", 0.0))
            configured_actions[cn] = [{"at": 0.0, "action": c.get("action", "idle")}] + [
                {"at": ch["at"], "action": ch["action"]} for ch in chgs if "action" in ch
            ]
            configured_poses[cn] = [c.get("pose", "relaxed")] + [ch["pose"] for ch in chgs if "pose" in ch]
            configured_faces[cn] = [c.get("face", "smile")] + [ch["face"] for ch in chgs if "face" in ch]
            configured_props[cn] = [list(c.get("props", []))] + [list(ch["props"]) for ch in chgs if "props" in ch]

        motion_result = {
            "sampled": False,
            "frames": None,
            "pixel_diff_mad": None,
            "camera_moved_studs": None,
            "camera_movement": None,
            "character_displacement_studs": {},
            "root_displacement_studs": {},
            "pose_changes": {},
            "action_state_transitions": configured_actions,
            "facial_expression_changes": {},
            "prop_state_changes": {},
            "animation_summary": None,
        }

        if sid in ms_map:
            m_item = ms_map[sid]
            samps = m_item.get("samples", {})
            p_start = samps.get("start", {}).get("png")
            p_mid = samps.get("mid", {}).get("png")
            p_end = samps.get("end", {}).get("png")

            mad_sm = _pixel_mad(p_start, p_mid) if p_start and p_mid else None
            mad_me = _pixel_mad(p_mid, p_end) if p_mid and p_end else None
            mad_se = _pixel_mad(p_start, p_end) if p_start and p_end else None

            t_start = samps.get("start", {}).get("telemetry", {})
            t_mid = samps.get("mid", {}).get("telemetry", {})
            t_end = samps.get("end", {}).get("telemetry", {})

            cam_moved_sm = _dist3(t_start.get("camera_loc"), t_mid.get("camera_loc"))
            cam_moved_me = _dist3(t_mid.get("camera_loc"), t_end.get("camera_loc"))
            cam_moved_se = _dist3(t_start.get("camera_loc"), t_end.get("camera_loc"))
            cam_moved = round(max(cam_moved_se, cam_moved_sm + cam_moved_me), 3)

            cam_rot_delta = 0.0
            if t_start.get("camera_rot_deg") and t_end.get("camera_rot_deg"):
                cam_rot_delta = round(sum(
                    min(abs(a - b) % 360.0, 360.0 - (abs(a - b) % 360.0))
                    for a, b in zip(t_start["camera_rot_deg"], t_end["camera_rot_deg"])
                ), 2)

            char_disp = {}
            root_disp_detail = {}
            pose_changes_detail = {}
            face_changes_detail = {}
            prop_changes_detail = {
                "hand_props": {},
                "world_placed_props": {
                    "configured": [
                        {"id": pl.get("id", f"place{i}"), "prop": pl.get("prop"),
                         "pop_at": pl.get("pop_at"), "poof_at": pl.get("poof_at")}
                        for i, pl in enumerate(s.get("place", []))
                    ],
                    "sampled_visible_counts": {
                        "start": len(t_start.get("visible_world_props", [])),
                        "mid": len(t_mid.get("visible_world_props", [])),
                        "end": len(t_end.get("visible_world_props", [])),
                    },
                    "changed": any("pop_at" in pl or "poof_at" in pl for pl in s.get("place", [])),
                },
            }

            any_char_animated = False

            for c in s.get("cast", []):
                cn = c["name"]
                c0 = t_start.get("characters", {}).get(cn)
                cm = t_mid.get("characters", {}).get(cn)
                c1 = t_end.get("characters", {}).get(cn)

                d_sm = _dist3(c0.get("root"), cm.get("root")) if (c0 and cm) else 0.0
                d_me = _dist3(cm.get("root"), c1.get("root")) if (cm and c1) else 0.0
                d_se = _dist3(c0.get("root"), c1.get("root")) if (c0 and c1) else 0.0
                max_d = round(max(d_sm, d_me, d_se), 3)
                char_disp[cn] = max_d
                root_disp_detail[cn] = {
                    "start_to_mid": d_sm,
                    "mid_to_end": d_me,
                    "start_to_end": d_se,
                    "max_displacement": max_d,
                }

                # Pose rotation telemetry
                rot_sm = _bone_rot_delta_deg(c0.get("bone_rotations_deg") if c0 else None,
                                             cm.get("bone_rotations_deg") if cm else None)
                rot_me = _bone_rot_delta_deg(cm.get("bone_rotations_deg") if cm else None,
                                             c1.get("bone_rotations_deg") if c1 else None)
                rot_se = _bone_rot_delta_deg(c0.get("bone_rotations_deg") if c0 else None,
                                             c1.get("bone_rotations_deg") if c1 else None)
                max_rot_deg = round(max(rot_sm, rot_me, rot_se), 2)
                cfg_poses = configured_poses.get(cn, [])
                pose_changed = (len(set(cfg_poses)) > 1) or (max_rot_deg >= 8.0)
                pose_changes_detail[cn] = {
                    "configured_poses": cfg_poses,
                    "bone_rotation_delta_deg": {
                        "start_to_mid": rot_sm,
                        "mid_to_end": rot_me,
                        "start_to_end": rot_se,
                        "max_delta_deg": max_rot_deg,
                    },
                    "changed": pose_changed,
                }

                # Facial expression telemetry
                f0_name = c0.get("face_name") if c0 else None
                fm_name = cm.get("face_name") if cm else None
                f1_name = c1.get("face_name") if c1 else None
                cfg_faces = configured_faces.get(cn, [])
                face_changed = (len({x for x in (f0_name, fm_name, f1_name) if x}) > 1) or (len(set(cfg_faces)) > 1)
                face_changes_detail[cn] = {
                    "sampled_faces": {"start": f0_name, "mid": fm_name, "end": f1_name},
                    "configured_faces": cfg_faces,
                    "changed": face_changed,
                }

                # Hand prop state telemetry
                hp0 = t_start.get("visible_hand_props", {}).get(cn, [])
                hpm = t_mid.get("visible_hand_props", {}).get(cn, [])
                hp1 = t_end.get("visible_hand_props", {}).get(cn, [])
                cfg_p = configured_props.get(cn, [])
                prop_changed = (hp0 != hpm or hpm != hp1) or (len(cfg_p) > 1 and any(x != cfg_p[0] for x in cfg_p[1:]))
                prop_changes_detail["hand_props"][cn] = {
                    "configured_sequence": cfg_p,
                    "sampled_visible": {"start": hp0, "mid": hpm, "end": hp1},
                    "changed": prop_changed,
                }

                acts_for_c = [a["action"] for a in configured_actions.get(cn, [])]
                has_non_idle_action = any(a != "idle" for a in acts_for_c)
                if max_d >= 0.20 or pose_changed or face_changed or prop_changed or has_non_idle_action:
                    any_char_animated = True

                # Locomotion path checks
                if any(a in ("walk_to", "run_to", "walk_in", "walk_out", "run_out") for a in acts_for_c) and max_d < 0.25:
                    w_msg = f"{sid}: {cn} has locomotion action {acts_for_c} but max root displacement is only {max_d:.2f} studs"
                    warnings.append(w_msg)
                    suggestions.append(f"Check {cn}'s destination mark/to_dx/to_dy in {sid}; destination may equal start position.")
                    total_motion_warns += 1
                elif max_d > 24.0:
                    w_msg = f"{sid}: {cn} displaced {max_d:.1f} studs inside one shot (possible teleport or excessive speed)"
                    warnings.append(w_msg)
                    suggestions.append(f"Reduce {cn}'s movement distance in {sid} to avoid visual teleporting.")
                    total_motion_warns += 1

                if cm and cm.get("scale", 1.0) < 0.05 and not any(a in ("poof", "pop_in") for a in acts_for_c):
                    w_msg = f"{sid}: {cn} scale is near-zero ({cm.get('scale')}) at middle frame without poof/pop_in"
                    warnings.append(w_msg)
                    suggestions.append(f"Verify {cn}'s scale keyframes in {sid}.")
                    total_motion_warns += 1

            if prop_changes_detail["world_placed_props"]["changed"]:
                any_char_animated = True

            cam_animated = (cam_moved >= 0.15) or (cam_rot_delta >= 1.5)

            if mad_se is not None and mad_se < 0.35:
                w_msg = f"{sid}: start-to-end pixel difference is very low (MAD={mad_se}) - shot appears visually frozen"
                warnings.append(w_msg)
                suggestions.append(f"Add camera movement (push_in/orbit) or character action in {sid}.")
                total_motion_warns += 1
            elif cam_animated and not any_char_animated and len(s.get("cast", [])) > 0:
                w_msg = f"{sid}: camera moves ({cam_moved:.2f} studs) but characters have no root displacement, pose change, expression change, or prop change"
                warnings.append(w_msg)
                suggestions.append(f"Add purposeful character action or mid-shot pose/expression changes in {sid} instead of relying solely on camera movement.")
                total_motion_warns += 1

            # Phase 03: Multi-character interaction telemetry
            interaction_contacts = {}
            for pair_name, dist_val in t_mid.get("character_distances", {}).items():
                interaction_contacts[pair_name] = {
                    "mid_distance_studs": dist_val,
                    "within_interaction_range": dist_val <= 4.2,
                }

            motion_result = {
                "sampled": True,
                "frames": {
                    "start": samps.get("start", {}).get("frame"),
                    "mid": samps.get("mid", {}).get("frame"),
                    "end": samps.get("end", {}).get("frame"),
                },
                "pixel_diff_mad": {
                    "start_to_mid": mad_sm,
                    "mid_to_end": mad_me,
                    "start_to_end": mad_se,
                },
                "camera_moved_studs": cam_moved,
                "camera_movement": {
                    "translation_studs": cam_moved,
                    "rotation_delta_deg": cam_rot_delta,
                    "move_type": s.get("camera", {}).get("move", "static"),
                    "animated": cam_animated,
                },
                "character_displacement_studs": char_disp,
                "root_displacement_studs": root_disp_detail,
                "pose_changes": pose_changes_detail,
                "action_state_transitions": configured_actions,
                "facial_expression_changes": face_changes_detail,
                "prop_state_changes": prop_changes_detail,
                "character_interactions": interaction_contacts,
                "animation_summary": {
                    "camera_animated": cam_animated,
                    "character_animated": any_char_animated,
                    "camera_only_motion": bool(cam_animated and not any_char_animated),
                },
            }

        qa_shots.append({
            "shot_id": sid,
            "static_validation": {
                "errors": st_val["errors"],
                "warnings": st_val["warnings"],
            },
            "motion_sampling": motion_result,
            "warnings": warnings,
            "suggested_corrections": suggestions,
        })

    report = {
        "episode": shots_data.get("episode", ep.name),
        "qa_methodology": "rule_based_validation_and_3d_motion_telemetry (not AI vision inspection)",
        "motion_sheet_image": str(motion_sheet_png.relative_to(ep)) if motion_sheet_png else None,
        "summary": {
            "total_shots": len(qa_shots),
            "motion_sampled_shots": len(ms_map),
            "static_errors": len(val_detail["errors"]),
            "static_warnings": len(val_detail["warnings"]),
            "motion_warnings": total_motion_warns,
        },
        "shots": qa_shots,
    }

    out_json = ep / "render" / "visual_qa.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report, out_json, motion_sheet_png


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Generate render/visual_qa.json and render/motion_sheet.png for an episode.")
    ap.add_argument("episode_dir", help="Episode folder path (e.g. episodes/wi_3am_monster)")
    a = ap.parse_args()
    report, out_json, ms_png = generate_visual_qa(a.episode_dir)
    s = report["summary"]
    print(f"visual QA report: {out_json}")
    if ms_png:
        print(f"motion sheet:     {ms_png}")
    print(f"summary: {s['total_shots']} shots ({s['motion_sampled_shots']} motion-sampled) | "
          f"{s['static_errors']} error(s), {s['static_warnings']} static warning(s), {s['motion_warnings']} motion warning(s)")


if __name__ == "__main__":
    main()
