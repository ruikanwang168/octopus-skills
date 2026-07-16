#!/usr/bin/env python3
"""Compare incremental or reconstruction screenshots outside declared masks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth(a: int, b: int, c: int) -> int:
    estimate = a + b - c
    pa = abs(estimate - a)
    pb = abs(estimate - b)
    pc = abs(estimate - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG file")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, interlace = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            break
    if not width or not height or bit_depth != 8 or interlace != 0:
        raise ValueError(f"{path} must be a non-interlaced 8-bit PNG")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if not channels:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}")
    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise ValueError(f"{path} has unexpected decoded length")
    output = bytearray(height * stride)
    previous = bytearray(stride)
    source = 0
    for row in range(height):
        filter_type = raw[source]
        source += 1
        scanline = bytearray(raw[source : source + stride])
        source += stride
        for index in range(stride):
            left = scanline[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_type == 2:
                scanline[index] = (scanline[index] + up) & 0xFF
            elif filter_type == 3:
                scanline[index] = (scanline[index] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[index] = (scanline[index] + paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"{path} uses unsupported PNG filter {filter_type}")
        start = row * stride
        output[start : start + stride] = scanline
        previous = scanline
    return width, height, channels, bytes(output)


def normalized_masks(value: object, viewport: str) -> list[dict[str, object]]:
    if not isinstance(value, dict):
        return []
    rows = value.get(viewport, [])
    if not isinstance(rows, list):
        raise ValueError(f"masks.{viewport} must be a list")
    masks: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"masks.{viewport} entries must be objects")
        mask = {
            "label": str(row.get("label") or "declared-change"),
            "x": int(row.get("x", 0)),
            "y": int(row.get("y", 0)),
            "width": int(row.get("width", 0)),
            "height": int(row.get("height", 0)),
        }
        if mask["width"] <= 0 or mask["height"] <= 0:
            raise ValueError(f"masks.{viewport} entries require positive width and height")
        masks.append(mask)
    return masks


def masked(x: int, y: int, masks: list[dict[str, object]]) -> bool:
    return any(
        int(mask["x"]) <= x < int(mask["x"]) + int(mask["width"])
        and int(mask["y"]) <= y < int(mask["y"]) + int(mask["height"])
        for mask in masks
    )


def compare(
    baseline_path: Path,
    current_path: Path,
    masks: list[dict[str, object]],
    pixel_delta: int,
) -> dict[str, object]:
    base_width, base_height, base_channels, baseline = read_png(baseline_path)
    width, height, channels, current = read_png(current_path)
    if (base_width, base_height, base_channels) != (width, height, channels):
        raise ValueError(
            f"screenshot dimensions/channels differ: baseline={base_width}x{base_height}x{base_channels}, "
            f"current={width}x{height}x{channels}"
        )
    compared = changed = masked_pixels = max_channel_delta = 0
    for y in range(height):
        for x in range(width):
            if masked(x, y, masks):
                masked_pixels += 1
                continue
            compared += 1
            start = (y * width + x) * channels
            delta = max(abs(baseline[start + channel] - current[start + channel]) for channel in range(channels))
            max_channel_delta = max(max_channel_delta, delta)
            if delta > pixel_delta:
                changed += 1
    if compared == 0:
        raise ValueError("change masks cover the entire screenshot; unchanged regions cannot be verified")
    return {
        "width": width,
        "height": height,
        "channels": channels,
        "comparedPixels": compared,
        "maskedPixels": masked_pixels,
        "changedPixels": changed,
        "diffRatio": changed / compared,
        "maxChannelDelta": max_channel_delta,
        "pixelDeltaThreshold": pixel_delta,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("incremental", "reconstruction"), default="incremental")
    parser.add_argument("--viewport", action="append", default=[], help="Repeatable id,baseline.png,current.png comparison")
    parser.add_argument("--baseline-desktop")
    parser.add_argument("--current-desktop")
    parser.add_argument("--baseline-mobile")
    parser.add_argument("--current-mobile")
    parser.add_argument("--masks", help="Optional JSON with changeMasks and/or unstableMasks")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-diff-ratio", type=float)
    parser.add_argument("--pixel-delta", type=int)
    parser.add_argument("--max-mask-ratio", type=float)
    parser.add_argument("--allow-large-mask-reason")
    args = parser.parse_args()
    comparisons: dict[str, tuple[Path, Path]] = {}
    for value in args.viewport:
        parts = value.split(",", 2)
        if len(parts) != 3 or not all(parts):
            raise SystemExit("--viewport format is id,baseline.png,current.png")
        viewport_id, baseline, current = parts
        comparisons[viewport_id] = (Path(baseline), Path(current))
    legacy = {
        "desktop": (args.baseline_desktop, args.current_desktop),
        "mobile": (args.baseline_mobile, args.current_mobile),
    }
    if not comparisons and any(all(pair) for pair in legacy.values()):
        print("WARN legacy desktop/mobile arguments are deprecated; prefer repeatable --viewport id,baseline,current")
        comparisons = {name: (Path(pair[0]), Path(pair[1])) for name, pair in legacy.items() if all(pair)}
    if not comparisons:
        raise SystemExit("at least one --viewport id,baseline.png,current.png is required")
    masks_data = json.loads(Path(args.masks).read_text(encoding="utf-8")) if args.masks else {}
    if "changeMasks" in masks_data or "unstableMasks" in masks_data:
        change_data = masks_data.get("changeMasks", {})
        unstable_data = masks_data.get("unstableMasks", {})
    else:
        change_data = masks_data
        unstable_data = {}
    viewport_ids = list(comparisons)
    if args.mode == "reconstruction" and any(normalized_masks(change_data, viewport) for viewport in viewport_ids):
        raise SystemExit("reconstruction mode accepts unstableMasks only; intended change masks belong to incremental mode")
    pixel_delta = args.pixel_delta if args.pixel_delta is not None else (8 if args.mode == "incremental" else 16)
    max_diff_ratio = args.max_diff_ratio if args.max_diff_ratio is not None else (0.001 if args.mode == "incremental" else 0.02)
    max_mask_ratio = args.max_mask_ratio if args.max_mask_ratio is not None else (0.35 if args.mode == "incremental" else 0.10)
    masks_by_viewport = {
        viewport: normalized_masks(change_data, viewport) + normalized_masks(unstable_data, viewport)
        for viewport in viewport_ids
    }
    metrics_by_viewport = {
        viewport: compare(baseline, current, masks_by_viewport[viewport], pixel_delta)
        for viewport, (baseline, current) in comparisons.items()
    }
    excessive_masks = []
    for viewport, metrics in metrics_by_viewport.items():
        total = int(metrics["comparedPixels"]) + int(metrics["maskedPixels"])
        metrics["maskRatio"] = int(metrics["maskedPixels"]) / total
        if metrics["maskRatio"] > max_mask_ratio:
            excessive_masks.append(viewport)
    if excessive_masks and not args.allow_large_mask_reason:
        raise SystemExit(
            f"mask coverage exceeds {max_mask_ratio:.0%} for {', '.join(excessive_masks)}; "
            "reduce masks or provide --allow-large-mask-reason"
        )
    unchanged_match = all(metrics["diffRatio"] <= max_diff_ratio for metrics in metrics_by_viewport.values())
    report = {
        "version": 2,
        "generator": "compare-prototype-screenshots.py",
        "mode": args.mode,
        "method": f"pixel-diff-{args.mode}-outside-declared-masks",
        "reviewedViewports": viewport_ids,
        "maxDiffRatio": max_diff_ratio,
        "maxMaskRatio": max_mask_ratio,
        "largeMaskWaiverReason": args.allow_large_mask_reason or "",
        "changeRegions": sorted({str(mask["label"]) for viewport in viewport_ids for mask in normalized_masks(change_data, viewport)}),
        "unstableRegions": sorted({str(mask["label"]) for viewport in viewport_ids for mask in normalized_masks(unstable_data, viewport)}),
        "changedRegions": sorted({str(mask["label"]) for masks in masks_by_viewport.values() for mask in masks}),
        "unchangedRegionsMatch": unchanged_match,
        "viewports": metrics_by_viewport,
    }
    report.update(metrics_by_viewport)  # legacy readers can still access report.desktop/report.mobile.
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = ", ".join(f"{name}={metrics['diffRatio']:.6f}" for name, metrics in metrics_by_viewport.items())
    print(f"Visual diff {'passed' if unchanged_match else 'failed'}: {summary}")
    return 0 if unchanged_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
