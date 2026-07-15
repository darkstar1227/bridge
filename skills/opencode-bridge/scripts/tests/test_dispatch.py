import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dispatch  # noqa: E402


def test_load_json_file_missing_returns_default(tmp_path):
    missing = tmp_path / "nope.json"
    result = dispatch.load_json_file(missing, default={})
    assert result == {}


def test_load_json_file_valid_returns_contents(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"a": 1}))
    result = dispatch.load_json_file(path, default={})
    assert result == {"a": 1}


def test_load_json_file_corrupt_quarantines_and_returns_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json")
    result = dispatch.load_json_file(path, default={})
    assert result == {}
    quarantined = list(tmp_path.glob("config.json.corrupt-*"))
    assert len(quarantined) == 1
    assert not path.exists()


def test_save_json_file_atomic_write(tmp_path):
    path = tmp_path / "state.json"
    dispatch.save_json_file(path, {"x": 42})
    assert json.loads(path.read_text()) == {"x": 42}
    # no leftover temp file
    assert list(tmp_path.glob("state.json.tmp-*")) == []


def test_resolve_session_missing_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "sessions.json")
    result = dispatch.resolve_session("repo-a", "topic-a")
    assert result is None


def test_resolve_session_found_key_returns_session_id(tmp_path, monkeypatch):
    sessions_path = tmp_path / "sessions.json"
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", sessions_path)
    dispatch.save_json_file(sessions_path, {"repo-a::topic-a": "ses_123"})
    result = dispatch.resolve_session("repo-a", "topic-a")
    assert result == "ses_123"


def test_resolve_session_different_topic_same_repo_returns_none(tmp_path, monkeypatch):
    sessions_path = tmp_path / "sessions.json"
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", sessions_path)
    dispatch.save_json_file(sessions_path, {"repo-a::topic-a": "ses_123"})
    result = dispatch.resolve_session("repo-a", "topic-b")
    assert result is None


def test_update_session_mapping_persists(tmp_path, monkeypatch):
    sessions_path = tmp_path / "sessions.json"
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", sessions_path)
    dispatch.update_session_mapping("repo-a", "topic-a", "ses_new")
    assert dispatch.resolve_session("repo-a", "topic-a") == "ses_new"


def test_build_command_includes_dir_and_model():
    cmd = dispatch.build_command(task="do the thing", repo="/repo/a", model="opencode/kimi-k2.7-code", session_id=None)
    assert cmd[:3] == ["opencode", "run", "do the thing"]
    assert "--format" in cmd and "json" in cmd
    assert "--dir" in cmd and "/repo/a" in cmd
    assert "-m" in cmd and "opencode/kimi-k2.7-code" in cmd
    assert "--session" not in cmd  # no session_id yet


def test_build_command_includes_session_when_present():
    cmd = dispatch.build_command(task="do the thing", repo="/repo/a", model="m", session_id="ses_1")
    assert "--session" in cmd
    assert "ses_1" in cmd


def _init_git_repo(path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=path, check=True)


def test_git_status_snapshot_empty_repo(tmp_path):
    _init_git_repo(tmp_path)
    snapshot = dispatch.git_status_snapshot(str(tmp_path))
    assert snapshot == set()


def test_git_status_snapshot_detects_untracked_file(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "new.txt").write_text("hi")
    snapshot = dispatch.git_status_snapshot(str(tmp_path))
    assert any("new.txt" in line for line in snapshot)


def test_diff_snapshots_returns_new_lines_only(tmp_path):
    _init_git_repo(tmp_path)
    before = dispatch.git_status_snapshot(str(tmp_path))
    (tmp_path / "new.txt").write_text("hi")
    after = dispatch.git_status_snapshot(str(tmp_path))
    changed = dispatch.diff_snapshots(before, after)
    assert any("new.txt" in line for line in changed)


def test_diff_snapshots_no_changes_returns_empty(tmp_path):
    _init_git_repo(tmp_path)
    before = dispatch.git_status_snapshot(str(tmp_path))
    after = dispatch.git_status_snapshot(str(tmp_path))
    assert dispatch.diff_snapshots(before, after) == set()
