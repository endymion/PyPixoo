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


def _scene_header_text(scene) -> str:
    row = scene.layout.rows[0]
    cells = getattr(row, "cells", None)
    if isinstance(cells, list):
        parts = [str(getattr(cell, "value", "")).strip() for cell in cells]
        return " ".join(part for part in parts if part)
    content = getattr(row, "content", "")
    if isinstance(content, list):
        return "".join(
            str(getattr(span, "text", "") or "")
            for span in content
            if getattr(span, "text", "")
        )
    return str(content)


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

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        fixtures = {
            "kanbus-abcdef12-1111": {
                "id": "kanbus-abcdef12-1111",
                "type": "task",
                "status": "open",
                "description": "Created issue description line one line two",
                "parent": "kanbus-parent-1",
                "comments": [],
            },
            "kanbus-parent-1": {
                "id": "kanbus-parent-1",
                "type": "epic",
                "status": "open",
                "description": "Parent description for top section",
                "comments": [],
            },
            "kanbus-bbeeff12-1111": {
                "id": "kanbus-bbeeff12-1111",
                "type": "bug",
                "status": "in_progress",
                "description": "Transition issue description block",
                "comments": [],
            },
            "kanbus-11223344-1111": {
                "id": "kanbus-11223344-1111",
                "type": "task",
                "status": "open",
                "description": "Issue description for comment card",
                "comments": [{"text": "Latest fallback comment"}],
            },
            "kanbus-abc12345-2222": {
                "id": "kanbus-abc12345-2222",
                "type": "task",
                "status": "open",
                "description": "",
                "title": "Missing status title",
                "comments": [],
            },
        }
        payload = fixtures.get(issue_id, {"id": issue_id, "type": "issue", "status": "open", "description": ""})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    created = module.KanbusEvent(
        path=Path("x.json"),
        schema_version=1,
        event_id="e1",
        issue_id="kanbus-abcdef12-1111",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={"issue_type": "task", "status": "in_progress", "title": "Create watcher"},
    )
    notice = module.summarize_event(created)
    assert notice.scene is not None
    header_text = _scene_header_text(notice.scene)
    assert header_text.startswith("KANBUS")
    assert "TASK" in header_text
    # Parent-present layout includes top section, divider, and bottom section.
    assert len(notice.scene.layout.rows) == 9

    created_missing_status = module.KanbusEvent(
        path=Path("x2.json"),
        schema_version=1,
        event_id="e1b",
        issue_id="kanbus-abc12345-2222",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:01Z"),
        actor_id="tester",
        payload={"issue_type": "task", "title": "Missing status"},
    )
    missing_status_notice = module.summarize_event(created_missing_status)
    assert missing_status_notice.scene is not None
    assert _scene_header_text(missing_status_notice.scene).startswith("KANBUSTASK")
    missing_status_body = "\n".join(
        str(getattr(r, "content", "")) for r in missing_status_notice.scene.layout.rows[1:]
    )
    assert "Missing status" in missing_status_body

    created_long_title = module.KanbusEvent(
        path=Path("x3.json"),
        schema_version=1,
        event_id="e1c",
        issue_id="kanbus-abcd9999-3333",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:02Z"),
        actor_id="tester",
        payload={
            "issue_type": "task",
            "status": "open",
            "title": "This is a very long created issue title that should wrap across lines",
        },
    )
    long_title_notice = module.summarize_event(created_long_title)
    assert long_title_notice.scene is not None
    # No parent layout: header + 7 issue rows.
    assert len(long_title_notice.scene.layout.rows) == 8

    transition = module.KanbusEvent(
        path=Path("y.json"),
        schema_version=1,
        event_id="e2",
        issue_id="kanbus-bbeeff12-1111",
        event_type="state_transition",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={"from_status": "open", "to_status": "closed", "title": "Clock status sync"},
    )
    transition_notice = module.summarize_event(transition)
    assert transition_notice.scene is not None
    t_header = _scene_header_text(transition_notice.scene)
    assert t_header.startswith("KANBUS")
    assert "BUG" in t_header
    assert "INPROGRESS" in t_header
    body_text = "\n".join(
        str(getattr(r, "content", ""))
        for r in transition_notice.scene.layout.rows[1:]
    )
    assert "FROM:" not in body_text
    assert "TO:" not in body_text

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
    assert comment_notice.scene is not None
    c_rows = comment_notice.scene.layout.rows
    # Header + 2 issue rows + 3 comment rows.
    assert len(c_rows) == 6
    c_body = [str(getattr(r, "content", "")) for r in c_rows[1:]]
    assert any("Issue" in line for line in c_body[:2])
    assert any("description" in line for line in c_body[:2])
    assert any("Deploy failed" in line for line in c_body[2:])


def test_issue_type_palette_applies_to_cards_including_comments():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        fixtures = {
            "kanbus-task-1": {
                "id": "kanbus-task-1",
                "type": "task",
                "status": "open",
                "description": "Task description",
                "comments": [],
            },
            "kanbus-epic-1": {
                "id": "kanbus-epic-1",
                "type": "epic",
                "status": "open",
                "description": "Epic description",
                "comments": [],
            },
            "kanbus-story-1": {
                "id": "kanbus-story-1",
                "type": "story",
                "status": "open",
                "description": "Story description",
                "comments": [],
            },
            "kanbus-bug-1": {
                "id": "kanbus-bug-1",
                "type": "bug",
                "status": "open",
                "description": "Bug description",
                "comments": [{"text": "Bug comment text"}],
            },
        }
        payload = fixtures.get(issue_id, {"id": issue_id, "type": "issue", "status": "open", "description": ""})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    def _assert_band(scene, band: str):
        header = scene.layout.rows[0]
        expected_bg = module.parse_color(f"dark.{band}2")
        expected_header = module.parse_color(f"dark.{band}8")
        expected_main = module.parse_color(f"dark.{band}9")
        assert header.background_color == expected_bg
        assert header.style.color == expected_header
        # Body rows should use the same band background.
        assert all(getattr(row, "background_color", expected_bg) == expected_bg for row in scene.layout.rows[1:])
        # Main body content should use the brightest intensity for the band.
        text_rows = [row for row in scene.layout.rows[1:] if hasattr(row, "style") and getattr(row, "content", "") != ""]
        assert any(getattr(row.style, "color", None) == expected_main for row in text_rows)

    task_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("task.json"),
            schema_version=1,
            event_id="e-task",
            issue_id="kanbus-task-1",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert task_notice.scene is not None
    _assert_band(task_notice.scene, "blue")

    epic_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("epic.json"),
            schema_version=1,
            event_id="e-epic",
            issue_id="kanbus-epic-1",
            event_type="state_transition",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert epic_notice.scene is not None
    _assert_band(epic_notice.scene, "indigo")

    story_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("story.json"),
            schema_version=1,
            event_id="e-story",
            issue_id="kanbus-story-1",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert story_notice.scene is not None
    _assert_band(story_notice.scene, "yellow")

    bug_comment_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("bug.json"),
            schema_version=1,
            event_id="e-bug",
            issue_id="kanbus-bug-1",
            event_type="comment_added",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={"comment": "Manual comment payload"},
        )
    )
    assert bug_comment_notice.scene is not None
    _assert_band(bug_comment_notice.scene, "red")


def test_issue_prefix_uses_event_issue_key_when_show_returns_internal_id():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot("BIBS-1234")
    assert snapshot is not None
    assert snapshot.id_prefix_upper == "BIBS"


def test_issue_prefix_uses_key_field_when_available():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "key": "ACME-42",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot("kanbus-abcdef")
    assert snapshot is not None
    assert snapshot.id_prefix_upper == "ACME"


def test_issue_prefix_uses_payload_key_when_show_returns_internal_id_only():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot(
        "kanbus-abcdef",
        payload={"issue_key": "BIBS-1234"},
    )
    assert snapshot is not None
    assert snapshot.id_prefix_upper == "BIBS"


def test_issue_prefix_does_not_fall_back_to_numeric_suffix_when_requested_key_exists():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "short_id": "123",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot("ABC-123")
    assert snapshot is not None
    assert snapshot.id_prefix_upper == "ABC"


def test_summarize_event_prefers_event_issue_key_prefix_over_lookup_ids():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "short_id": "1234",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("ev.json"),
            schema_version=1,
            event_id="e-1",
            issue_id="ABC-1234",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-05T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert notice.scene is not None
    assert _scene_header_text(notice.scene).startswith("ABCTASK")


def test_event_prefix_override_rejects_numeric_only_prefix():
    module = _load_demo_module()
    assert module._event_prefix_override("ABC-1234") == "ABC"
    assert module._event_prefix_override("1234") == ""
    assert module._event_prefix_override("kanbus-abc123") == ""


def test_payload_prefix_override_prefers_full_issue_key():
    module = _load_demo_module()
    assert module._payload_prefix_override({"issue_key": "ABC-1234"}) == "ABC"
    assert module._payload_prefix_override({"project_key": "ABC", "number": 1234}) == "ABC"
    assert module._payload_prefix_override({"text": "Issue ABC-9876 updated"}) == "ABC"


def test_repo_prefix_used_when_show_fails(tmp_path: Path):
    module = _load_demo_module()
    config_path = tmp_path / ".kanbus.yml"
    config_path.write_text("project_key: PIXO\n", encoding="utf-8")
    event = module.KanbusEvent(
        path=tmp_path / "project" / "events" / "event.json",
        schema_version=1,
        event_id="e-1",
        issue_id="03adbc",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-05T00:00:00Z"),
        actor_id="tester",
        payload={},
        repo_root=tmp_path,
    )

    module._run_kbs_show_json = lambda *args, **kwargs: None  # type: ignore[assignment]
    notice = module.summarize_event(event)
    assert notice.scene is not None
    assert _scene_header_text(notice.scene).startswith("PIXO")


def test_repo_prefix_used_when_issue_id_matches_project_key(tmp_path: Path):
    module = _load_demo_module()
    config_path = tmp_path / ".kanbus.yml"
    config_path.write_text("project_key: PIXO\n", encoding="utf-8")

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "PIXO-acdeff11-2222-3333-4444-555555555555",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot("acdeff11-2222-3333-4444-555555555555", repo_root=tmp_path)
    assert snapshot is not None
    assert snapshot.id_prefix_upper == "PIXO"


def test_summarize_event_uses_payload_prefix_when_event_id_is_numeric():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "kanbus-11111111-2222-3333-4444-555555555555",
            "short_id": "1234",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("ev2.json"),
            schema_version=1,
            event_id="e-2",
            issue_id="1234",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-05T00:00:00Z"),
            actor_id="tester",
            payload={"issue_key": "ABC-1234"},
        )
    )
    assert notice.scene is not None
    assert _scene_header_text(notice.scene).startswith("ABCTASK")


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


def test_watch_poll_step_returns_logs_and_notices(tmp_path: Path):
    module = _load_demo_module()
    module.subprocess.run = lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="")  # type: ignore[assignment]
    events_dir = tmp_path / "project" / "events"
    events_dir.mkdir(parents=True)
    event_path = events_dir / "2026-03-04T00:00:01.000Z__new.json"
    _write_event(
        event_path,
        event_type="issue_created",
        issue_id="kanbus-watch-1",
        occurred_at="2026-03-04T00:00:01.000Z",
        payload={"title": "watch", "status": "open", "issue_type": "task"},
    )

    tracked: dict[Path, set[str]] = {events_dir.resolve(): set()}
    failures: dict[Path, int] = {}
    logs, notices = module._watch_poll_step(
        root=tmp_path,
        tracked=tracked,
        failures=failures,
        do_rescan=False,
        max_failures=5,
    )

    assert len(notices) == 1
    assert notices[0].header.startswith("KANBUS")
    assert any("watcher: event issue_created" in line for line in logs)
    assert event_path.name in tracked[events_dir.resolve()]


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


def test_enqueue_message_transition_uses_push_left_for_in_and_out():
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
    # Kanbus clock now uses leftward push for both directions:
    # notice enters from right, then exits left while clock enters from right.
    assert items[1].transition.kind == "push_left"
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
            line_darker_steps={1: 1},
            line_indent_px={2: 2},
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


def test_message_scene_pins_first_line_before_vertical_center_pad():
    module = _load_demo_module()

    scene = module._message_scene(
        "info",
        "KBS ABCDEF\nFROM:\nOPEN\nTO:\nCLOSED",
        fg=(100, 100, 100),
        bg=(10, 10, 10),
        body_font="bytesized",
        body_center_vertical=True,
        pin_first_line_top=True,
        body_min_row_height=6,
        body_max_row_height=6,
    )
    rows = scene.layout.rows
    assert rows[1].content == "KBS ABCDEF"
    assert rows[2].content == ""


def test_message_scene_centers_configured_non_first_line():
    module = _load_demo_module()

    scene = module._message_scene(
        "info",
        "ID\nTASK OPEN\nTitle",
        fg=(100, 100, 100),
        bg=(10, 10, 10),
        center_first_line=True,
        center_line_indices={1},
        first_line_darker_steps=2,
        line_darker_steps={1: 2},
    )
    rows = scene.layout.rows[1:]
    text_rows = [r for r in rows if getattr(r, "content", None) not in ("", None)]
    assert len(text_rows) >= 2
    assert text_rows[0].content == "ID"
    assert text_rows[1].content == "TASK OPEN"
    assert text_rows[0].align == "center"
    assert text_rows[1].align == "center"
    first = text_rows[0].style.color
    second = text_rows[1].style.color
    assert first == second


def test_message_scene_applies_pre_line_spacer():
    module = _load_demo_module()

    scene = module._message_scene(
        "info",
        "ID\nDESC\nFROM:\nOPEN",
        fg=(100, 100, 100),
        bg=(10, 10, 10),
        line_spacer_before_px={2: 2},
        body_min_row_height=6,
        body_max_row_height=6,
    )
    rows = scene.layout.rows[1:]
    assert rows[0].content == "ID"
    assert rows[1].content == "DESC"
    assert rows[2].content == ""
    assert rows[2].height == 2
    assert rows[3].content == "FROM:"


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


def test_issue_id_prefix_upper_from_before_dash():
    module = _load_demo_module()
    assert module._issue_id_prefix_upper("kanbus-abc123") == "KANBUS"
    assert module._issue_id_prefix_upper("kanbus-b31680b6-1514-4fc7") == "KANBUS"
    assert module._issue_id_prefix_upper("EPIC-123") == "EPIC"
    assert module._issue_id_prefix_upper("singleid") == "SINGLEID"


def test_live_issue_fetch_called_for_each_event(monkeypatch):
    module = _load_demo_module()
    calls: list[tuple[list[str], str | None]] = []

    def _fake_run(*args, **kwargs):
        calls.append((list(args[0]), kwargs.get("cwd")))
        issue_id = args[0][2]
        payload = {
            "id": issue_id,
            "type": "task",
            "status": "open",
            "description": "desc",
            "comments": [{"text": "comment fallback"}],
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    repo_path = Path("/tmp/demo-repo/project/events/event.json")
    events = [
        module.KanbusEvent(
            path=repo_path,
            schema_version=1,
            event_id="e1",
            issue_id="kanbus-live-0001",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        ),
        module.KanbusEvent(
            path=repo_path,
            schema_version=1,
            event_id="e2",
            issue_id="kanbus-live-0002",
            event_type="state_transition",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:01Z"),
            actor_id="tester",
            payload={},
        ),
        module.KanbusEvent(
            path=repo_path,
            schema_version=1,
            event_id="e3",
            issue_id="kanbus-live-0003",
            event_type="comment_added",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:02Z"),
            actor_id="tester",
            payload={},
        ),
    ]

    for event in events:
        module.summarize_event(event)

    assert len(calls) == 3
    assert all(call[0][:3] == ["kbs", "show", call[0][2]] for call in calls)
    assert all(call[1] == str(Path("/tmp/demo-repo").resolve()) for call in calls)


def test_parent_fetch_only_when_parent_present(monkeypatch):
    module = _load_demo_module()
    requested_ids: list[str] = []

    def _fake_run(*args, **kwargs):
        issue_id = args[0][2]
        requested_ids.append(issue_id)
        if issue_id == "kanbus-with-parent":
            payload = {
                "id": issue_id,
                "type": "task",
                "status": "open",
                "description": "child desc",
                "parent": "kanbus-parent-xyz",
                "comments": [],
            }
        elif issue_id == "kanbus-parent-xyz":
            payload = {
                "id": issue_id,
                "type": "epic",
                "status": "open",
                "description": "parent desc",
                "comments": [],
            }
        else:
            payload = {
                "id": issue_id,
                "type": "task",
                "status": "open",
                "description": "no parent desc",
                "comments": [],
            }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    event_with_parent = module.KanbusEvent(
        path=Path("/tmp/demo-repo/project/events/event.json"),
        schema_version=1,
        event_id="ep",
        issue_id="kanbus-with-parent",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={},
    )
    module.summarize_event(event_with_parent)

    event_without_parent = module.KanbusEvent(
        path=Path("/tmp/demo-repo/project/events/event.json"),
        schema_version=1,
        event_id="enp",
        issue_id="kanbus-no-parent",
        event_type="issue_created",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:01Z"),
        actor_id="tester",
        payload={},
    )
    module.summarize_event(event_without_parent)

    assert requested_ids.count("kanbus-with-parent") == 1
    assert requested_ids.count("kanbus-parent-xyz") == 1
    assert requested_ids.count("kanbus-no-parent") == 1


def test_build_parser_defaults_auto_info_seconds_30():
    module = _load_demo_module()
    parser = module.build_parser()
    args = parser.parse_args([])
    assert args.auto_info_seconds == 30.0
