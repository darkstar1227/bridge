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


def test_build_ping_command_includes_model_and_scratch_dir():
    cmd = dispatch.build_ping_command(model="opencode/kimi-k2.7-code", scratch_dir="/tmp/scratch")
    assert cmd[:2] == ["opencode", "run"]
    assert "-m" in cmd and "opencode/kimi-k2.7-code" in cmd
    assert "--dir" in cmd and "/tmp/scratch" in cmd
    assert "--session" not in cmd  # ping never continues a session


def test_ping_model_uses_throwaway_dir_not_repo(monkeypatch):
    seen = {}

    def fake_run_opencode(cmd, timeout):
        seen["cmd"] = cmd
        seen["timeout"] = timeout
        return dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],
        )

    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    outcome = dispatch.ping_model(model="m1", timeout=5)
    assert outcome.classification == "DONE"
    assert seen["timeout"] == 5
    dir_index = seen["cmd"].index("--dir") + 1
    scratch_dir = seen["cmd"][dir_index]
    assert scratch_dir != "" and "opencode-bridge-ping-" in scratch_dir
    # the scratch dir must not be (or be inside) a real target repo path
    assert scratch_dir != os.getcwd()


def test_ping_model_propagates_failure_classification(monkeypatch):
    monkeypatch.setattr(
        dispatch, "run_opencode",
        lambda cmd, timeout: dispatch.DispatchOutcome(
            classification="FAILED", reason="unknown model", retryable=False,
        ),
    )
    outcome = dispatch.ping_model(model="bad/model", timeout=5)
    assert outcome.classification == "FAILED"
    assert outcome.reason == "unknown model"


def _init_git_repo(path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=path, check=True)


def _stub_ping_ok(monkeypatch):
    """Make every model pass the pre-dispatch ping check, so existing
    attempt/retry/fallback tests exercise only the real-dispatch path."""
    monkeypatch.setattr(
        dispatch, "ping_model",
        lambda model, timeout: dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],
        ),
    )


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


# --- Task 6: JSON event stream parsing and terminal-state classification ---


def test_parse_events_valid_lines():
    stdout = (
        '{"type":"step_start"}\n'
        '{"type":"text","part":{"text":"hi"}}\n'
        '{"type":"step_finish","part":{"reason":"stop"}}\n'
    )
    events = dispatch.parse_events(stdout, allow_truncated_last_line=False)
    assert len(events) == 3
    assert events[-1]["part"]["reason"] == "stop"


def test_parse_events_truncated_last_line_when_allowed():
    stdout = '{"type":"step_start"}\n{"type":"step_fin'
    events = dispatch.parse_events(stdout, allow_truncated_last_line=True)
    assert len(events) == 1  # truncated line silently dropped


def test_parse_events_malformed_line_raises_when_not_allowed():
    stdout = '{"type":"step_start"}\nnot json at all\n'
    import pytest
    with pytest.raises(dispatch.ProtocolError):
        dispatch.parse_events(stdout, allow_truncated_last_line=False)


def test_has_terminal_stop_event_true():
    events = [{"type": "step_finish", "part": {"reason": "stop"}}]
    assert dispatch.has_terminal_stop_event(events) is True


def test_has_terminal_stop_event_false():
    events = [{"type": "step_start"}]
    assert dispatch.has_terminal_stop_event(events) is False


def test_has_terminal_stop_event_null_part_does_not_crash():
    events = [{"type": "step_finish", "part": None}]
    assert dispatch.has_terminal_stop_event(events) is False


# --- Task 7: Non-retryable vs. retryable failure classification ---


def test_classify_failure_non_retryable_bad_model():
    result = dispatch.classify_failure(exit_code=1, stderr="unknown model: fake/model")
    assert result == "non_retryable"


def test_classify_failure_non_retryable_missing_executable():
    result = dispatch.classify_failure(exit_code=127, stderr="command not found")
    assert result == "non_retryable"


def test_classify_failure_retryable_connection_error():
    result = dispatch.classify_failure(exit_code=1, stderr="connection refused")
    assert result == "retryable"


def test_classify_failure_retryable_rate_limit():
    result = dispatch.classify_failure(exit_code=1, stderr="429 rate limit exceeded")
    assert result == "retryable"


def test_classify_failure_unknown_defaults_to_non_retryable():
    result = dispatch.classify_failure(exit_code=1, stderr="some new error we've never seen")
    assert result == "non_retryable"


# --- Task 8: Subprocess execution with process-group launch and timeout kill ---


class _FakePopen:
    """Stand-in for subprocess.Popen used by run_opencode's tests."""

    def __init__(self, returncode=0, stdout="", stderr="", pid=4242, raise_timeout=False):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.pid = pid
        self._raise_timeout = raise_timeout
        self._communicate_calls = 0

    def communicate(self, timeout=None):
        self._communicate_calls += 1
        if self._raise_timeout and self._communicate_calls == 1:
            raise dispatch.subprocess.TimeoutExpired(cmd=["opencode"], timeout=timeout)
        return self._stdout, self._stderr


def test_run_opencode_success(monkeypatch):
    def fake_popen(cmd, **kwargs):
        assert kwargs.get("start_new_session") is True
        return _FakePopen(returncode=0, stdout='{"type":"step_finish","part":{"reason":"stop"}}\n')

    monkeypatch.setattr(dispatch.subprocess, "Popen", fake_popen)
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "DONE"


def test_run_opencode_timeout_kills_process_group(monkeypatch):
    killed_pgids = []

    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(pid=4242, raise_timeout=True),
    )
    monkeypatch.setattr(dispatch.os, "killpg", lambda pgid, sig: killed_pgids.append(pgid))
    monkeypatch.setattr(dispatch.os, "getpgid", lambda pid: 999 if pid == 4242 else None)
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=1)
    assert outcome.classification == "TIMED_OUT"
    assert killed_pgids == [999]


def test_run_opencode_timeout_is_retryable(monkeypatch):
    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(pid=4242, raise_timeout=True),
    )
    monkeypatch.setattr(dispatch.os, "killpg", lambda pgid, sig: None)
    monkeypatch.setattr(dispatch.os, "getpgid", lambda pid: 999)
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=1)
    assert outcome.retryable is True


def test_run_opencode_nonzero_exit_classifies_failed(monkeypatch):
    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(returncode=1, stdout="", stderr="connection refused"),
    )
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"
    assert outcome.retryable is True


def test_run_opencode_zero_exit_no_terminal_event_is_failed(monkeypatch):
    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(returncode=0, stdout='{"type":"step_start"}\n'),
    )
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"


def test_run_opencode_zero_exit_error_event_is_failed(monkeypatch):
    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(
            returncode=0,
            stdout='{"type":"error","error":{"name":"UnknownError","data":{"message":"Unexpected server error"}}}\n',
        ),
    )
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"
    assert "Unexpected server error" in outcome.reason


def test_run_opencode_zero_exit_non_json_output_is_failed(monkeypatch):
    monkeypatch.setattr(
        dispatch.subprocess, "Popen",
        lambda cmd, **kw: _FakePopen(
            returncode=0,
            stdout="Error: Unexpected error\n\nEACCES: permission denied, lstat '/x'\n",
        ),
    )
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"
    assert outcome.retryable is False


# --- Task 9: Retry + fallback chain orchestration (mutation-guard-aware) ---


def test_dispatch_chain_stops_on_mutation_after_failure(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)

    call_count = {"n": 0}

    def fake_run_opencode(cmd, timeout):
        call_count["n"] += 1
        if call_count["n"] == 1:
            (tmp_path / "partial.txt").write_text("half-done")  # simulate mutation before failure
            return dispatch.DispatchOutcome(classification="FAILED", reason="boom", retryable=True)
        raise AssertionError("should not retry after a mutation")

    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1", "m2"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "FAILED"
    assert call_count["n"] == 1


def test_dispatch_chain_mutation_reports_files_changed(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)

    def fake_run_opencode(cmd, timeout):
        (tmp_path / "partial.txt").write_text("half-done")
        return dispatch.DispatchOutcome(classification="FAILED", reason="boom", retryable=True)

    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert any("partial.txt" in line for line in result.files_changed)


def test_dispatch_chain_retries_same_model_then_advances(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)
    seen_models = []

    def fake_build_command(task, repo, model, session_id):
        seen_models.append(model)
        return ["opencode", "run", task]

    def fake_run_opencode(cmd, timeout):
        n = len(seen_models)
        if n < 3:
            return dispatch.DispatchOutcome(classification="FAILED", reason="conn refused", retryable=True)
        return dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}},
                    {"type": "text", "part": {"text": "done"}}],
        )

    monkeypatch.setattr(dispatch, "build_command", fake_build_command)
    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1", "m2"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "DONE"
    assert seen_models == ["m1", "m1", "m2"]  # m1 tried twice, then m2 succeeds


def test_dispatch_chain_non_retryable_advances_to_fallback_model(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)
    seen_models = []

    def fake_build_command(task, repo, model, session_id):
        seen_models.append(model)
        return ["opencode", "run", task]

    def fake_run_opencode(cmd, timeout):
        if len(seen_models) == 1:
            return dispatch.DispatchOutcome(classification="FAILED", reason="unknown model", retryable=False)
        return dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],
        )

    monkeypatch.setattr(dispatch, "build_command", fake_build_command)
    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["bad/model", "good/model"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "DONE"
    # non-retryable failure on "bad/model" must not be retried, and must advance to "good/model"
    assert seen_models == ["bad/model", "good/model"]


def test_dispatch_chain_exhausted_returns_failed(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)
    monkeypatch.setattr(
        dispatch, "run_opencode",
        lambda cmd, timeout: dispatch.DispatchOutcome(classification="FAILED", reason="conn refused", retryable=True),
    )
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1", "m2"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "FAILED"
    assert "m1" in result.reason and "m2" in result.reason


def test_dispatch_chain_ping_failure_skips_model_without_real_attempt(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    pinged_models = []
    real_attempt_models = []

    def fake_ping_model(model, timeout):
        pinged_models.append(model)
        if model == "bad/model":
            return dispatch.DispatchOutcome(classification="FAILED", reason="unknown model")
        return dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],
        )

    def fake_build_command(task, repo, model, session_id):
        real_attempt_models.append(model)
        return ["opencode", "run", task]

    def fake_run_opencode(cmd, timeout):
        return dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],
        )

    monkeypatch.setattr(dispatch, "ping_model", fake_ping_model)
    monkeypatch.setattr(dispatch, "build_command", fake_build_command)
    monkeypatch.setattr(dispatch, "run_opencode", fake_run_opencode)
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["bad/model", "good/model"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "DONE"
    assert pinged_models == ["bad/model", "good/model"]
    # the failed ping must have prevented any real dispatch attempt against bad/model
    assert real_attempt_models == ["good/model"]


def test_dispatch_chain_all_pings_fail_returns_failed(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    monkeypatch.setattr(
        dispatch, "ping_model",
        lambda model, timeout: dispatch.DispatchOutcome(classification="FAILED", reason="auth error"),
    )
    result = dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1", "m2"], per_attempt_timeout=5, chain_timeout=30,
    )
    assert result.classification == "FAILED"
    assert "m1" in result.reason and "m2" in result.reason


def test_dispatch_chain_does_not_fabricate_session_id(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "sessions.json")
    monkeypatch.setattr(
        dispatch, "run_opencode",
        lambda cmd, timeout: dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}],  # no sessionID anywhere
        ),
    )
    dispatch.dispatch_with_retry(
        task="x", repo=str(tmp_path), topic="t",
        models=["m1"], per_attempt_timeout=5, chain_timeout=30,
    )
    # no sessionID was ever observed and there was no prior session_id -> nothing should be persisted
    assert dispatch.resolve_session(str(tmp_path), "t") is None


# --- Task 10: Handoff report builder ---


def test_build_handoff_report_done_with_test_results():
    outcome = dispatch.DispatchOutcome(
        classification="DONE",
        events=[
            {"type": "text", "part": {"text": "Implemented the thing. Tests: 5/5 passing."}},
            {"type": "step_finish", "part": {"reason": "stop"}},
        ],
    )
    outcome.files_changed = ["M  src/foo.py"]
    report = dispatch.build_handoff_report(outcome, session_id="ses_1")
    assert report["terminal_state"] == "DONE"
    assert report["files_changed"] == ["M  src/foo.py"]
    assert "Implemented the thing" in report["implemented_summary"]
    assert report["session_id"] == "ses_1"


def test_build_handoff_report_no_test_results_says_not_reported():
    outcome = dispatch.DispatchOutcome(
        classification="DONE",
        events=[{"type": "text", "part": {"text": "Implemented the thing."}}],
    )
    outcome.files_changed = []
    report = dispatch.build_handoff_report(outcome, session_id="ses_1")
    assert report["test_results"] == "not reported by OpenCode"


def test_build_handoff_report_failed():
    outcome = dispatch.DispatchOutcome(classification="FAILED", reason="boom")
    report = dispatch.build_handoff_report(outcome, session_id=None)
    assert report["terminal_state"] == "FAILED"
    assert report["issues"] == "boom"


def test_build_handoff_report_mutation_failure_includes_files_changed():
    outcome = dispatch.DispatchOutcome(
        classification="FAILED", reason="stopped after mutation -- boom",
        files_changed=["M  src/foo.py"],
    )
    report = dispatch.build_handoff_report(outcome, session_id=None)
    assert report["files_changed"] == ["M  src/foo.py"]


# --- Task 11: Top-level dispatch() entry point + config loading + CLI wiring ---


def test_dispatch_fails_deterministically_when_config_missing(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(dispatch, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "state" / "sessions.json")
    with pytest.raises(dispatch.ConfigError):
        dispatch.dispatch(task="x", repo=str(tmp_path), topic="t")


def test_dispatch_uses_config_models(tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    _stub_ping_ok(monkeypatch)
    config_path = tmp_path / "config.json"
    dispatch.save_json_file(config_path, {"default_model": "m1", "fallback_models": ["m2"]})
    monkeypatch.setattr(dispatch, "CONFIG_PATH", config_path)
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "state" / "sessions.json")
    monkeypatch.setattr(
        dispatch, "run_opencode",
        lambda cmd, timeout: dispatch.DispatchOutcome(
            classification="DONE",
            events=[{"type": "step_finish", "part": {"reason": "stop"}}, {"sessionID": "ses_x"}],
        ),
    )
    report = dispatch.dispatch(task="x", repo=str(tmp_path), topic="t")
    assert report["terminal_state"] == "DONE"


def test_dispatch_handles_bad_repo_path_gracefully(tmp_path, monkeypatch):
    _stub_ping_ok(monkeypatch)
    config_path = tmp_path / "config.json"
    dispatch.save_json_file(config_path, {"default_model": "m1", "fallback_models": []})
    monkeypatch.setattr(dispatch, "CONFIG_PATH", config_path)
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "state" / "sessions.json")
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    report = dispatch.dispatch(task="x", repo=str(not_a_repo), topic="t")
    assert report["terminal_state"] == "FAILED"
