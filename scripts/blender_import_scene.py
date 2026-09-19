"""Import a Stage-5 scene JSON into Blender.

Usage from the project root:

    blender --background --python scripts/blender_import_scene.py -- \
        examples/stage5_deformed_scene.json \
        --save-blend examples/stage5_deformed_scene.blend

The script adds ../src to sys.path automatically, so an editable pip install is
not required for this repository layout.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tunnel_scanner_core.blender_adapter import build_scene_package_in_blender
from tunnel_scanner_core.scene_io import read_scene_package_json


def _argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene_json", type=Path)
    parser.add_argument("--save-blend", type=Path, default=None)
    parser.add_argument("--root-collection", default="TunnelScanner")
    parser.add_argument("--keep-existing-root", action="store_true")
    return parser.parse_args(_argv_after_double_dash())


def main() -> None:
    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=not args.keep_existing_root,
    )
    print(
        f"Imported {len(result.object_names)} objects into collection "
        f"{result.root_collection_name!r}."
    )

    if args.save_blend is not None:
        import bpy  # type: ignore

        output = args.save_blend.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        print(f"Saved: {output}")


if __name__ == "__main__":
    main()
