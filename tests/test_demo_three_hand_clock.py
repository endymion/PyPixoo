"""Unit tests for demos/demo_three_hand_clock.py helper logic."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
import requests
from pypixoo.buffer import Buffer


def _load_demo_module():
    path = Path(__file__).resolve().parents[1] / "demos" / "demo_three_hand_clock.py"
    spec = importlib.util.spec_from_file_location("demo_three_hand_clock", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


clock_demo = _load_demo_module()


def test_angles_for_hms_known_points():
    h, m, s = clock_demo.angles_for_hms(12, 0, 0.0)
    assert h == pytest.approx(-math.pi / 2.0)
    assert m == pytest.approx(-math.pi / 2.0)
    assert s == pytest.approx(-math.pi / 2.0)

    h2, m2, s2 = clock_demo.angles_for_hms(3, 15, 30.0)
    assert s2 == pytest.approx(math.pi / 2.0)
    assert m2 == pytest.approx(((15.5 / 60.0) * 2.0 * math.pi) - (math.pi / 2.0))
    assert h2 == pytest.approx((((3 + (15.5 / 60.0)) / 12.0) * 2.0 * math.pi) - (math.pi / 2.0))

    h3, m3, s3 = clock_demo.angles_for_hms(6, 30, 45.0)
    assert h3 == pytest.approx((((6 + (30.75 / 60.0)) / 12.0) * 2.0 * math.pi) - (math.pi / 2.0))
    assert m3 == pytest.approx(((30.75 / 60.0) * 2.0 * math.pi) - (math.pi / 2.0))
    assert s3 == pytest.approx(((45.0 / 60.0) * 2.0 * math.pi) - (math.pi / 2.0))


def test_build_segment_sequence_respects_max_frames():
    style = clock_demo.ClockStyle(
        dial_color=(0, 0, 0),
        marker_color=(100, 0, 100),
        top_marker_color=(255, 0, 255),
        hour_hand_color=(200, 200, 200),
        minute_hand_color=(180, 180, 220),
        second_hand_color=(255, 0, 0),
        center_color=(255, 255, 255),
        hour_length=16,
        minute_length=23,
        second_length=28,
        marker_inner_radius=26,
        marker_outer_radius=30,
        marker_thickness=1,
        top_marker_thickness=2,
        hour_thickness=2,
        minute_thickness=2,
        second_thickness=1,
        center_radius=1,
    )
    sequence = clock_demo.build_segment_sequence(
        segment_start=0.0,
        segment_seconds=12.0,
        fps=10,
        max_frames=88,
        style=style,
    )
    assert len(sequence.frames) <= 88
    assert sequence.speed_ms >= 20


def test_aligned_segment_start_rounds_up():
    assert clock_demo.aligned_segment_start(25.1, 12.0) == pytest.approx(36.0)
    assert clock_demo.aligned_segment_start(24.0, 12.0) == pytest.approx(24.0)


def test_upload_sequence_resilient_falls_back_to_frame_by_frame():
    pixoo = MagicMock()
    frame = MagicMock()
    sequence = MagicMock()
    sequence.frames = [frame] * 20
    sequence.speed_ms = 200

    calls = []

    def _upload_side_effect(seq, *, mode, chunk_size):
        calls.append(mode.value if hasattr(mode, "value") else str(mode))
        if len(calls) == 1:
            raise RuntimeError("Command failed (Draw/CommandList): {'error_code': 'Request data illegal json'}")
        return 1

    pixoo.upload_sequence.side_effect = _upload_side_effect
    mode_used, retries, frame_count = clock_demo.upload_sequence_resilient(
        pixoo,
        sequence,
        upload_mode=clock_demo.UploadMode.COMMAND_LIST,
        chunk_size=8,
    )
    assert calls[0] == "command_list"
    assert calls[1] == "frame_by_frame"
    assert mode_used == clock_demo.UploadMode.FRAME_BY_FRAME
    assert retries >= 1
    assert frame_count > 0


def test_upload_sequence_resilient_downsamples_on_timeout_in_frame_mode():
    pixoo = MagicMock()
    frame = clock_demo.GifFrame(image=Buffer.from_flat_list([0, 0, 0] * (64 * 64)), duration_ms=200)
    sequence = clock_demo.GifSequence(frames=[frame] * 40, speed_ms=200)

    call_lengths = []

    def _upload_side_effect(seq, *, mode, chunk_size):
        call_lengths.append(len(seq.frames))
        if len(call_lengths) == 1:
            raise requests.exceptions.ReadTimeout("timed out")
        return 1

    pixoo.upload_sequence.side_effect = _upload_side_effect
    mode_used, retries, frame_count = clock_demo.upload_sequence_resilient(
        pixoo,
        sequence,
        upload_mode=clock_demo.UploadMode.FRAME_BY_FRAME,
        chunk_size=1,
    )
    assert call_lengths[0] == 40
    assert call_lengths[1] < 40
    assert mode_used == clock_demo.UploadMode.FRAME_BY_FRAME
    assert retries >= 1
    assert frame_count == call_lengths[1]


def test_parser_rejects_invalid_numeric_values():
    parser = clock_demo.build_parser(ip_default="192.168.0.37")
    args = parser.parse_args([])
    assert args.delivery == "push"
    with pytest.raises(SystemExit):
        parser.parse_args(["--fps", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--segment-seconds", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--max-frames", "0"])


def test_parser_accepts_radix_color_tokens():
    parser = clock_demo.build_parser(ip_default="192.168.0.37")
    args = parser.parse_args(
        [
            "--hour-hand-color",
            "gray11",
            "--minute-hand-color",
            "dark.gray11",
            "--second-hand-color",
            "grayDark11",
        ]
    )
    assert args.hour_hand_color == clock_demo.parse_color("gray11")
    assert args.minute_hand_color == clock_demo.parse_color("dark.gray11")
    assert args.second_hand_color == clock_demo.parse_color("grayDark11")
