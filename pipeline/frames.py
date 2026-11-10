"""
Grab stills from any .blend (episode or edit) for review:
    blender -b <file.blend> --python pipeline/frames.py -- <out_dir> <frame> [<frame> ...]
"""
import bpy, os, sys
argv = sys.argv[sys.argv.index("--") + 1:]
out, frames = os.path.abspath(argv[0]), [int(f) for f in argv[1:]]
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
r = sc.render
try:
    r.image_settings.media_type = 'IMAGE'
except Exception:
    pass
r.image_settings.file_format = 'PNG'
r.resolution_percentage = min(r.resolution_percentage, 50)
for f in frames:
    sc.frame_set(f)
    r.filepath = os.path.join(out, f"f{f:05d}.png")
    bpy.ops.render.render(write_still=True)
    print("wrote", r.filepath, os.path.exists(r.filepath), flush=True)
print("DONE frames", len(frames))
