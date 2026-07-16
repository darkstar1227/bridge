# OpenCode Bridge Skill (Phase 1) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give Claude Code a skill (`/opencode-bridge`) that delegates a coding task to OpenCode and reliably reports back done/failed/timed-out plus a structured handoff report, using OpenCode's own CLI capabilities instead of custom polling/HTTP/registry infrastructure.

**Architecture:** A single Python helper (`skills/opencode-bridge/scripts/dispatch.py`, invoked via `uv run`) wraps `opencode run --format json --session <id> -m <model> --dir <repo>` as a subprocess in its own process group. It classifies the outcome from the JSON event stream and exit code, guards against unsafe automatic retries once files have been mutated, retries/falls back across a configured model chain only for safe/transient failures, and builds a structured handoff report. A `SKILL.md` layer handles the one thing the script can't do itself: interactive first-run configuration via AskUserQuestion.

**Tech Stack:** Python (PEP 723 inline script metadata, `uv run`, `filelock` dependency), OpenCode CLI (`opencode run --format json`), `git status --porcelain --untracked-files=all` for mutation/files-changed detection, pytest for tests.

---

## Reference material

- Source design: `~/.gstack/projects/darkstar1227-bridge/ds-anxing-main-design-20260714-201742.md` (fully reviewed — 13 eng-review findings + 11 outside-voice tensions resolved, 2 empirical unknowns verified live).
- Handoff spec: `docs/superpowers/input/gstack-handoff-2026-07-15-opencode-bridge.md`.
- Test plan artifact: `~/.gstack/projects/darkstar1227-bridge/ds-anxing-main-eng-review-test-plan-20260715-123635.md`.
- This repo's skill conventions: `@CLAUDE.md` — read the "Adding a new skill" and "Python scripts" sections before Task 11.
- An existing skill for frontmatter/structure reference: `@skills/init-project/SKILL.md`.

---

### Task 1: Investigate OpenCode's real failure-mode JSON/exit shapes

This is a research task, not a TDD task — its output (concrete error shapes) is required input for Task 8's classifier. Do not guess; run these against the locally installed `opencode` (v1.17.15 confirmed present).

**Files:** none (research only — record findings as a comment block at the top of `skills/opencode-bridge/scripts/dispatch.py` once created in Task 2, or in a scratch note for now).

**Step 1: Induce a bad model name**

Run: `opencode run "say hi" --format json -m does-not-exist/fake-model --dir /tmp 2>&1 | tail -20`
Record: exit code (`echo $?`), whether any JSON event is emitted, and the exact stderr text.

**Step 2: Induce an auth failure**

If a provider's credentials can be temporarily invalidated safely (e.g. via an env var override for that single command, `ANTHROPIC_API_KEY=invalid opencode run ...` for an Anthropic-backed model), run it and record exit code + output shape. Skip this step if no safe way to induce it exists in this environment — note the skip explicitly, do not fabricate a result.

**Step 3: Induce a missing-executable case**

Run: `PATH=/nonexistent opencode run "say hi" --format json --dir /tmp 2>&1; echo "EXIT: $?"` (this actually tests the *caller's* handling of `FileNotFoundError` from Python, not OpenCode's own behavior — note this distinction).

**Step 4: Induce a permission-denied case**

Run against a directory the current user can't write to, e.g. `opencode run "create a file" --format json --dir /private/var/root 2>&1; echo "EXIT: $?"` (adjust to a real permission-denied path on this machine).

**Step 5: Record findings**

Write a short markdown note (can live as a code comment in Task 2's `dispatch.py`, in the `# Non-retryable failure detection` section) mapping each induced case to: exit code, JSON event shape (if any), and which string/pattern in stderr or the JSON reliably identifies it. This directly feeds Task 8.

---

### Task 2: Config and state file I/O (load/save, atomic writes, quarantine-on-corrupt)

**Files:**
- Create: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
# skills/opencode-bridge/scripts/tests/test_dispatch.py
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
```

**Step 2: Run tests to verify they fail**

Run: `cd skills/opencode-bridge/scripts && uv run pytest tests/test_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError` or `AttributeError: module 'dispatch' has no attribute 'load_json_file'` (dispatch.py doesn't exist yet).

**Step 3: Write minimal implementation**

```python
# skills/opencode-bridge/scripts/dispatch.py
# /// script
# dependencies = ["filelock"]
# ///
"""OpenCode bridge dispatch helper. Invoked via `uv run dispatch.py`."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from filelock import FileLock

STATE_DIR = Path.home() / ".opencode-bridge"
CONFIG_PATH = STATE_DIR / "config.json"
SESSIONS_PATH = STATE_DIR / "state" / "sessions.json"


def load_json_file(path: Path, default):
    """Load JSON from path. Missing -> default. Corrupt -> quarantine + default."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        quarantine_path = path.with_name(f"{path.name}.corrupt-{timestamp}")
        path.rename(quarantine_path)
        return default


def save_json_file(path: Path, data) -> None:
    """Write JSON to path via temp-file + atomic rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.tmp-", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise
```

**Step 4: Run tests to verify they pass**

Run: `cd skills/opencode-bridge/scripts && uv run pytest tests/test_dispatch.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add config/state JSON I/O with atomic writes and corrupt-file quarantine"
```

---

### Task 3: Session mapping resolution (repo,topic)->session_id, mismatch-safe

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k resolve_session or update_session_mapping`
Expected: FAIL — `AttributeError: module 'dispatch' has no attribute 'resolve_session'`

**Step 3: Write minimal implementation**

```python
def _session_key(repo: str, topic: str) -> str:
    return f"{repo}::{topic}"


def resolve_session(repo: str, topic: str) -> str | None:
    """Look up a session_id for (repo, topic). Never returns a session_id
    for a different (repo, topic) — a key mismatch is treated as no session,
    since cross-context session reuse has been observed to hang OpenCode."""
    lock = FileLock(str(SESSIONS_PATH) + ".lock")
    with lock:
        mapping = load_json_file(SESSIONS_PATH, default={})
    return mapping.get(_session_key(repo, topic))


def update_session_mapping(repo: str, topic: str, session_id: str) -> None:
    lock = FileLock(str(SESSIONS_PATH) + ".lock")
    with lock:
        mapping = load_json_file(SESSIONS_PATH, default={})
        mapping[_session_key(repo, topic)] = session_id
        save_json_file(SESSIONS_PATH, mapping)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (8 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add (repo,topic)->session_id mapping resolution"
```

---

### Task 4: Command construction (always includes --dir and --session/-m)

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k build_command`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
def build_command(task: str, repo: str, model: str, session_id: str | None) -> list[str]:
    cmd = ["opencode", "run", task, "--format", "json", "-m", model, "--dir", repo]
    if session_id:
        cmd += ["--session", session_id]
    return cmd
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (10 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add opencode CLI command construction with --dir/--session"
```

---

### Task 5: Git status snapshot + diff (mutation-guard / files-changed)

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
import subprocess


def _init_git_repo(path):
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k snapshot`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
def git_status_snapshot(repo: str) -> set[str]:
    """Snapshot of `git status --porcelain --untracked-files=all` lines,
    run with cwd=repo (must match the --dir passed to opencode)."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return set(line for line in result.stdout.splitlines() if line.strip())


def diff_snapshots(before: set[str], after: set[str]) -> set[str]:
    """Lines present after dispatch that weren't present before — this is
    both the mutation-guard signal and the files-changed report content."""
    return after - before
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (14 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add git-status-based mutation-guard and files-changed detection"
```

---

### Task 6: JSON event stream parsing and terminal-state classification

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k "parse_events or terminal_stop"`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
class ProtocolError(Exception):
    """A JSON line failed to parse outside the expected forced-kill truncation case."""


def parse_events(stdout: str, allow_truncated_last_line: bool) -> list[dict]:
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    events = []
    for i, line in enumerate(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            is_last = i == len(lines) - 1
            if allow_truncated_last_line and is_last:
                continue  # expected truncation on timeout/kill
            raise ProtocolError(f"unparseable JSON line (not a kill-truncation case): {line!r}")
    return events


def has_terminal_stop_event(events: list[dict]) -> bool:
    return any(
        e.get("type") == "step_finish" and e.get("part", {}).get("reason") == "stop"
        for e in events
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (19 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add JSON event parsing with kill-truncation-aware error handling"
```

---

### Task 7: Non-retryable vs. retryable failure classification

Use the concrete findings from Task 1's investigation to fill in the pattern-matching below — do not guess if Task 1 found different strings than shown here; use what was actually observed.

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
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
    # Safer default: an unrecognized failure should NOT be blindly retried.
    result = dispatch.classify_failure(exit_code=1, stderr="some new error we've never seen")
    assert result == "non_retryable"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k classify_failure`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

Update the patterns below with whatever Task 1 actually observed before finalizing this step.

```python
_NON_RETRYABLE_PATTERNS = [
    "unknown model", "invalid model", "model not found",
    "unauthorized", "auth", "authentication",
    "command not found", "no such file or directory",
    "permission denied",
]
_RETRYABLE_PATTERNS = [
    "connection refused", "connection reset", "econnrefused",
    "timed out", "timeout",
    "rate limit", "429", "too many requests",
]


def classify_failure(exit_code: int, stderr: str) -> str:
    """Returns 'non_retryable' or 'retryable'. Defaults to non_retryable
    for unrecognized failures — safer than blindly retrying an unknown
    error class."""
    lowered = stderr.lower()
    if exit_code == 127:
        return "non_retryable"
    for pattern in _RETRYABLE_PATTERNS:
        if pattern in lowered:
            return "retryable"
    for pattern in _NON_RETRYABLE_PATTERNS:
        if pattern in lowered:
            return "non_retryable"
    return "non_retryable"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (24 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add non-retryable/retryable failure classification"
```

---

### Task 8: Subprocess execution with process-group launch and timeout kill

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
def test_run_opencode_success(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = '{"type":"step_finish","part":{"reason":"stop"}}\n'
        stderr = ""

    def fake_run(cmd, **kwargs):
        assert kwargs.get("start_new_session") is True
        return FakeCompleted()

    monkeypatch.setattr(dispatch.subprocess, "run", fake_run)
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "DONE"


def test_run_opencode_timeout_kills_process_group(monkeypatch):
    killed_pgids = []

    def fake_run(cmd, **kwargs):
        raise dispatch.subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    def fake_killpg(pgid, sig):
        killed_pgids.append(pgid)

    monkeypatch.setattr(dispatch.subprocess, "run", fake_run)
    monkeypatch.setattr(dispatch.os, "killpg", fake_killpg)
    monkeypatch.setattr(dispatch.os, "getpgid", lambda pid: 999)
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=1)
    assert outcome.classification == "TIMED_OUT"
    assert killed_pgids == [999]


def test_run_opencode_nonzero_exit_classifies_failed(monkeypatch):
    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = "connection refused"

    monkeypatch.setattr(dispatch.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"
    assert outcome.retryable is True


def test_run_opencode_zero_exit_no_terminal_event_is_failed(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = '{"type":"step_start"}\n'
        stderr = ""

    monkeypatch.setattr(dispatch.subprocess, "run", lambda cmd, **kw: FakeCompleted())
    outcome = dispatch.run_opencode(["opencode", "run", "x"], timeout=5)
    assert outcome.classification == "FAILED"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k run_opencode`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
import signal
import subprocess
from dataclasses import dataclass, field


@dataclass
class DispatchOutcome:
    classification: str  # "DONE" | "FAILED" | "TIMED_OUT"
    reason: str = ""
    retryable: bool = False
    events: list = field(default_factory=list)


def run_opencode(cmd: list[str], timeout: float) -> DispatchOutcome:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as exc:
        pid = getattr(exc, "pid", None)
        if pid is not None:
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return DispatchOutcome(classification="TIMED_OUT", reason="timeout elapsed, process group killed")

    if result.returncode != 0:
        retryable = classify_failure(result.returncode, result.stderr) == "retryable"
        return DispatchOutcome(
            classification="FAILED", reason=result.stderr.strip() or f"exit code {result.returncode}",
            retryable=retryable,
        )

    events = parse_events(result.stdout, allow_truncated_last_line=False)
    if not has_terminal_stop_event(events):
        return DispatchOutcome(
            classification="FAILED",
            reason="process exited zero but no terminal step_finish/stop event found",
            retryable=False, events=events,
        )
    return DispatchOutcome(classification="DONE", events=events)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (28 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add subprocess execution with process-group timeout kill and classification"
```

---

### Task 9: Retry + fallback chain orchestration (mutation-guard-aware)

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
def test_dispatch_chain_stops_on_mutation_after_failure(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)

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


def test_dispatch_chain_retries_same_model_then_advances(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
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


def test_dispatch_chain_exhausted_returns_failed(monkeypatch, tmp_path):
    _init_git_repo(tmp_path)
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k dispatch_chain`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
import uuid


def dispatch_with_retry(task, repo, topic, models, per_attempt_timeout, chain_timeout):
    start = time.monotonic()
    failure_reasons = []
    mapping_session_id = resolve_session(repo, topic)

    for model_index, model in enumerate(models):
        session_id = mapping_session_id if model_index == 0 else None
        for attempt in range(2):  # original attempt + one retry, per model
            if time.monotonic() - start > chain_timeout:
                return DispatchOutcome(
                    classification="FAILED",
                    reason=f"chain-level timeout exceeded; failures so far: {failure_reasons}",
                )
            before = git_status_snapshot(repo)
            cmd = build_command(task=task, repo=repo, model=model, session_id=session_id)
            outcome = run_opencode(cmd, timeout=per_attempt_timeout)

            if outcome.classification == "DONE":
                new_session_id = _extract_session_id(outcome.events) or session_id or str(uuid.uuid4())
                update_session_mapping(repo, topic, new_session_id)
                after = git_status_snapshot(repo)
                outcome.files_changed = sorted(diff_snapshots(before, after))
                return outcome

            after = git_status_snapshot(repo)
            mutated = bool(diff_snapshots(before, after))
            failure_reasons.append(f"{model}: {outcome.reason}")

            if mutated:
                outcome.reason = f"stopped after mutation — {outcome.reason}"
                return outcome
            if not outcome.retryable:
                return outcome
            # retryable + clean tree: retry same model once with a fresh session
            session_id = None  # fresh temp session for the retry attempt

    return DispatchOutcome(
        classification="FAILED",
        reason=f"all models exhausted: {'; '.join(failure_reasons)}",
    )


def _extract_session_id(events: list[dict]) -> str | None:
    for e in events:
        sid = e.get("sessionID")
        if sid:
            return sid
    return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (31 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add mutation-guarded retry/fallback chain with per-attempt and chain-level timeouts"
```

---

### Task 10: Handoff report builder

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k build_handoff_report`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
import re


def build_handoff_report(outcome: DispatchOutcome, session_id: str | None) -> dict:
    if outcome.classification != "DONE":
        return {
            "terminal_state": outcome.classification,
            "issues": outcome.reason,
            "files_changed": getattr(outcome, "files_changed", []),
            "session_id": session_id,
        }

    final_text = ""
    for e in outcome.events:
        if e.get("type") == "text":
            final_text = e.get("part", {}).get("text", final_text)

    test_match = re.search(r"tests?[:\s]+\d+/\d+\s+passing", final_text, re.IGNORECASE)
    test_results = test_match.group(0) if test_match else "not reported by OpenCode"

    return {
        "terminal_state": "DONE",
        "implemented_summary": final_text,
        "files_changed": getattr(outcome, "files_changed", []),
        "test_results": test_results,
        "self_review_notes": "not reported by OpenCode",
        "session_id": session_id,
    }
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (34 tests total)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add structured handoff report builder"
```

---

### Task 11: Top-level dispatch() entry point + config loading + CLI wiring

**Files:**
- Modify: `skills/opencode-bridge/scripts/dispatch.py`
- Test: `skills/opencode-bridge/scripts/tests/test_dispatch.py`

**Step 1: Write the failing tests**

```python
def test_dispatch_fails_deterministically_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(dispatch, "SESSIONS_PATH", tmp_path / "state" / "sessions.json")
    with pytest.raises(dispatch.ConfigError):
        dispatch.dispatch(task="x", repo=str(tmp_path), topic="t")


def test_dispatch_uses_config_models(tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dispatch.py -v -k "test_dispatch_"`
Expected: FAIL — `AttributeError`

**Step 3: Write minimal implementation**

```python
class ConfigError(Exception):
    """Config is missing or malformed — caller must re-run SKILL.md-level setup."""


def dispatch(task: str, repo: str, topic: str) -> dict:
    config = load_json_file(CONFIG_PATH, default=None)
    if config is None or "default_model" not in config:
        raise ConfigError(
            "config missing or invalid at ~/.opencode-bridge/config.json — "
            "re-run the SKILL.md first-run setup flow"
        )
    models = [config["default_model"]] + config.get("fallback_models", [])
    per_attempt_timeout = config.get("per_attempt_timeout_seconds", 300)
    chain_timeout = config.get("chain_timeout_seconds", 600)

    outcome = dispatch_with_retry(
        task=task, repo=repo, topic=topic, models=models,
        per_attempt_timeout=per_attempt_timeout, chain_timeout=chain_timeout,
    )
    session_id = resolve_session(repo, topic)
    return build_handoff_report(outcome, session_id=session_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args()
    try:
        report = dispatch(task=args.task, repo=args.repo, topic=args.topic)
    except ConfigError as exc:
        print(json.dumps({"terminal_state": "CONFIG_ERROR", "issues": str(exc)}))
        raise SystemExit(1)
    print(json.dumps(report, indent=2))
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (36 tests total, full suite green)

**Step 5: Commit**

```bash
git add skills/opencode-bridge/scripts/dispatch.py skills/opencode-bridge/scripts/tests/test_dispatch.py
git commit -m "feat: add top-level dispatch() entry point and CLI wiring"
```

---

### Task 12: SKILL.md — interactive first-run setup + outer timeout wrapper

Read `@CLAUDE.md`'s "Adding a new skill" section and an existing skill (e.g. `@skills/init-project/SKILL.md`) for frontmatter conventions before writing this.

**Files:**
- Create: `skills/opencode-bridge/SKILL.md`

**Step 1: Write the SKILL.md frontmatter and instructions**

```markdown
---
name: opencode-bridge
description: Delegate a coding task to OpenCode and get back a structured handoff report (done/failed/timed-out, files changed, implementation summary) — for use as an OpenCode-backed implementer step in subagent-driven-development or executing-plans.
allowed-tools:
  - Bash
  - AskUserQuestion
triggers:
  - delegate to opencode
  - use opencode for this task
  - opencode bridge
---

# OpenCode Bridge

## Step 1: Check config

Run:
\`\`\`bash
test -f ~/.opencode-bridge/config.json && echo EXISTS || echo MISSING
cat ~/.opencode-bridge/config.json 2>/dev/null
\`\`\`

If `MISSING`, or if the file exists but fails to parse as JSON: ask the user via AskUserQuestion for:
- Default model (`provider/model` format, e.g. `opencode/kimi-k2.7-code` — list available models with `opencode models` if the user wants to see options)
- Fallback model list (ordered, can be empty)
- Per-attempt timeout in seconds (default suggestion: 300)
- Chain-level timeout in seconds (default suggestion: 600 — must be greater than per-attempt timeout)

Write the answers to `~/.opencode-bridge/config.json`:
\`\`\`json
{
  "default_model": "<answer>",
  "fallback_models": ["<answer>", "..."],
  "per_attempt_timeout_seconds": <answer>,
  "chain_timeout_seconds": <answer>
}
\`\`\`

Do this only once — do not re-ask on subsequent invocations once the file exists and parses.

## Step 2: Dispatch

Run (substituting the actual task description, target repo absolute path, and a short topic string identifying this line of work — e.g. the feature/branch name):

\`\`\`bash
timeout <chain_timeout_seconds + 30> uv run skills/opencode-bridge/scripts/dispatch.py \
  --task "<task description>" --repo "<absolute repo path>" --topic "<topic>"
\`\`\`

The outer `timeout` value must exceed the configured `chain_timeout_seconds` — it exists so that if Claude's own Bash tool call is itself cancelled or times out, the OpenCode process group still gets reaped rather than surviving as an orphan.

## Step 3: Handle the result

Parse the JSON handoff report from stdout.

- If `terminal_state` is `DONE`: present `implemented_summary`, `files_changed`, and `test_results` to the user/calling workflow. This report can be handed directly to `subagent-driven-development`'s `spec-reviewer-prompt.md` step.
- If `terminal_state` is `FAILED` or `TIMED_OUT`: present `issues` and any partial `files_changed`. If the failure happened after files were mutated, say so explicitly and do not automatically retry — ask the user how to proceed (continue manually, discard partial edits, or something else).
- If `terminal_state` is `CONFIG_ERROR`: re-run Step 1.
```

**Step 2: Manual verification**

Run: `rm -f ~/.opencode-bridge/config.json` then invoke the skill in a real Claude Code session; confirm the setup prompt appears exactly once and the config file is written. Invoke a second time and confirm no re-prompt.

**Step 3: Commit**

```bash
git add skills/opencode-bridge/SKILL.md
git commit -m "feat: add opencode-bridge SKILL.md with interactive first-run setup"
```

---

### Task 13: Repo metadata updates

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `README.md`

**Step 1: Bump plugin version**

Open `.claude-plugin/plugin.json`, bump the `version` field per this repo's existing semver convention (check recent git log for the last bump pattern with `git log --oneline -- .claude-plugin/plugin.json | head -5`).

**Step 2: Update README**

Add a section to `README.md` describing the `opencode-bridge` skill: what it does (delegate a coding task to OpenCode, get back done/failed/timed-out + a structured handoff report), and how to invoke it. Follow the existing README's format for documenting other skills in this repo.

**Step 3: Commit**

```bash
git add .claude-plugin/plugin.json README.md
git commit -m "chore: bump plugin version and document opencode-bridge skill"
```

---

## Explicit Assumptions carried from the handoff spec

- [ASSUMPTION] Skill name is `opencode-bridge` / invocation `/opencode-bridge` — not finalized upstream; confirm before Task 12 if the user has a different naming preference.
- [ASSUMPTION] `~/.opencode-bridge/` as the state directory name doesn't conflict with anything else on the user's machine — not verified.
- [OPEN, feeds Task 7] Exact non-retryable/retryable string patterns in `_NON_RETRYABLE_PATTERNS`/`_RETRYABLE_PATTERNS` must be corrected against Task 1's actual findings before Task 7 is considered done — the patterns shown in Task 7 are reasonable placeholders, not verified against real OpenCode output.
