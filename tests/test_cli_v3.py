"""Tests for v3 raster/scene CLI commands."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from pypixoo.cli import cmd_scene_run, main


def test_raster_push_subcommand_routes():
    with patch("pypixoo.cli.cmd_raster_push") as mock_cmd, patch(
        "sys.argv",
        ["pixoo", "raster", "push", "--color", "dark.amber10"],
    ):
        main()
    mock_cmd.assert_called_once()


def test_raster_stream_subcommand_routes():
    with patch("pypixoo.cli.cmd_raster_stream") as mock_cmd, patch(
        "sys.argv",
        [
            "pixoo",
            "raster",
            "stream",
            "--fps",
            "3",
            "--duration",
            "2",
            "--primary-color",
            "black",
            "--secondary-color",
            "dark.gray8",
        ],
    ):
        main()
    mock_cmd.assert_called_once()


def test_scene_run_subcommand_routes():
    with patch("pypixoo.cli.cmd_scene_run") as mock_cmd, patch(
        "sys.argv",
        [
            "pixoo",
            "scene",
            "run",
            "--scene",
            "info",
            "--duration",
            "1",
            "--info-title",
            "STATUS",
            "--info-font",
            "tiny5",
            "--info-header-height",
            "14",
            "--no-info-header-border",
            "--info-header-border-thickness",
            "2",
            "--info-header-border-color",
            "dark.gray8",
        ],
    ):
        main()
    mock_cmd.assert_called_once()


def test_scene_run_subcommand_routes_with_info_layout_json():
    with patch("pypixoo.cli.cmd_scene_run") as mock_cmd, patch(
        "sys.argv",
        [
            "pixoo",
            "scene",
            "run",
            "--scene",
            "info",
            "--duration",
            "1",
            "--info-layout-json",
            '{"rows":[{"kind":"text","content":"HELLO"}]}',
        ],
    ):
        main()
    mock_cmd.assert_called_once()


def test_scene_enqueue_subcommand_routes():
    with patch("pypixoo.cli.cmd_scene_enqueue") as mock_cmd, patch(
        "sys.argv",
        [
            "pixoo",
            "scene",
            "enqueue",
            "--from-scene",
            "clock",
            "--to-scene",
            "info",
            "--transition",
            "push_left",
            "--duration-ms",
            "500",
        ],
    ):
        main()
    mock_cmd.assert_called_once()


def test_scene_demo_subcommand_routes():
    with patch("pypixoo.cli.cmd_scene_demo") as mock_cmd, patch(
        "sys.argv",
        ["pixoo", "scene", "demo", "--all-transitions"],
    ):
        main()
    mock_cmd.assert_called_once()


def test_scene_subcommands_reject_invalid_info_font():
    with patch("sys.argv", ["pixoo", "scene", "run", "--info-font", "does_not_exist"]):
        try:
            main()
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("expected parser failure for invalid scene font")


def test_scene_run_exits_cleanly_on_invalid_info_layout_json():
    dummy_pixoo = SimpleNamespace(close=lambda: None)
    with patch("pypixoo.cli._connect", return_value=dummy_pixoo), patch(
        "pypixoo.cli.PixooFrameSink"
    ), patch("pypixoo.cli.AsyncRasterClient"), patch("pypixoo.cli.ScenePlayer"), patch(
        "pypixoo.cli._build_scene", side_effect=ValueError("bad layout json")
    ):
        try:
            cmd_scene_run(
                ip="127.0.0.1",
                scene_name="info",
                fps=1,
                duration_s=1,
                accent_color="black",
                info_title="INFO",
                info_font="tiny5",
                info_header_height=12,
                info_header_border=True,
                info_header_border_thickness=1,
                info_header_border_color="black",
                info_layout_json='{"rows":',
            )
        except SystemExit as exc:
            assert exc.code == 1
        else:
            raise AssertionError("expected SystemExit(1)")
