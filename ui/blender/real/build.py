# Builds the realistic city's models (docs/models.md) into one directory:
#
#   bun run models [-- ids...] [--no-bake] [--no-tex]
#   (blender -b --factory-startup -P blender/real/build.py -- public/models a1 s1)
#
# Writes tex/*.png (the shared texture library), and per model <id>.glb
# (pieces as nodes, materials named by role) and <id>_ao.png (AO baked on
# its lightmap UVs). The output is git-ignored; the app falls back to the
# low-poly kit for any model that is missing.
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lib  # noqa: E402

MODELS = {"a1": "a1_apartment", "c1": "c1_farmhouse", "c3": "c3_modern", "s1": "s1_shop"}

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
    importlib.import_module(MODELS[id_]).build(out, bake="--no-bake" not in flags)
