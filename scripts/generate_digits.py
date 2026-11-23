#!/usr/bin/env python3
"""Compose meter JPGs: PSD digits on meter photo, sample-style crop (no PDF)."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "digit-cache"
META_PATH = CACHE / "meta.json"
BACKGROUND_PATH = ROOT / "data" / "meter_background.jpg"

BIG_LEN = 5
SMALL_LEN = 6
DISPLAY_CENTER = (1740, 2080)

# In-memory digit PNG cache (huge speedup vs reopening 11 files per row)
_DIGIT_LAYER_CACHE: dict[str, Image.Image] = {}
_PREP_BG: Image.Image | None = None


def _raw_number_text(value: object, length: int) -> str:
    """Turn Excel/text into a clean numeric string before digit extraction.

    Excel often stores trip values as binary floats (1025.1000000000001).
    Taking digits from that string and keeping the last N chars yields 00001.
    BIG (5 digits) is shown as XXXX.X → keep 1 decimal. SMALL is whole km.
    """
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if length == BIG_LEN:
            return f"{value:.1f}"
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.0f}"
    raw = str(value).strip()
    if not raw:
        return ""
    # Long float tails in text (from Excel) → reformat
    if re.fullmatch(r"[-+]?\d+\.\d+", raw):
        try:
            num = float(raw)
        except ValueError:
            return raw
        if length == BIG_LEN:
            return f"{num:.1f}"
        if abs(num - round(num)) < 1e-9:
            return str(int(round(num)))
        return f"{num:.0f}"
    return raw


def only_digits(value: object, length: int) -> str:
    raw = _raw_number_text(value, length)
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValueError(f"No digits found in value: {value!r}")
    if len(digits) < length:
        digits = digits.zfill(length)
    if len(digits) > length:
        digits = digits[-length:]
    return digits


def load_meta():
    return json.loads(META_PATH.read_text())


def clear_runtime_caches() -> None:
    global _PREP_BG
    _DIGIT_LAYER_CACHE.clear()
    _PREP_BG = None


def preload_digit_layers(meta: dict) -> None:
    """Load every digit PNG once into RAM for the batch."""
    for group in meta["groups"].values():
        for info in group["digits"].values():
            rel = info["file"]
            if rel in _DIGIT_LAYER_CACHE:
                continue
            _DIGIT_LAYER_CACHE[rel] = Image.open(CACHE / rel).convert("RGBA")


def prepare_background(meta: dict, background: Image.Image) -> Image.Image:
    """Convert/resize meter photo once; callers copy() per row."""
    global _PREP_BG
    if _PREP_BG is not None and _PREP_BG.size == (meta["width"], meta["height"]):
        return _PREP_BG
    canvas = background.convert("RGBA")
    if canvas.size != (meta["width"], meta["height"]):
        canvas = canvas.resize((meta["width"], meta["height"]), Image.BILINEAR)
    _PREP_BG = canvas
    return _PREP_BG


def compose_one(meta: dict, big: str, small: str, background: Image.Image) -> Image.Image:
    base = prepare_background(meta, background)
    canvas = base.copy()

    for group_name, number in (("BIG", big), ("Small", small)):
        group = meta["groups"][group_name]
        for pos, digit in enumerate(number, start=1):
            key = f"{digit}:{pos}"
            info = group["digits"].get(key)
            if not info:
                raise ValueError(f"Missing digit layer {group_name} {key}")
            rel = info["file"]
            layer = _DIGIT_LAYER_CACHE.get(rel)
            if layer is None:
                layer = Image.open(CACHE / rel).convert("RGBA")
                _DIGIT_LAYER_CACHE[rel] = layer
            canvas.alpha_composite(layer, (info["left"], info["top"]))
    return canvas.convert("RGB")


def apply_color_variation(
    img: Image.Image, rng: random.Random, scene_index: int | None = None
) -> tuple[Image.Image, str]:
    scenes = [
        ("morning_warm", 1.08, 1.05, 1.12, 22, 1.02),
        ("noon_harsh", 1.18, 1.20, 0.95, 4, 0.96),
        ("afternoon_gold", 1.05, 1.10, 1.15, 28, 1.00),
        ("evening_amber", 0.92, 1.12, 1.20, 35, 0.98),
        ("overcast_flat", 1.02, 0.88, 0.82, -6, 1.04),
        ("shade_cool", 0.90, 1.05, 0.90, -22, 1.02),
        ("bright_window", 1.22, 1.08, 1.05, 10, 0.94),
        ("garage_mix", 0.85, 1.15, 1.08, 16, 1.06),
    ]
    if scene_index is None:
        name, bri, con, col, warm, mid = rng.choice(scenes)
    else:
        name, bri, con, col, warm, mid = scenes[scene_index % len(scenes)]
    bri *= rng.uniform(0.96, 1.05)
    con *= rng.uniform(0.95, 1.06)
    col *= rng.uniform(0.94, 1.06)
    warm += rng.uniform(-6, 6)

    out = img
    out = ImageEnhance.Brightness(out).enhance(bri)
    out = ImageEnhance.Contrast(out).enhance(con)
    out = ImageEnhance.Color(out).enhance(col)

    # NumPy channel tweak (much faster than PIL point() lambdas)
    arr = np.asarray(out, dtype=np.int16)
    if warm >= 0:
        arr[..., 0] = np.clip(arr[..., 0] + int(warm), 0, 255)
        arr[..., 1] = np.clip(arr[..., 1] + int(warm * 0.25), 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] - int(warm * 0.65), 0, 255)
    else:
        cool = -warm
        arr[..., 2] = np.clip(arr[..., 2] + int(cool), 0, 255)
        arr[..., 1] = np.clip(arr[..., 1] + int(cool * 0.15), 0, 255)
        arr[..., 0] = np.clip(arr[..., 0] - int(cool * 0.55), 0, 255)
    out = Image.fromarray(arr.astype(np.uint8))

    if abs(mid - 1.0) > 0.001:
        gamma = 1.0 / mid
        lut = [int(max(0, min(255, ((p / 255.0) ** gamma) * 255))) for p in range(256)]
        out = out.point(lut * 3)

    if rng.random() < 0.55:
        wash = Image.new("RGB", out.size, (255, 245, 230) if warm >= 0 else (230, 240, 255))
        out = Image.blend(out, wash, rng.uniform(0.05, 0.14))

    return out, name

def _corners_ok(arr: np.ndarray, limit: int = 35) -> bool:
    """Reject frames whose corner patches are near-black (rotate/fill artifacts)."""
    h, w = arr.shape[:2]
    s = max(8, min(h, w) // 40)
    patches = (
        arr[:s, :s],
        arr[:s, -s:],
        arr[-s:, :s],
        arr[-s:, -s:],
    )
    for p in patches:
        if float(p.mean()) < limit:
            return False
    return True


def sample_style_crop(
    img: Image.Image,
    rng: random.Random,
    *,
    angle_sign: int | None = None,
    zoom_mode: str | None = None,
) -> tuple[Image.Image, dict]:
    """
    Handheld crop: left/right tilt + zoom in/out.
    ALWAYS keeps the full digit display (BIG+Small) inside the frame.
    """
    w, h = img.size

    # Digit display bbox on the 3000x4416 canvas (with comfortable side margin)
    # BIG ~ (1575,1964)-(1897,2073), Small ~ (1622,2108)-(1948,2197)
    # Keep LCD bezel + "km" + a bit of gauges inside frame
    disp_l, disp_t, disp_r, disp_b = 1420, 1820, 2100, 2340
    disp_cx = (disp_l + disp_r) // 2
    disp_cy = (disp_t + disp_b) // 2
    disp_w = disp_r - disp_l
    disp_h = disp_b - disp_t

    zoom_choices = ("close", "medium", "wide")
    if zoom_mode not in zoom_choices:
        zoom_mode = rng.choice(zoom_choices)

    # Crop must leave room around display so rotate inset never eats digits
    min_w_for_display = int(disp_w * {"close": 1.55, "medium": 1.85, "wide": 2.25}[zoom_mode])
    min_h_for_display = int(disp_h * {"close": 1.65, "medium": 1.95, "wide": 2.35}[zoom_mode])

    aspect = rng.uniform(0.66, 0.72)
    crop_w = max(min_w_for_display, int(w * {"close": 0.50, "medium": 0.58, "wide": 0.70}[zoom_mode]))
    crop_h = max(min_h_for_display, int(crop_w / aspect))
    if crop_h < min_h_for_display:
        crop_h = min_h_for_display
        crop_w = int(crop_h * aspect)
    if crop_w > w:
        crop_w = w
        crop_h = int(crop_w / aspect)
    if crop_h > h:
        crop_h = h
        crop_w = int(crop_h * aspect)

    # Very light jitter only — display stays near center
    max_jitter_x = max(0, (crop_w - disp_w) // 8)
    max_jitter_y = max(0, (crop_h - disp_h) // 8)
    cx = disp_cx + rng.randint(-max_jitter_x, max_jitter_x)
    cy = disp_cy + rng.randint(-max_jitter_y, max_jitter_y)

    left = int(cx - crop_w / 2)
    top = int(cy - crop_h / 2)
    left = max(0, min(left, w - crop_w))
    top = max(0, min(top, h - crop_h))

    # Hard pad: at least ~80px of canvas beyond display on each side before rotate
    pad = 80
    if left > disp_l - pad:
        left = max(0, disp_l - pad)
    if top > disp_t - pad:
        top = max(0, disp_t - pad)
    if left + crop_w < disp_r + pad:
        left = min(w - crop_w, disp_r + pad - crop_w)
    if top + crop_h < disp_b + pad:
        top = min(h - crop_h, disp_b + pad - crop_h)
    left = max(0, min(left, w - crop_w))
    top = max(0, min(top, h - crop_h))

    cropped = img.crop((left, top, left + crop_w, top + crop_h))

    if angle_sign not in (-1, 1):
        angle_sign = rng.choice([-1, 1])
    # Mild tilt — keeps side margins after inset
    angle = angle_sign * rng.uniform(2.5, 6.0)

    rotated = cropped.rotate(angle, resample=Image.BILINEAR, expand=False)
    rw, rh = rotated.size
    rad = abs(angle) * 3.14159 / 180.0
    inset_x = int(rw * (0.05 + 0.40 * abs(np.sin(rad)))) + 4
    inset_y = int(rh * (0.05 + 0.40 * abs(np.sin(rad)))) + 4
    inset_x = min(inset_x, rw // 6)
    inset_y = min(inset_y, rh // 6)
    inner = rotated.crop((inset_x, inset_y, rw - inset_x, rh - inset_y))

    iw, ih = inner.size
    # Keep most of the safe inner area (don't re-crop aggressively)
    target_w = int(min(iw, ih * aspect) * rng.uniform(0.94, 0.99))
    target_h = int(target_w / aspect)
    target_w = max(100, min(target_w, iw))
    target_h = max(100, min(target_h, ih))
    if target_h > ih:
        target_h = ih
        target_w = min(iw, int(target_h * aspect))

    x0 = max(0, (iw - target_w) // 2 + rng.randint(-max(0, iw // 50), max(0, iw // 50)))
    y0 = max(0, (ih - target_h) // 2 + rng.randint(-max(0, ih // 50), max(0, ih // 50)))
    x0 = max(0, min(x0, iw - target_w))
    y0 = max(0, min(y0, ih - target_h))
    framed = inner.crop((x0, y0, x0 + target_w, y0 + target_h))

    arr = np.asarray(framed)
    for _ in range(12):
        if _corners_ok(arr, limit=30):
            break
        if arr.shape[0] < 200 or arr.shape[1] < 200:
            break
        arr = arr[2:-2, 2:-2]
    framed = Image.fromarray(arr)

    out_w = rng.randint(1700, 2100)
    out_h = max(1, int(out_w / (framed.width / max(1, framed.height))))
    framed = framed.resize((out_w, out_h), Image.BILINEAR)
    meta = {
        "angle_dir": "left" if angle_sign < 0 else "right",
        "angle_deg": round(angle, 2),
        "zoom": zoom_mode,
    }
    return framed, meta


def unique_jpg_name(out_dir: Path, small: str) -> str:
    name = f"{small}.jpg"
    if not (out_dir / name).exists():
        return name
    n = 2
    while (out_dir / f"{small}_{n}.jpg").exists():
        n += 1
    return f"{small}_{n}.jpg"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True, help="JSON file with rows")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed")
    args = parser.parse_args()

    if not BACKGROUND_PATH.exists():
        print(json.dumps({"error": f"Missing meter background: {BACKGROUND_PATH}"}), file=sys.stderr)
        return 1

    jobs = json.loads(Path(args.jobs).read_text())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_runtime_caches()
    meta = load_meta()
    preload_digit_layers(meta)
    background = Image.open(BACKGROUND_PATH)
    prepare_background(meta, background)
    base_rng = random.Random(args.seed)

    results = []
    zoom_cycle = ("close", "medium", "wide")
    for i, row in enumerate(jobs, start=1):
        try:
            big = only_digits(row.get("big"), BIG_LEN)
            small = only_digits(row.get("small"), SMALL_LEN)
            rng = random.Random(base_rng.randint(0, 2**31 - 1))
            full = compose_one(meta, big, small, background)
            angle_sign = -1 if (i % 2 == 1) else 1
            zoom_mode = zoom_cycle[(i - 1) % 3]
            styled, crop_meta = sample_style_crop(
                full, rng, angle_sign=angle_sign, zoom_mode=zoom_mode
            )
            styled, shade = apply_color_variation(styled, rng, scene_index=i - 1)
            filename = unique_jpg_name(out_dir, small)
            path = out_dir / filename
            styled.convert("RGB").save(path, "JPEG", quality=90, optimize=False, subsampling=2)
            results.append(
                {
                    "ok": True,
                    "index": i,
                    "big": big,
                    "small": small,
                    "file": filename,
                    "source_row": row.get("row"),
                    "angle_dir": crop_meta["angle_dir"],
                    "angle_deg": crop_meta["angle_deg"],
                    "zoom": crop_meta["zoom"],
                    "shade": shade,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "ok": False,
                    "index": i,
                    "error": str(exc),
                    "source_row": row.get("row"),
                    "big_raw": row.get("big"),
                    "small_raw": row.get("small"),
                }
            )

    summary = {
        "total": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "results": results,
    }
    (out_dir / "manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
