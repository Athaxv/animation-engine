"""
Background render helper (run by blender.exe -b <episode>.blend --python render_preview.py -- [scale] [out])
    scale: resolution percentage (default 50 -> 540x960 preview)
    out:   output mp4 path (default: <episode>/render/<scene>_preview.mp4)
"""
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
scale = int(argv[0]) if argv else 50
sc = bpy.context.scene
r = sc.render
r.resolution_percentage = scale
out = argv[1] if len(argv) > 1 else os.path.join(os.path.dirname(bpy.data.filepath), "render", f"{sc.name}_{'preview' if scale < 100 else 'final'}.mp4")
r.filepath = out
try:
    sc.eevee.taa_render_samples = 16 if scale < 100 else 64
except Exception:
    pass
try:  # all 4 sets' lights share one scene -> default 512 MB shadow pool overflows
    sc.eevee.shadow_pool_size = "1024"
except Exception:
    pass
print(f"Rendering {sc.frame_start}-{sc.frame_end} at {scale}% -> {out}", flush=True)
bpy.ops.render.render(animation=True)
print("DONE", out, flush=True)
