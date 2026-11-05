# Builds the realistic city's models (docs/models.md) into one directory:
#
#   bun run models [-- ids...] [--no-bake] [--no-tex]
#   (blender -b --factory-startup -P blender/real/build.py -- public/models a1 s1)
#
# Writes tex/*.png (the shared texture library; --no-tex skips it, but a
# model's own textures are always made with it), and per model <id>.glb
# (pieces as nodes, materials named by role) and <id>_ao.png (AO baked on
# its lightmap UVs). The output is git-ignored; the app falls back to the
# low-poly kit for any model that is missing.
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lib  # noqa: E402

MODELS = {"a1": "a1_apartment", "c1": "c1_farmhouse", "c3": "c3_modern", "c4": "c4_aframe", "s1": "s1_shop", "s3": "s3_diner", "s4": "s4_factory", "cars": "vehicles", "trees": "trees", "street": "street", "bridge": "bridge"}

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
flags = {a for a in argv if a.startswith("--")}
args = [a for a in argv if not a.startswith("--")]
out = args[0] if args else "public/models"
ids = args[1:] or list(MODELS)
os.makedirs(out, exist_ok=True)

if "--no-tex" not in flags:
    lib.textures(os.path.join(out, "tex"))
for id_ in ids:
    lib.reset()
    mod = importlib.import_module(MODELS[id_])
    # A model's own textures (leaves, bark, ...) are made with it.
    if hasattr(mod, "TEXTURES"):
        lib.textures(os.path.join(out, "tex"), mod.TEXTURES)
    mod.build(out, bake="--no-bake" not in flags)
