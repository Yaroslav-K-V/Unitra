import json
import os
import tempfile
import pytest

import src.recent as recent_module
from src.recent import add_recent, get_recent, MAX_RECENT


@pytest.fixture(autouse=True)
def isolated_recent(tmp_path, monkeypatch):
    """Redirect RECENT_PATH to a temp file for each test."""
    tmp_file = tmp_path / "recent.json"
    monkeypatch.setattr(recent_module, "RECENT_PATH", str(tmp_file))
    yield tmp_file


# ── add_recent ────────────────────────────────────────────────────────────────

def test_add_recent_file(tmp_path):
    f = tmp_path / "code.py"
    f.write_text("x = 1")
    add_recent(str(f))
    items = get_recent()
    assert len(items) == 1
    assert items[0]["path"] == str(f)
    assert items[0]["type"] == "file"


def test_add_recent_folder(tmp_path):
    add_recent(str(tmp_path))
    items = get_recent()
    assert items[0]["type"] == "folder"


def test_add_recent_deduplicates(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("")
    add_recent(str(f))
    add_recent(str(f))
    items = get_recent()
    assert len(items) == 1


def test_add_recent_most_recent_first(tmp_path):
    a = tmp_path / "a.py"; a.write_text("")
    b = tmp_path / "b.py"; b.write_text("")
    add_recent(str(a))
    add_recent(str(b))
    items = get_recent()
    assert items[0]["path"] == str(b)


def test_add_recent_respects_max(tmp_path):
    files = []
    for i in range(MAX_RECENT + 3):
        f = tmp_path / f"f{i}.py"
        f.write_text("")
        files.append(f)
        add_recent(str(f))
    items = get_recent()
    assert len(items) == MAX_RECENT


def test_add_recent_moves_duplicate_to_front(tmp_path):
    a = tmp_path / "a.py"; a.write_text("")
    b = tmp_path / "b.py"; b.write_text("")
    add_recent(str(a))
    add_recent(str(b))
    add_recent(str(a))  # re-add a → should be first now
    items = get_recent()
    assert items[0]["path"] == str(a)


# ── get_recent ────────────────────────────────────────────────────────────────

def test_get_recent_empty(isolated_recent):
    assert get_recent() == []


def test_get_recent_filters_missing(tmp_path, isolated_recent):
    """Entries whose paths no longer exist are excluded."""
    ghost = str(tmp_path / "gone.py")
    data = [{"path": ghost, "type": "file"}]
    isolated_recent.write_text(json.dumps(data))
    assert get_recent() == []


def test_get_recent_keeps_existing(tmp_path, isolated_recent):
    real = tmp_path / "real.py"
    real.write_text("")
    data = [{"path": str(real), "type": "file"}]
    isolated_recent.write_text(json.dumps(data))
    items = get_recent()
    assert len(items) == 1
    assert items[0]["path"] == str(real)
