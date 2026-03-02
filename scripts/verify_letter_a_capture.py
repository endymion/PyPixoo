#!/usr/bin/env python3
"""Verify letter A debug captures are top-left aligned and pixel-accurate."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

from PIL import Image


ExpectedBBox = Tuple[int, int, int, int]


EXPECTED_BBOXES: Dict[str, ExpectedBBox] = {
    "letter_a_fullres.png": (0, 0, 11, 14),       # 12x15
    "letter_a_rendered_pre.png": (0, 0, 3, 4),    # 4x5
    "letter_a_rendered.png": (0, 0, 3, 4),        # 4x5
}


def _bbox_non_black(img: Image.Image) -> ExpectedBBox:
    pix = img.load()
    xs = []
    ys = []
    for y in range(img.height):
        for x in range(img.width):
            if any(pix[x, y]):
                xs.append(x)
                ys.append(y)
    if not xs:
        raise AssertionError("Image has no lit pixels")
    return (min(xs), min(ys), max(xs), max(ys))


def _channel_intensities(img: Image.Image) -> set[int]:
    return {value for px in img.getdata() for value in px}


def _verify_image(path: Path, expected_bbox: ExpectedBBox) -> None:
    if not path.exists():
        raise AssertionError(f"Missing file: {path}")
    img = Image.open(path).convert("RGB")
    bbox = _bbox_non_black(img)
    if bbox != expected_bbox:
        raise AssertionError(
            f"{path.name} bbox mismatch: expected {expected_bbox}, got {bbox}"
        )

    intensities = _channel_intensities(img)
    if intensities != {0, 255}:
        raise AssertionError(
            f"{path.name} intensity mismatch: expected {{0, 255}}, got {sorted(intensities)}"
        )

    w = bbox[2] - bbox[0] + 1
    h = bbox[3] - bbox[1] + 1
    print(f"PASS {path.name}: bbox={bbox} size={w}x{h} intensities={[0, 255]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify letter A capture fixtures against exact bbox/intensity expectations."
    )
    parser.add_argument(
        "--fixtures-dir",
        default="demos/fixtures",
        help="Path to fixture directory (default: demos/fixtures)",
    )
    args = parser.parse_args()

    fixtures_dir = Path(args.fixtures_dir)
    for filename, expected in EXPECTED_BBOXES.items():
        _verify_image(fixtures_dir / filename, expected)
    print("All letter A capture checks passed.")


if __name__ == "__main__":
    main()
