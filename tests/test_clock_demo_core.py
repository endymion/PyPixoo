"""Tests for shared clock demo mode guardrails and routing."""

from __future__ import annotations

import argparse
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pypixoo import _clock_demo as clock_demo


def _parser() -> argparse.ArgumentParser:
    return clock_demo.build_clock_parser(
        description="clock-test",
        ip_default="192.168.0.37",
        default_mode=clock_demo.MODE_NATIVE,
        default_fps=2,
        default_loop_seconds=2.0,
    )


def test_guardrail_blocks_web_options_in_native_mode():
    parser = _parser()
    args = parser.parse_args(["--mode", "native_clock", "--fps", "5"])
    with pytest.raises(ValueError, match="does not allow web-render options"):
        clock_demo.enforce_mode_guardrails(args, parser)


def test_guardrail_blocks_native_options_in_web_mode():
    parser = _parser()
    args = parser.parse_args(["--mode", "web_clock_experimental", "--clock-id", "2"])
    with pytest.raises(ValueError, match="does not allow native-only options"):
        clock_demo.enforce_mode_guardrails(args, parser)


def test_guardrail_allows_defaults_for_native_mode():
    parser = _parser()
    args = parser.parse_args(["--mode", "native_clock"])
    clock_demo.enforce_mode_guardrails(args, parser)


def test_run_native_mode_routes_expected_commands(monkeypatch, capsys):
    fake_pixoo = MagicMock()
    fake_pixoo.get_clock_info.return_value = {"ClockId": 1}
    args = SimpleNamespace(
        sync_utc=True,
        twenty_four_hour=True,
        channel_index=3,
        clock_id=1,
        poll_seconds=0.1,
    )

    def _stop(_):
        raise KeyboardInterrupt()

    monkeypatch.setattr(clock_demo.time, "sleep", _stop)
    with pytest.raises(KeyboardInterrupt):
        clock_demo._run_native_clock_mode(fake_pixoo, args)

    fake_pixoo.set_utc_time.assert_called()
    fake_pixoo.set_time_24_flag.assert_called_once_with(1)
    fake_pixoo.set_channel_index.assert_called_once_with(3)
    fake_pixoo.set_clock_select_id.assert_called_once_with(1)
    fake_pixoo.get_clock_info.assert_called_once()
    out = capsys.readouterr().out
    assert "mode=native_clock capability=device_native_clock" in out


def test_run_native_mode_preserves_current_clock_when_id_not_provided(monkeypatch):
    fake_pixoo = MagicMock()
    fake_pixoo.get_clock_info.return_value = {"ClockId": 846}
    args = SimpleNamespace(
        sync_utc=False,
        twenty_four_hour=None,
        channel_index=None,
        clock_id=None,
        poll_seconds=0.1,
    )

    def _stop(_):
        raise KeyboardInterrupt()

    monkeypatch.setattr(clock_demo.time, "sleep", _stop)
    with pytest.raises(KeyboardInterrupt):
        clock_demo._run_native_clock_mode(fake_pixoo, args)

    fake_pixoo.set_clock_select_id.assert_not_called()
    fake_pixoo.get_clock_info.assert_called_once()


def test_run_clock_demo_web_mode_prints_experimental_banner(monkeypatch, capsys):
    parser = _parser()
    args = parser.parse_args(
        [
            "--mode",
            "web_clock_experimental",
            "--delivery",
            "push",
        ]
    )

    fake_pixoo = MagicMock()
    monkeypatch.setattr(clock_demo, "Pixoo", lambda ip: fake_pixoo)
    monkeypatch.setattr(clock_demo, "_wait_for_connection", lambda pixoo, delay: None)

    def _stop(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(clock_demo, "_run_web_push_mode", _stop)
    clock_demo.run_clock_demo(args, parser)
    out = capsys.readouterr().out
    assert "EXPERIMENTAL: smoothness/time fidelity not guaranteed." in out
    assert "mode selected: web_clock_experimental" in out
