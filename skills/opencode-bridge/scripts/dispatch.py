# /// script
# dependencies = ["filelock"]
# ///
"""OpenCode bridge dispatch helper. Invoked via `uv run dispatch.py`.

# Task 1 investigation findings (opencode v1.17.15, macOS)
#
# Bad model name (`-m does-not-exist/fake-model`):
#   exit code 0. Stdout is valid JSON, one line:
#   {"type":"error","timestamp":...,"sessionID":"ses_...",
#    "error":{"name":"UnknownError","data":{"message":"Unexpected server error...","ref":"err_..."}}}
#
# Auth failure (`ANTHROPIC_API_KEY=invalid`, real model):
#   Same shape as above: exit 0, one JSON line with "type":"error".
#
# Missing opencode executable (`PATH=/nonexistent opencode run ...`):
#   exit 127, shell-level "command not found" -- this is really testing the
#   *caller's* handling of Python's FileNotFoundError, not OpenCode's own
#   output shape (per Task 1 Step 3 note).
#
# Permission-denied `--dir` (e.g. /private/var/root):
#   exit code 0. Output is NOT JSON at all -- ANSI-colored plain text:
#   "Error: Unexpected error\n\nEACCES: permission denied, lstat '...'"
#
# Conclusion: exit code alone does not indicate failure -- OpenCode returns 0
# even for bad-model/auth failures. The reliable failure signal is a parsed
# JSON event with "type":"error", or (when no valid JSON is present at all)
# plain-text output containing an error marker. classify_failure() must be
# given this text (JSON error message, or raw stdout+stderr) rather than only
# `stderr`, and run_opencode()/parse_events() must treat "no valid JSON found"
# as a classifiable failure case, not a ProtocolError.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
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


def _session_key(repo: str, topic: str) -> str:
    return f"{repo}::{topic}"


def resolve_session(repo: str, topic: str) -> str | None:
    """Look up a session_id for (repo, topic). Never returns a session_id
    for a different (repo, topic) -- a key mismatch is treated as no session,
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


def build_command(task: str, repo: str, model: str, session_id: str | None) -> list[str]:
    cmd = ["opencode", "run", task, "--format", "json", "-m", model, "--dir", repo]
    if session_id:
        cmd += ["--session", session_id]
    return cmd


def build_ping_command(model: str, scratch_dir: str) -> list[str]:
    return [
        "opencode", "run",
        "Reply with exactly the word OK. Do not read or write any files.",
        "--format", "json", "-m", model, "--dir", scratch_dir,
    ]


def ping_model(model: str, timeout: float) -> "DispatchOutcome":
    """Cheap reachability/auth check for a model, run before committing to a
    full dispatch attempt -- catches a dead/misconfigured model without
    burning the (much longer) per-attempt timeout on it. Runs in a throwaway
    directory, never the target repo, so a misbehaving model has nothing to
    touch."""
    with tempfile.TemporaryDirectory(prefix="opencode-bridge-ping-") as scratch_dir:
        cmd = build_ping_command(model, scratch_dir)
        return run_opencode(cmd, timeout=timeout)


def git_status_snapshot(repo: str) -> set[str]:
    """Snapshot of `git status --porcelain --untracked-files=all` lines,
    run with cwd=repo (must match the --dir passed to opencode)."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return set(line for line in result.stdout.splitlines() if line.strip())


def diff_snapshots(before: set[str], after: set[str]) -> set[str]:
    """Lines present after dispatch that weren't present before -- this is
    both the mutation-guard signal and the files-changed report content."""
    return after - before


class ProtocolError(Exception):
    """No valid JSON could be parsed from the output at all (outside the
    expected forced-kill truncation case). Callers should fall back to
    classifying the raw text (see Task 1 findings re: permission-denied)."""


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
        e.get("type") == "step_finish" and (e.get("part") or {}).get("reason") == "stop"
        for e in events
    )


def find_error_event(events: list[dict]) -> dict | None:
    """First {"type":"error"} event, if any -- OpenCode's real failure signal
    (see module docstring: exit code stays 0 for these)."""
    for e in events:
        if e.get("type") == "error":
            return e
    return None


def _error_event_message(error_event: dict) -> str:
    error = error_event.get("error") or {}
    data = error.get("data") or {}
    message = data.get("message") or error.get("name") or "unknown error"
    return str(message)


_NON_RETRYABLE_PATTERNS = [
    "unknown model", "invalid model", "model not found",
    "unauthorized", "auth", "authentication",
    "command not found", "no such file or directory",
    "permission denied", "eacces",
]
_RETRYABLE_PATTERNS = [
    "connection refused", "connection reset", "econnrefused",
    "timed out", "timeout",
    "rate limit", "429", "too many requests",
]


def classify_failure(exit_code: int, stderr: str) -> str:
    """Returns 'non_retryable' or 'retryable'. `stderr` here is really "the
    best available failure text" -- may be actual stderr, an extracted JSON
    error-event message, or raw stdout when no JSON was parseable at all
    (see module docstring). Defaults to non_retryable for unrecognized
    failures -- safer than blindly retrying an unknown error class."""
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


@dataclass
class DispatchOutcome:
    classification: str  # "DONE" | "FAILED" | "TIMED_OUT"
    reason: str = ""
    retryable: bool = False
    events: list = field(default_factory=list)
    files_changed: list = field(default_factory=list)


def run_opencode(cmd: list[str], timeout: float) -> DispatchOutcome:
    # Popen (not subprocess.run) so we retain the pid for a process-group kill
    # on timeout -- subprocess.run's own TimeoutExpired never carries .pid,
    # which would make the kill unreachable (verified empirically: a real
    # TimeoutExpired instance has no `pid` attribute at all).
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()  # reap the now-killed process
        return DispatchOutcome(
            classification="TIMED_OUT", reason="timeout elapsed, process group killed",
            retryable=True,
        )

    returncode = proc.returncode

    # Parse whatever JSON events we can find. A total parse failure (e.g. the
    # permission-denied case, which emits plain ANSI text, no JSON at all) is
    # not a ProtocolError here -- it's classified from the raw text instead.
    try:
        events = parse_events(stdout, allow_truncated_last_line=False)
    except ProtocolError:
        events = []

    error_event = find_error_event(events)
    if error_event is not None:
        message = _error_event_message(error_event)
        retryable = classify_failure(returncode, message) == "retryable"
        return DispatchOutcome(
            classification="FAILED", reason=message, retryable=retryable, events=events,
        )

    if not events:
        raw_text = (stdout or "") + (stderr or "")
        if raw_text.strip():
            retryable = classify_failure(returncode, raw_text) == "retryable"
            return DispatchOutcome(
                classification="FAILED",
                reason=raw_text.strip(),
                retryable=retryable,
            )

    if returncode != 0:
        retryable = classify_failure(returncode, stderr) == "retryable"
        return DispatchOutcome(
            classification="FAILED", reason=(stderr or "").strip() or f"exit code {returncode}",
            retryable=retryable,
        )

    if not has_terminal_stop_event(events):
        return DispatchOutcome(
            classification="FAILED",
            reason="process exited zero but no terminal step_finish/stop event found",
            retryable=False, events=events,
        )
    return DispatchOutcome(classification="DONE", events=events)


def _extract_session_id(events: list[dict]) -> str | None:
    for e in events:
        sid = e.get("sessionID")
        if sid:
            return sid
    return None


def dispatch_with_retry(task, repo, topic, models, per_attempt_timeout, chain_timeout, ping_timeout=30):
    start = time.monotonic()
    failure_reasons = []
    mapping_session_id = resolve_session(repo, topic)

    for model_index, model in enumerate(models):
        if time.monotonic() - start > chain_timeout:
            return DispatchOutcome(
                classification="FAILED",
                reason=f"chain-level timeout exceeded; failures so far: {failure_reasons}",
            )

        ping_outcome = ping_model(model, timeout=ping_timeout)
        if ping_outcome.classification != "DONE":
            failure_reasons.append(f"{model}: ping failed -- {ping_outcome.reason}")
            continue  # dead/misconfigured model -- skip straight to the next fallback

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
                new_session_id = _extract_session_id(outcome.events) or session_id
                if new_session_id:
                    update_session_mapping(repo, topic, new_session_id)
                after = git_status_snapshot(repo)
                outcome.files_changed = sorted(diff_snapshots(before, after))
                return outcome

            after = git_status_snapshot(repo)
            changed = diff_snapshots(before, after)
            mutated = bool(changed)
            failure_reasons.append(f"{model}: {outcome.reason}")

            if mutated:
                outcome.reason = f"stopped after mutation -- {outcome.reason}"
                outcome.files_changed = sorted(changed)
                return outcome
            if not outcome.retryable:
                break  # non-retryable: stop retrying this model, advance to the next
            # retryable + clean tree: retry same model once with a fresh session
            session_id = None  # fresh temp session for the retry attempt

    return DispatchOutcome(
        classification="FAILED",
        reason=f"all models exhausted: {'; '.join(failure_reasons)}",
    )


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
            final_text = (e.get("part") or {}).get("text", final_text)

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


class ConfigError(Exception):
    """Config is missing or malformed -- caller must re-run SKILL.md-level setup."""


def dispatch(task: str, repo: str, topic: str) -> dict:
    config = load_json_file(CONFIG_PATH, default=None)
    if config is None or "default_model" not in config:
        raise ConfigError(
            "config missing or invalid at ~/.opencode-bridge/config.json -- "
            "re-run the SKILL.md first-run setup flow"
        )
    models = [config["default_model"]] + config.get("fallback_models", [])
    per_attempt_timeout = config.get("per_attempt_timeout_seconds", 300)
    chain_timeout = config.get("chain_timeout_seconds", 600)
    ping_timeout = config.get("ping_timeout_seconds", 30)

    try:
        outcome = dispatch_with_retry(
            task=task, repo=repo, topic=topic, models=models,
            per_attempt_timeout=per_attempt_timeout, chain_timeout=chain_timeout,
            ping_timeout=ping_timeout,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        outcome = DispatchOutcome(
            classification="FAILED",
            reason=f"could not run git status against --repo {repo!r}: {exc}",
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
