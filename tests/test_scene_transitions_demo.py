"""Tests for demos/scene_transitions.py helper behavior."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_demo_module():
    path = Path(__file__).resolve().parents[1] / "demos" / "scene_transitions.py"
    demos_dir = str(path.parent)
    if demos_dir not in sys.path:
        sys.path.insert(0, demos_dir)
    spec = importlib.util.spec_from_file_location("scene_transitions_demo", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parser_defaults_to_pingpong_mode():
    module = _load_demo_module()
    parser = module.build_parser()
    args = parser.parse_args([])
    assert args.mode == "pingpong"
    assert args.switch_seconds == 5.0
    assert args.run_seconds == 0.0
    assert args.info_title == "INFO"
    assert args.info_header_height == 12
    assert args.info_header_border is True


def test_parser_rejects_unsupported_info_font():
    module = _load_demo_module()
    parser = module.build_parser()
    try:
        parser.parse_args(["--info-font", "not_a_font"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse to reject unsupported font")


def test_derived_hold_ms_targets_switch_period():
    module = _load_demo_module()
    assert module._derived_hold_ms(switch_seconds=5.0, duration_ms=700) == 4300
    assert module._derived_hold_ms(switch_seconds=1.0, duration_ms=1200) == 0


def test_parser_accepts_info_layout_json():
    module = _load_demo_module()
    parser = module.build_parser()
    args = parser.parse_args(["--info-layout-json", '{"rows":[{"kind":"text","content":"X"}]}'])
    assert args.info_layout_json == '{"rows":[{"kind":"text","content":"X"}]}'
