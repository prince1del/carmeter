#!/usr/bin/env python3
"""Rebuild data/digit-cache from templates/digit_template.psd."""

from __future__ import annotations

import json
from pathlib import Path

from psd_tools import PSDImage

ROOT = Path(__file__).resolve().parents[1]
PSD_PATH = ROOT / "templates" / "digit_template.psd"
CACHE = ROOT / "data" / "digit-cache"


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    psd = PSDImage.open(PSD_PATH)
    meta = {"width": psd.width, "height": psd.height, "groups": {}}

    for group in psd:
        gname = group.name
        meta["groups"][gname] = {"positions": {}, "digits": {}}
        gdir = CACHE / gname
        gdir.mkdir(exist_ok=True)
        for layer in group:
            parts = layer.name.split()
            digit = parts[0]
            pos = int(parts[-1])
            img = layer.topil()
            if img is None:
                continue
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            left, top, _, _ = layer.bbox
            out_name = f"{digit}_pos{pos}.png"
            img.save(gdir / out_name, "PNG")
            key = f"{digit}:{pos}"
            meta["groups"][gname]["digits"][key] = {
                "file": f"{gname}/{out_name}",
                "left": left,
                "top": top,
                "width": img.width,
                "height": img.height,
                "digit": digit,
                "pos": pos,
            }
            meta["groups"][gname]["positions"][str(pos)] = True
            print(f"cached {gname} {key}")

    (CACHE / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Done {psd.width}x{psd.height}")


if __name__ == "__main__":
    main()
