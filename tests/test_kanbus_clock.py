"""Unit tests for demos/kanbus_clock.py helper logic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def _load_demo_module():
    path = Path(__file__).resolve().parents[1] / "demos" / "kanbus_clock.py"
    demos_dir = str(path.parent)
    if demos_dir not in sys.path:
        sys.path.insert(0, demos_dir)
    spec = importlib.util.spec_from_file_location("kanbus_clock_demo", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_event(path: Path, *, event_type: str, issue_id: str, occurred_at: str, payload: dict):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": f"evt-{path.stem}",
                "issue_id": issue_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
                "actor_id": "tester",
                "payload": payload,
            }
        ),
        encoding="utf-8",
    )


def test_discover_event_dirs_recursive(tmp_path: Path):
    module = _load_demo_module()

    (tmp_path / "project" / "events").mkdir(parents=True)
    (tmp_path / "a" / "b" / "project" / "events").mkdir(parents=True)
    (tmp_path / "x" / "project" / "event").mkdir(parents=True)

    found = module.discover_event_dirs(tmp_path)
    expected = sorted(
        [
            (tmp_path / "project" / "events").resolve(),
            (tmp_path / "a" / "b" / "project" / "events").resolve(),
        ]
    )
    assert found == expected


def test_latest_event_timestamp_prefers_json_occurred_at(tmp_path: Path):
    module = _load_demo_module()
    events_dir = tmp_path / "project" / "events"
    events_dir.mkdir(parents=True)

    _write_event(
        events_dir / "2026-03-04T00:00:00.000Z__old.json",
        event_type="issue_created",
        issue_id="kanbus-aaaaaa-1",
        occurred_at="2026-03-04T01:00:00.000Z",
        payload={"title": "old", "status": "open", "issue_type": "task"},
    )
    _write_event(
        events_dir / "2026-03-04T00:00:01.000Z__new.json",
        event_type="issue_created",
        issue_id="kanbus-bbbbbb-1",
        occurred_at="2026-03-04T02:30:00.000Z",
        payload={"title": "new", "status": "open", "issue_type": "task"},
    )

    count, latest = module.latest_event_timestamp(events_dir)
    assert count == 2
    assert latest == "2026-03-04T02:30:00Z"


def test_latest_event_timestamp_falls_back_to_filename_on_invalid_json(tmp_path: Path):
    module = _load_demo_module()
    events_dir = tmp_path / "project" / "events"
    events_dir.mkdir(parents=True)

    bad = events_dir / "2026-03-04T03:21:22.123Z__bad.json"
    bad.write_text("{not-json", encoding="utf-8")

    count, latest = module.latest_event_timestamp(events_dir)
    assert count == 1
    assert latest == "2026-03-04T03:21:22.123000Z"


def test_load_kanbus_event_derives_repo_root(tmp_path: Path):
    module = _load_demo_module()
    event_path = tmp_path / "demo" / "project" / "events" / "event.json"
    event_path.parent.mkdir(parents=True)
    _write_event(
        event_path,
        event_type="comment_added",
        issue_id="kanbus-demo-1",
        occurred_at="2026-03-04T00:00:00.000Z",
        payload={"comment_author": "tester"},
    )

    event = module.load_kanbus_event(event_path)
    assert event.repo_root == (tmp_path / "demo").resolve()


def test_summarize_event_known_types():
    module = _load_demo_module()

    created = module.KanbusEvent(
        path=Path("x.json"),
        schema_version=1,
        event_id="e1",
        issue_id="kanbus-abcdef12-1111",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={"issue_type": "task", "status": "open", "title": "Create watcher"},
    )
    notice = module.summarize_event(created)
    assert notice.header == "CREATED"
    assert "KBS ABCDEF" in notice.message
    assert "TASK OPEN" in notice.message
    assert notice.header_font == "bytesized"
    assert notice.header_tight_padding is True
    assert notice.center_first_line is True

    transition = module.KanbusEvent(
        path=Path("y.json"),
        schema_version=1,
        event_id="e2",
        issue_id="kanbus-bbeeff12-1111",
        event_type="state_transition",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={"from_status": "open", "to_status": "closed"},
    )
    transition_notice = module.summarize_event(transition)
    assert transition_notice.header == "TRANSITION"
    assert "\nFROM\nOPEN\nTO\nCLOSED" in transition_notice.message
    assert transition_notice.center_first_line is True

    comment = module.KanbusEvent(
        path=Path("z.json"),
        schema_version=1,
        event_id="e3",
        issue_id="kanbus-11223344-1111",
        event_type="comment_added",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={
            "comment_author": "ryan.porter",
            "comment": "Deploy failed in staging and needs rollback now",
        },
    )
    comment_notice = module.summarize_event(comment)
    assert comment_notice.header == "COMMENT"
    assert "KBS 112233" in comment_notice.message
    assert "Deploy failed" in comment_notice.message
    assert "staging" in comment_notice.message
    assert comment_notice.body_font == "bytesized"
    assert comment_notice.body_align == "left"
    assert comment_notice.body_center_vertical is False
    assert comment_notice.body_line_vpad == 1
    assert comment_notice.center_first_line is True
    assert comment_notice.first_line_darker_steps == 2
    assert comment_notice.header_font == "bytesized"
    assert comment_notice.header_tight_padding is True
    assert comment_notice.body_max_lines == 7


def test_scan_folder_for_new_events_ignores_baseline_and_picks_new(tmp_path: Path):
    module = _load_demo_module()
    events_dir = tmp_path / "project" / "events"
    events_dir.mkdir(parents=True)

    baseline_file = events_dir / "2026-03-04T00:00:00.000Z__baseline.json"
    _write_event(
        baseline_file,
        event_type="issue_created",
        issue_id="kanbus-base-1",
        occurred_at="2026-03-04T00:00:00.000Z",
        payload={"title": "base", "status": "open", "issue_type": "task"},
    )

    known = {baseline_file.name}
    failures: dict[Path, int] = {}
    events = module.scan_folder_for_new_events(events_dir, known, failures)
    assert events == []

    new_file = events_dir / "2026-03-04T00:00:01.000Z__new.json"
    _write_event(
        new_file,
        event_type="comment_added",
        issue_id="kanbus-new-1",
        occurred_at="2026-03-04T00:00:01.000Z",
        payload={"comment_author": "a"},
    )
    events = module.scan_folder_for_new_events(events_dir, known, failures)
    assert len(events) == 1
    assert events[0].path == new_file
    assert new_file.name in known


def test_merge_new_event_dirs_adds_dirs_after_startup(tmp_path: Path):
    module = _load_demo_module()

    first = tmp_path / "one" / "project" / "events"
    first.mkdir(parents=True)
    tracked: dict[Path, set[str]] = {first.resolve(): set()}

    second = tmp_path / "two" / "project" / "events"
    second.mkdir(parents=True)

    added = module.merge_new_event_dirs(tmp_path, tracked)
    assert second.resolve() in added
    assert second.resolve() in tracked


def test_short_seconds_normalization():
    module = _load_demo_module()
    tokens = module._normalize_command_tokens(["-s5", "--color", "red-10", "hello"])
    assert tokens == ["--seconds", "5", "--color", "red-10", "hello"]


def test_enqueue_message_transition_adds_two_items():
    module = _load_demo_module()

    class _DummyClockScene:
        name = "clock"

    class _DummyPlayer:
        def __init__(self):
            self.items = []

        @property
        def queue_depth(self):
            return len(self.items)

        async def enqueue(self, item):
            self.items.append(item)

    async def _run():
        player = _DummyPlayer()
        await module._enqueue_message_transition(
            player=player,
            clock_scene=_DummyClockScene(),
            level="info",
            message="HELLO",
            seconds=5.0,
            transition_ms=1200,
            fg=(100, 100, 100),
            bg=(10, 10, 10),
        )
        return player.items

    items = __import__("asyncio").run(_run())
    assert len(items) == 2
    assert items[0].transition.kind == "push_left"
    assert items[1].transition.kind == "push_right"
    assert items[0].hold_ms == 5000
    assert items[1].hold_ms == 0


def test_enqueue_message_transition_respects_body_font():
    module = _load_demo_module()

    class _DummyClockScene:
        name = "clock"

    class _DummyPlayer:
        def __init__(self):
            self.items = []

        @property
        def queue_depth(self):
            return len(self.items)

        async def enqueue(self, item):
            self.items.append(item)

    async def _run():
        player = _DummyPlayer()
        await module._enqueue_message_transition(
            player=player,
            clock_scene=_DummyClockScene(),
            level="info",
            message="A\nB\nC\nD\nE\nF\nG",
            seconds=5.0,
            transition_ms=1200,
            fg=(100, 100, 100),
            bg=(10, 10, 10),
            header_title="COMMENT",
            header_font="bytesized",
            header_tight_padding=True,
            body_font="bytesized",
            body_align="left",
            body_center_vertical=False,
            body_line_vpad=1,
            center_first_line=True,
            first_line_darker_steps=2,
            body_max_lines=7,
            body_min_row_height=6,
            body_max_row_height=8,
        )
        return player.items[0].scene.layout.rows

    rows = __import__("asyncio").run(_run())
    header_row = rows[0]
    expected_header_h = module.measure_scene_text("COMMENT", "bytesized")[1] + 3
    assert header_row.style.font == "bytesized"
    assert header_row.height == expected_header_h

    rows = rows[1:]
    text_rows = [r for r in rows if getattr(r, "content", None) not in ("", None)]
    assert text_rows
    assert all(r.style.font == "bytesized" for r in text_rows)
    assert text_rows[0].align == "center"
    assert all(r.align == "left" for r in text_rows[1:])
    if len(text_rows) >= 2:
        first = text_rows[0].style.color
        second = text_rows[1].style.color
        assert first != second
        assert all(a < b for a, b in zip(first, second))


def test_setup_readline_history_permission_error_is_non_fatal(tmp_path: Path, monkeypatch):
    module = _load_demo_module()
    calls: list[str] = []

    fake_readline = SimpleNamespace(
        read_history_file=lambda _path: (_ for _ in ()).throw(PermissionError("denied")),
        set_history_length=lambda _n: calls.append("set_len"),
        write_history_file=lambda _path: calls.append("write"),
    )
    monkeypatch.setattr(module, "readline", fake_readline)

    module._setup_readline_history(tmp_path / "history")
    assert calls == []


def test_extract_comment_text_from_nested_payload():
    module = _load_demo_module()
    payload = {
        "comment_author": "ryan.porter",
        "meta": {"id": "123", "status": "open"},
        "comment_data": {"body": "This is the real comment body we should display"},
    }
    text = module._extract_comment_text(payload)
    assert text == "This is the real comment body we should display"


def test_wrap_text_lines_respects_pixel_width(monkeypatch):
    module = _load_demo_module()
    monkeypatch.setattr(module, "measure_scene_text", lambda text, _font: (len(text) * 5, 7))

    lines = module._wrap_text_lines(
        "alpha beta gamma delta epsilon",
        max_width_px=20,
        max_lines=4,
        font_key="tiny5",
    )
    assert lines
    assert all((len(line) * 5) <= 20 for line in lines)


def test_comment_summary_falls_back_to_kbs_show_when_payload_missing(monkeypatch):
    module = _load_demo_module()
    captured: dict[str, object] = {}

    fake_issue_json = json.dumps(
        {
            "comments": [
                {"text": "older"},
                {"text": "Newest comment from kbs show"},
            ]
        }
    )

    def _fake_run(*_args, **_kwargs):
        captured.update(_kwargs)
        return SimpleNamespace(returncode=0, stdout=fake_issue_json)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    event = module.KanbusEvent(
        path=Path("/tmp/demo-repo/project/events/event.json"),
        schema_version=1,
        event_id="e4",
        issue_id="kanbus-aaaaaa-0001",
        event_type="comment_added",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={"comment_author": "tester"},
    )
    notice = module.summarize_event(event)
    assert notice.header == "COMMENT"
    assert "KBS AAAAAA" in notice.message
    assert "Newest" in notice.message
    assert "comment" in notice.message
    assert captured.get("cwd") == str(Path("/tmp/demo-repo").resolve())
