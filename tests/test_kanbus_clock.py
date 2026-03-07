"""Unit tests for demos/kanbus_clock.py helper logic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import asyncio
import time
import urllib.request

import pytest


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
                    "title": "Issue title for comment card",
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
    # Parent-present layout uses comment-style rows: header + 2 parent + 2 issue + 5 bottom.
    assert len(notice.scene.layout.rows) == 10

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
    # No parent layout: header + 2 issue + 7 bottom.
    assert len(long_title_notice.scene.layout.rows) == 10

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
    # Header + 2 issue + 7 comment rows (no parent).
    assert len(c_rows) == 10
    c_body = [str(getattr(r, "content", "")) for r in c_rows[1:]]
    assert any("Issue title" in line for line in c_body[:2])
    assert any("Deploy failed" in line for line in c_body[2:])


def test_transition_layout_fills_viewport_and_rows():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        long_desc = (
            "This is a long issue description intended to wrap across many lines "
            "so the transition layout can be validated for row allocation."
        )
        fixtures = {
            "kanbus-with-parent": {
                "id": "kanbus-with-parent",
                "type": "task",
                "status": "in_progress",
                "description": long_desc * 4,
                "parent": "kanbus-parent",
                "comments": [],
            },
            "kanbus-parent": {
                "id": "kanbus-parent",
                "type": "epic",
                "status": "open",
                "description": long_desc * 2,
                "comments": [],
            },
            "kanbus-no-parent": {
                "id": "kanbus-no-parent",
                "type": "bug",
                "status": "in_progress",
                "description": long_desc * 6,
                "comments": [],
            },
        }
        payload = fixtures.get(issue_id, {"id": issue_id, "type": "issue", "status": "open", "description": ""})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    parent_transition = module.KanbusEvent(
        path=Path("p.json"),
        schema_version=1,
        event_id="ep",
        issue_id="kanbus-with-parent",
        event_type="state_transition",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={},
    )
    parent_notice = module.summarize_event(parent_transition)
    assert parent_notice.scene is not None
    rows = parent_notice.scene.layout.rows
    assert len(rows) == 10

    no_parent_transition = module.KanbusEvent(
        path=Path("np.json"),
        schema_version=1,
        event_id="enp",
        issue_id="kanbus-no-parent",
        event_type="state_transition",
        occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
        actor_id="tester",
        payload={},
    )
    no_parent_notice = module.summarize_event(no_parent_transition)
    assert no_parent_notice.scene is not None
    np_rows = no_parent_notice.scene.layout.rows
    assert len(np_rows) == 10


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

    def _assert_band(scene, band: str, *, comment: bool = False):
        header = scene.layout.rows[0]
        expected_body_bg = module.parse_color(f"dark.{band}1")
        expected_issue_bg = module.parse_color(f"dark.{band}2")
        expected_header_bg = module.parse_color(f"dark.{band}4")
        expected_header = module.parse_color(f"dark.{band}{module._BASE_STEP}")
        expected_main = module.parse_color(f"dark.{band}{module._ATTENTION_STEP}")
        expected_comment = module.parse_color(f"dark.sky{module._ATTENTION_STEP}")
        assert header.background_color == expected_header_bg
        assert header.style.color == expected_header
        # Body rows use issue bg (step 2) for issue lines and body bg (step 1) for bottom lines.
        assert any(getattr(row, "background_color", expected_body_bg) == expected_body_bg for row in scene.layout.rows[1:])
        assert any(getattr(row, "background_color", expected_issue_bg) == expected_issue_bg for row in scene.layout.rows[1:])
        # Main body content should use the brightest intensity for the band.
        text_rows = [row for row in scene.layout.rows[1:] if hasattr(row, "style") and getattr(row, "content", "") != ""]
        if comment:
            assert any(getattr(row.style, "color", None) == expected_comment for row in text_rows)
        else:
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
    _assert_band(bug_comment_notice.scene, "red", comment=True)


def test_parent_row_uses_parent_issue_type_palette():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        fixtures = {
            "kanbus-child-1": {
                "id": "kanbus-child-1",
                "type": "story",
                "status": "open",
                "title": "Child title",
                "description": "Child description",
                "parent": "kanbus-parent-1",
                "comments": [],
            },
            "kanbus-parent-1": {
                "id": "kanbus-parent-1",
                "type": "epic",
                "status": "open",
                "title": "Parent title",
                "description": "Parent description",
                "comments": [],
            },
        }
        payload = fixtures.get(issue_id, {"id": issue_id, "type": "issue", "status": "open", "description": ""})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("parent.json"),
            schema_version=1,
            event_id="e-parent",
            issue_id="kanbus-child-1",
            event_type="comment_added",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={"comment": "Parent palette test"},
        )
    )
    assert notice.scene is not None
    rows = notice.scene.layout.rows
    parent_row = rows[1]
    parent_bg = parent_row.background_color
    assert parent_bg == module.parse_color("dark.indigo3")


def test_comment_and_transition_use_titles_in_top_rows():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        fixtures = {
            "kanbus-title-1": {
                "id": "kanbus-title-1",
                "type": "task",
                "status": "open",
                "title": "Title One",
                "description": "Description One",
                "comments": [],
            }
        }
        payload = fixtures.get(issue_id, {"id": issue_id, "type": "issue", "status": "open", "description": ""})
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    comment_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("c.json"),
            schema_version=1,
            event_id="ec",
            issue_id="kanbus-title-1",
            event_type="comment_added",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={"comment": "comment body"},
        )
    )
    assert comment_notice.scene is not None
    comment_rows = comment_notice.scene.layout.rows
    top_text = "\n".join(str(r.content) for r in comment_rows[1:3])
    assert "Title One" in top_text
    assert "Description One" not in top_text

    transition_notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("t.json"),
            schema_version=1,
            event_id="et",
            issue_id="kanbus-title-1",
            event_type="state_transition",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert transition_notice.scene is not None
    transition_rows = transition_notice.scene.layout.rows
    transition_top = "\n".join(str(r.content) for r in transition_rows[1:3])
    transition_bottom = "\n".join(str(r.content) for r in transition_rows[3:])
    assert "Title One" in transition_top
    assert "Description One" in transition_bottom


def test_transition_header_status_uses_attention_color():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        payload = {
            "id": issue_id,
            "type": "story",
            "status": "in_progress",
            "title": "Story title",
            "description": "Story description",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("t.json"),
            schema_version=1,
            event_id="et",
            issue_id="kanbus-story-1",
            event_type="state_transition",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert notice.scene is not None
    header_row = notice.scene.layout.rows[0]
    spans = getattr(header_row, "content", [])
    status_spans = [
        span
        for span in spans
        if getattr(span, "text", "") in {"INPROGRESS", "IN", "PROGRESS"}
    ]
    assert status_spans
    expected = module.parse_color(f"dark.yellow{module._ATTENTION_STEP}")
    assert all(getattr(span, "color", None) == expected for span in status_spans)


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


def test_header_id_prefix_is_one_step_lighter_than_base():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        issue_id = args[0][2]
        payload = {
            "id": issue_id,
            "type": "task",
            "status": "open",
            "title": "Title",
            "description": "Desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]

    notice = module.summarize_event(
        module.KanbusEvent(
            path=Path("ev.json"),
            schema_version=1,
            event_id="e-1",
            issue_id="ABCD-1234",
            event_type="issue_created",
            occurred_at=module._parse_iso8601("2026-03-04T00:00:00Z"),
            actor_id="tester",
            payload={},
        )
    )
    assert notice.scene is not None
    header_row = notice.scene.layout.rows[0]
    spans = getattr(header_row, "content", [])
    prefix_span = next(
        (span for span in spans if getattr(span, "text", "") == "ABCD"),
        None,
    )
    assert prefix_span is not None
    expected = module.parse_color(f"dark.blue{min(module._BASE_STEP + 1, 12)}")
    assert prefix_span.color == expected


def test_kbs_show_uses_project_root_arg_when_available():
    module = _load_demo_module()
    calls: list[list[str]] = []

    def _fake_run(*args, **kwargs):
        command = args[0]
        calls.append(command)
        payload = {"id": "PIXO-1234", "type": "task", "status": "open", "description": "d"}
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_run  # type: ignore[assignment]
    module._run_kbs_show_json("PIXO-1234", kbs_root=Path("/tmp"), project_root=Path("/tmp/proj"))
    assert any("--project-root" in call for call in calls)


def test_auto_notice_queue_blocks_instead_of_dropping():
    module = _load_demo_module()

    async def _run() -> None:
        queue: asyncio.Queue[module.AutoNotice] = asyncio.Queue(maxsize=1)
        notice = module.AutoNotice(header="H", message="M")
        await module._enqueue_auto_notice(queue, notice)

        put_task = asyncio.create_task(module._enqueue_auto_notice(queue, notice))
        await asyncio.sleep(0)
        assert not put_task.done()
        _ = await queue.get()
        await asyncio.wait_for(put_task, timeout=1.0)
        assert queue.qsize() == 1

    asyncio.run(_run())


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


def test_issue_prefix_falls_back_to_event_issue_id_when_show_fails(tmp_path: Path):
    module = _load_demo_module()
    event = module.KanbusEvent(
        path=tmp_path / "project" / "events" / "event.json",
        schema_version=1,
        event_id="e-1",
        issue_id="PIXO-03adbc",
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


def test_issue_prefix_uses_key_from_show_payload():
    module = _load_demo_module()

    def _fake_issue(*args, **kwargs):
        payload = {
            "id": "PIXO-acdeff11-2222-3333-4444-555555555555",
            "type": "task",
            "status": "open",
            "description": "desc",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    module.subprocess.run = _fake_issue  # type: ignore[assignment]
    snapshot = module._fetch_issue_snapshot("acdeff11-2222-3333-4444-555555555555")
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
    module.subprocess.run = lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="")  # type: ignore[assignment]
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
        kbs_root=tmp_path,
    )

    assert len(notices) == 1
    assert notices[0].header.startswith("KANBUS")
    assert any("watcher: event issue_created" in line for line in logs)
    assert event_path.name in tracked[events_dir.resolve()]


def test_watch_poll_step_skips_ambiguous_identifiers(tmp_path: Path):
    module = _load_demo_module()

    def _fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="ambiguous identifier")

    module.subprocess.run = _fake_run  # type: ignore[assignment]
    events_dir = tmp_path / "project" / "events"
    events_dir.mkdir(parents=True)
    event_path = events_dir / "2026-03-04T00:00:01.000Z__new.json"
    _write_event(
        event_path,
        event_type="issue_created",
        issue_id="kanbus-watch-2",
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
        kbs_root=tmp_path,
    )

    assert notices == []
    assert any("ambiguous identifier" in line for line in logs)


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


def test_enqueue_message_transition_retries_when_scene_queue_is_temporarily_full():
    module = _load_demo_module()

    class _DummyClockScene:
        name = "clock"

    class _FlakyPlayer:
        def __init__(self):
            self.items = []
            self.failed_once = False

        @property
        def queue_depth(self):
            return len(self.items)

        async def enqueue(self, item):
            if len(self.items) == 1 and not self.failed_once:
                self.failed_once = True
                raise ValueError("scene transition queue is full")
            self.items.append(item)

    async def _run():
        player = _FlakyPlayer()
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
        return player

    player = __import__("asyncio").run(_run())
    assert player.failed_once is True
    assert len(player.items) == 2
    assert player.items[0].transition.kind == "push_left"
    assert player.items[1].transition.kind == "push_left"


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
    assert all(call[1] is None for call in calls)


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
    assert args.theme_check_seconds == 5.0
    assert args.event_source == "gossip"
    assert args.theme == "auto"
    assert args.react_clock is True
    assert not hasattr(args, "storybook_iframe")
    assert not hasattr(args, "clock_story_id")
    assert not hasattr(args, "clock_browser_mode")


def test_discover_kanbus_project_roots_recursive(tmp_path: Path):
    module = _load_demo_module()
    (tmp_path / ".kanbus.yml").write_text("key: root\n", encoding="utf-8")
    (tmp_path / "Kanbus" / ".kanbus.yml").parent.mkdir(parents=True)
    (tmp_path / "Kanbus" / ".kanbus.yml").write_text("key: kanbus\n", encoding="utf-8")
    (tmp_path / "Other" / "Nested" / ".kanbus.yml").parent.mkdir(parents=True)
    (tmp_path / "Other" / "Nested" / ".kanbus.yml").write_text("key: nested\n", encoding="utf-8")
    (tmp_path / "project" / "events").mkdir(parents=True)

    roots = module.discover_kanbus_project_roots(tmp_path)
    assert roots == sorted(
        [
            tmp_path.resolve(),
            (tmp_path / "Kanbus").resolve(),
            (tmp_path / "Other" / "Nested").resolve(),
        ]
    )


def test_watch_gossip_loop_fans_out_workers():
    module = _load_demo_module()

    async def _run():
        stop_event = asyncio.Event()
        notices: asyncio.Queue[module.AutoNotice] = asyncio.Queue()
        roots = [Path("/tmp/proj-a"), Path("/tmp/proj-b"), Path("/tmp/proj-c")]
        seen: list[Path] = []

        async def _fake_worker(**kwargs):
            seen.append(kwargs["root"])
            await kwargs["stop_event"].wait()

        module._watch_gossip_worker = _fake_worker  # type: ignore[assignment]
        task = asyncio.create_task(
            module._watch_gossip_loop(
                roots=roots,
                notices=notices,
                stop_event=stop_event,
                kbs_root=Path("/tmp/workspace"),
            )
        )
        await asyncio.sleep(0)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1.0)
        return seen

    seen = asyncio.run(_run())
    assert sorted(seen) == sorted([Path("/tmp/proj-a"), Path("/tmp/proj-b"), Path("/tmp/proj-c")])


def test_gossip_restart_delay_is_exponential_and_bounded():
    module = _load_demo_module()
    assert module._gossip_restart_delay_seconds(0) == 0.5
    assert module._gossip_restart_delay_seconds(1) == 1.0
    assert module._gossip_restart_delay_seconds(2) == 2.0
    assert module._gossip_restart_delay_seconds(3) == 4.0
    assert module._gossip_restart_delay_seconds(6) == 30.0
    assert module._gossip_restart_delay_seconds(20) == 30.0


def test_theme_resolution_and_radix_token_mapping(monkeypatch):
    module = _load_demo_module()
    monkeypatch.setattr(module, "_detect_system_theme", lambda: "light")
    assert module._set_active_theme("auto") == "light"
    assert module._radix_token("blue", 7) == "blue7"
    assert module._set_active_theme("dark") == "dark"
    assert module._radix_token("blue", 7) == "dark.blue7"


def test_theme_monitor_loop_updates_theme_and_calls_callback(monkeypatch):
    module = _load_demo_module()
    detected = iter(["dark", "light", "light"])
    monkeypatch.setattr(module, "_detect_system_theme", lambda: next(detected))
    assert module._set_active_theme("auto") == "dark"

    seen: list[str] = []

    async def _run():
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            module._theme_monitor_loop(
                mode="auto",
                check_seconds=1.0,
                stop_event=stop_event,
                on_theme_change=seen.append,
            )
        )
        await asyncio.sleep(1.05)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(_run())
    assert seen == ["light"]
    assert module._ACTIVE_THEME == "light"


def test_theme_monitor_loop_first_check_is_fast(monkeypatch):
    module = _load_demo_module()
    assert module._set_active_theme("dark") == "dark"
    seen: list[str] = []

    async def _run():
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            module._theme_monitor_loop(
                mode="auto",
                check_seconds=20.0,
                stop_event=stop_event,
                on_theme_change=seen.append,
            )
        )
        await asyncio.sleep(0.2)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1.0)

    start = time.monotonic()
    asyncio.run(_run())
    elapsed = time.monotonic() - start
    assert elapsed < 2.5
    assert seen == []


def test_theme_monitor_loop_noop_for_explicit_mode():
    module = _load_demo_module()

    async def _run():
        stop_event = asyncio.Event()
        started = time.monotonic()
        await module._theme_monitor_loop(
            mode="dark",
            check_seconds=1.0,
            stop_event=stop_event,
            on_theme_change=None,
        )
        return time.monotonic() - started

    elapsed = asyncio.run(_run())
    assert elapsed < 0.1


def test_event_from_gossip_envelope_classifies_created_transition_and_comment():
    module = _load_demo_module()
    created_issue = {
        "id": "PIXO-abc123",
        "type": "task",
        "status": "open",
        "title": "Issue title",
        "description": "Issue description",
        "comments": [],
        "created_at": "2026-03-07T03:00:00.000Z",
        "updated_at": "2026-03-07T03:00:00.000Z",
    }
    created_envelope = {
        "id": "env-created",
        "event_id": "evt-created",
        "ts": "2026-03-07T03:00:00.000Z",
        "producer_id": "gossip-test",
        "type": "issue.mutated",
        "issue_id": "PIXO-abc123",
        "issue": created_issue,
    }
    created_event = module._event_from_gossip_envelope(created_envelope, prior_issue=None)
    assert created_event is not None
    assert created_event.event_type == "issue_created"

    transitioned_issue = dict(created_issue)
    transitioned_issue["status"] = "in_progress"
    transitioned_issue["updated_at"] = "2026-03-07T03:00:10.000Z"
    transitioned_envelope = dict(created_envelope)
    transitioned_envelope["id"] = "env-transition"
    transitioned_envelope["event_id"] = "evt-transition"
    transitioned_envelope["issue"] = transitioned_issue
    transitioned_event = module._event_from_gossip_envelope(
        transitioned_envelope,
        prior_issue=created_issue,
    )
    assert transitioned_event is not None
    assert transitioned_event.event_type == "state_transition"
    assert transitioned_event.payload["from_status"] == "OPEN"
    assert transitioned_event.payload["to_status"] == "IN PROGRESS"

    commented_issue = dict(transitioned_issue)
    commented_issue["comments"] = [{"text": "fresh comment from gossip"}]
    commented_issue["updated_at"] = "2026-03-07T03:00:20.000Z"
    commented_envelope = dict(created_envelope)
    commented_envelope["id"] = "env-comment"
    commented_envelope["event_id"] = "evt-comment"
    commented_envelope["issue"] = commented_issue
    commented_event = module._event_from_gossip_envelope(
        commented_envelope,
        prior_issue=transitioned_issue,
    )
    assert commented_event is not None
    assert commented_event.event_type == "comment_added"
    assert commented_event.payload["comment"] == "fresh comment from gossip"


def test_runtime_clock_url_uses_direct_query_params():
    module = _load_demo_module()
    url = module._runtime_clock_url(
        "http://127.0.0.1:1234/index.html",
        {"hour": 9, "minute": 30, "showSecondHand": False},
    )
    assert "id=" not in url
    assert "args=" not in url
    assert "hour=9" in url
    assert "minute=30" in url
    assert "showSecondHand=false" in url


def test_react_clock_scene_includes_theme_query(monkeypatch):
    module = _load_demo_module()
    captured: dict[str, str] = {}

    def _fake_render(url: str, *, t: float = 0.0):
        captured["url"] = url
        return module.Buffer(width=64, height=64, data=tuple([0] * (64 * 64 * 3)))

    monkeypatch.setattr(module, "_render_runtime_frame", _fake_render)
    scene = module.ReactClockScene(
        runtime_base_url="http://127.0.0.1:1234/runtime.html",
        show_second_hand=False,
        theme="light",
    )
    scene._render_clock_sync(0.0)
    assert "theme=light" in captured["url"]
    scene.set_theme("dark")
    scene._render_clock_sync(0.0)
    assert "theme=dark" in captured["url"]


def test_runtime_static_server_requires_built_assets(tmp_path: Path):
    module = _load_demo_module()
    server = module._RuntimeStaticServer(tmp_path / "missing")
    with pytest.raises(RuntimeError):
        server.start()


def test_runtime_static_server_serves_index(tmp_path: Path):
    module = _load_demo_module()
    assets = tmp_path / "runtime"
    assets.mkdir(parents=True)
    (assets / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    server = module._RuntimeStaticServer(assets)
    server.start()
    try:
        with urllib.request.urlopen(server.base_url, timeout=2) as response:
            body = response.read().decode("utf-8")
            assert "ok" in body
    finally:
        server.stop()


def test_runtime_static_server_accepts_runtime_html(tmp_path: Path):
    module = _load_demo_module()
    assets = tmp_path / "runtime"
    assets.mkdir(parents=True)
    (assets / "runtime.html").write_text("<html><body>runtime</body></html>", encoding="utf-8")
    server = module._RuntimeStaticServer(assets)
    server.start()
    try:
        assert server.base_url.endswith("/runtime.html")
        with urllib.request.urlopen(server.base_url, timeout=2) as response:
            body = response.read().decode("utf-8")
            assert "runtime" in body
    finally:
        server.stop()
