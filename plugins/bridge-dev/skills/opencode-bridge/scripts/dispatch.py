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
import logging
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from filelock import FileLock

logger = logging.getLogger("opencode_bridge.dispatch")
if not logger.handlers:
    # dispatch.py is used both as an importable module (smoke_test.py) and as
    # a standalone `uv run dispatch.py` CLI -- attach a default stderr handler
    # here so progress messages are visible either way, since callers that
    # only import this module have no reason to configure logging themselves.
    _handler = logging.StreamHandler()  # defaults to sys.stderr
    _handler.setFormatter(logging.Formatter("%(asctime)s [dispatch] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

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


ROTATION_PATH = STATE_DIR / "state" / "provider_rotation.json"


def _provider_of(model: str) -> str:
    """First path segment of a model slug is its provider, e.g.
    "opencode-go/kimi-k2.6" -> "opencode-go", "openrouter/tencent/hy3:free"
    -> "openrouter"."""
    return model.split("/", 1)[0]


def _group_by_provider(models: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for m in models:
        groups.setdefault(_provider_of(m), []).append(m)
    return groups


def _next_rotation_start(providers: list[str]) -> int:
    """Persisted round-robin pointer so consecutive dispatch() calls don't
    all start on the same provider -- spreads load across providers over
    time instead of every call hammering the same one first."""
    lock = FileLock(str(ROTATION_PATH) + ".lock")
    with lock:
        state = load_json_file(ROTATION_PATH, default={"last_index": -1})
        start = (state.get("last_index", -1) + 1) % len(providers)
        save_json_file(ROTATION_PATH, {"last_index": start})
        return start


def rotate_models_by_provider(models: list[str]) -> list[str]:
    """Reorders the model chain to spread load across providers instead of
    exhausting one provider's rate limit before ever trying another:

    1. Round-robins which provider leads *this* call, persisted across
       calls via ROTATION_PATH -- repeated dispatch() calls cycle through
       providers rather than always starting on the same one.
    2. Within the resulting chain, interleaves providers round-robin (one
       model per provider per round) so a rate-limited provider's fallback
       models aren't retried back-to-back -- same-provider repeats only
       cluster once every other provider's models are exhausted.

    Relative order within each provider (i.e. score ranking from config)
    is preserved; only the interleaving across providers changes."""
    groups = _group_by_provider(models)
    providers = list(groups.keys())
    if len(providers) <= 1:
        return models
    start = _next_rotation_start(providers)
    rotated_providers = providers[start:] + providers[:start]
    chain = []
    round_idx = 0
    while len(chain) < len(models):
        for p in rotated_providers:
            bucket = groups[p]
            if round_idx < len(bucket):
                chain.append(bucket[round_idx])
        round_idx += 1
    return chain


RUN_LOG_DIR = STATE_DIR / "state" / "runs"


def _slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


def run_log_path_for(repo: str, topic: str, model: str) -> Path:
    """Deterministic-ish path so a caller can predict it and `tail -f` (or
    hand it to the Monitor tool) before/while the attempt is running.
    Timestamped so retries/re-runs against the same (repo, topic, model)
    don't clobber each other's log."""
    name = f"{_slugify(topic)}__{_slugify(model)}__{int(time.time())}.jsonl"
    return RUN_LOG_DIR / _slugify(repo) / name


HEALTH_PATH = STATE_DIR / "state" / "health.json"

# Consecutive ambiguous (timeout/rate-limit/generic) failures before a single
# model gets disabled on its own.
MODEL_FAIL_THRESHOLD = 2
# How many distinct models under the same provider have to be simultaneously
# struggling (>= MODEL_FAIL_THRESHOLD each) before we stop disabling them one
# by one and conclude it's an account-wide problem (quota/rate limit) --
# disabling the whole provider instead.
PROVIDER_ESCALATION_COUNT = 2
MODEL_COOLDOWN_SECONDS = 2 * 3600
PROVIDER_COOLDOWN_SECONDS = 6 * 3600

# Explicit text markers that unambiguously identify *which* level broke,
# independent of the retry-count heuristic above.
_MODEL_LEVEL_MARKERS = [
    "unknown model", "invalid model", "model not found",
    "unavailable for free", "does not exist",
]
_PROVIDER_LEVEL_MARKERS = [
    "unauthorized", "authentication", "auth failed",
    "invalid api key", "invalid_api_key",
]


def _load_health() -> dict:
    return load_json_file(HEALTH_PATH, default={"models": {}, "providers": {}})


def _save_health(health: dict) -> None:
    save_json_file(HEALTH_PATH, health)


def _entry_is_active(entry: dict | None) -> bool:
    if not entry or not entry.get("disabled"):
        return False
    until = entry.get("disabled_until")
    return until is None or time.time() < until  # None == permanent


def is_model_disabled(model: str) -> tuple[bool, str]:
    """Checks both this model's own disable entry and its provider's --
    a provider-level disable overrides every model under it, since the
    provider itself (not any one model) is the thing that's broken."""
    health = _load_health()
    provider = _provider_of(model)
    p_entry = health["providers"].get(provider)
    if _entry_is_active(p_entry):
        return True, f"provider '{provider}' disabled -- {p_entry.get('reason')}"
    m_entry = health["models"].get(model)
    if _entry_is_active(m_entry):
        return True, f"model disabled -- {m_entry.get('reason')}"
    return False, ""


def record_health_success(model: str) -> None:
    """Live proof the model (and by extension its provider's credentials)
    work right now -- clears any disable on both, since real evidence beats
    a stale disable flag."""
    lock = FileLock(str(HEALTH_PATH) + ".lock")
    with lock:
        health = _load_health()
        health["models"][model] = {"consecutive_failures": 0}
        provider = _provider_of(model)
        prov_entry = health["providers"].get(provider)
        if prov_entry and prov_entry.get("disabled"):
            prov_entry["disabled"] = False
        _save_health(health)


def record_health_failure(model: str, reason: str, sibling_models: list[str]) -> None:
    """Decides whether to disable just this model or escalate to disabling
    its whole provider:

    - An explicit "unknown model"/"model not found"/etc marker means the
      model slug itself is bad -> disable that model only, permanently (it
      will never start working on its own).
    - An explicit auth-failure marker means the provider's credentials are
      broken -> disable the whole provider, permanently (needs a human to
      fix credentials).
    - Otherwise (timeout / rate-limit / generic failure) it's ambiguous on
      its own -- track consecutive failures per model, and once a model
      crosses MODEL_FAIL_THRESHOLD, check how many *other* models under the
      same provider are also currently struggling. If enough are, this is
      almost certainly one account-wide problem (quota exhaustion, rate
      limit) rather than N independently-broken models -- escalate to a
      temporary provider-level disable instead of disabling each one by one.
    """
    lock = FileLock(str(HEALTH_PATH) + ".lock")
    with lock:
        health = _load_health()
        provider = _provider_of(model)
        lowered = (reason or "").lower()
        now = time.time()

        if any(marker in lowered for marker in _MODEL_LEVEL_MARKERS):
            health["models"][model] = {
                "consecutive_failures": health["models"].get(model, {}).get("consecutive_failures", 0) + 1,
                "disabled": True, "disabled_until": None, "disabled_at": now,
                "scope": "model", "reason": reason,
            }
            _save_health(health)
            return

        if any(marker in lowered for marker in _PROVIDER_LEVEL_MARKERS):
            health["providers"][provider] = {
                "disabled": True, "disabled_until": None, "disabled_at": now,
                "scope": "provider", "reason": reason,
            }
            _save_health(health)
            return

        entry = health["models"].get(model, {"consecutive_failures": 0})
        entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        entry["last_reason"] = reason
        entry["last_ts"] = now
        health["models"][model] = entry

        if entry["consecutive_failures"] < MODEL_FAIL_THRESHOLD:
            _save_health(health)
            return

        struggling_siblings = sum(
            1 for m in sibling_models
            if m != model and health["models"].get(m, {}).get("consecutive_failures", 0) >= MODEL_FAIL_THRESHOLD
        )
        if struggling_siblings + 1 >= PROVIDER_ESCALATION_COUNT:
            health["providers"][provider] = {
                "disabled": True, "disabled_until": now + PROVIDER_COOLDOWN_SECONDS,
                "disabled_at": now, "scope": "provider",
                "reason": (
                    f"{struggling_siblings + 1} models under provider '{provider}' are all "
                    f"failing at once (latest: {reason}) -- looks account-wide (quota/rate "
                    f"limit), not per-model"
                ),
            }
        else:
            entry["disabled"] = True
            entry["disabled_until"] = now + MODEL_COOLDOWN_SECONDS
            entry["disabled_at"] = now
            entry["scope"] = "model"
            entry["reason"] = reason
            health["models"][model] = entry
        _save_health(health)


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


def ping_model(model: str, timeout: float, env: dict | None = None) -> "DispatchOutcome":
    """Cheap reachability/auth check for a model, run before committing to a
    full dispatch attempt -- catches a dead/misconfigured model without
    burning the (much longer) per-attempt timeout on it. Runs in a throwaway
    directory, never the target repo, so a misbehaving model has nothing to
    touch."""
    with tempfile.TemporaryDirectory(prefix="opencode-bridge-ping-") as scratch_dir:
        cmd = build_ping_command(model, scratch_dir)
        return run_opencode(cmd, timeout=timeout, env=env)


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
    run_log_path: str | None = None  # jsonl file this attempt streamed to, if any


def _stream_reader(pipe, sink: list[str], log_file, log_lock: threading.Lock) -> None:
    """Reads `pipe` line-by-line as it arrives and appends each line to
    `sink` (for the caller's final stdout string) and, if given, tees it
    live to `log_file` -- so a long-running attempt's progress is visible
    (e.g. via `tail -f`/the Monitor tool) instead of only appearing after
    the whole process exits."""
    for line in iter(pipe.readline, ""):
        sink.append(line)
        if log_file is not None:
            with log_lock:
                log_file.write(line if line.endswith("\n") else line + "\n")
                log_file.flush()
    pipe.close()


def run_opencode(
    cmd: list[str], timeout: float, env: dict | None = None,
    jsonl_log_path: "Path | str | None" = None,
) -> DispatchOutcome:
    # Popen (not subprocess.run) so we retain the pid for a process-group kill
    # on timeout -- subprocess.run's own TimeoutExpired never carries .pid,
    # which would make the kill unreachable (verified empirically: a real
    # TimeoutExpired instance has no `pid` attribute at all).
    #
    # opencode writes every session to one global sqlite db (~/.local/share/
    # opencode/opencode.db, or $XDG_DATA_HOME/opencode/opencode.db). Running
    # several `opencode run` processes concurrently against that shared db
    # causes "database is locked" (immediate failure) or, once contention
    # backs up, silent hangs to the timeout. Callers dispatching multiple
    # models in parallel must pass a distinct env with its own XDG_DATA_HOME
    # per concurrent worker to keep each one on an isolated db file.
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True, env=env,
    )

    log_file = None
    if jsonl_log_path is not None:
        jsonl_log_path = Path(jsonl_log_path)
        jsonl_log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(jsonl_log_path, "a")

    # `--format json` already emits one JSON event per line -- read it
    # incrementally (own thread, since proc.stdout.readline() blocks) instead
    # of buffering the whole thing in communicate(), so each event lands in
    # jsonl_log_path the moment opencode writes it, not only at process exit.
    stdout_lines: list[str] = []
    log_lock = threading.Lock()
    reader = threading.Thread(
        target=_stream_reader, args=(proc.stdout, stdout_lines, log_file, log_lock),
        daemon=True,
    )
    reader.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()  # reap the now-killed process
        reader.join(timeout=5)
        if log_file is not None:
            log_file.close()
        return DispatchOutcome(
            classification="TIMED_OUT", reason="timeout elapsed, process group killed",
            retryable=True,
        )

    reader.join(timeout=5)
    stderr = proc.stderr.read()
    proc.stderr.close()
    if log_file is not None:
        log_file.close()
    stdout = "".join(stdout_lines)

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

        disabled, disabled_reason = is_model_disabled(model)
        if disabled:
            failure_reasons.append(f"{model}: skipped -- {disabled_reason}")
            continue  # known-bad model/provider -- don't waste a ping on it

        ping_outcome = ping_model(model, timeout=ping_timeout)
        if ping_outcome.classification != "DONE":
            failure_reasons.append(f"{model}: ping failed -- {ping_outcome.reason}")
            record_health_failure(model, ping_outcome.reason, sibling_models=models)
            continue  # dead/misconfigured model -- skip straight to the next fallback
        record_health_success(model)

        session_id = mapping_session_id if model_index == 0 else None
        for attempt in range(2):  # original attempt + one retry, per model
            if time.monotonic() - start > chain_timeout:
                return DispatchOutcome(
                    classification="FAILED",
                    reason=f"chain-level timeout exceeded; failures so far: {failure_reasons}",
                )
            before = git_status_snapshot(repo)
            cmd = build_command(task=task, repo=repo, model=model, session_id=session_id)
            log_path = run_log_path_for(repo, topic, model)
            logger.info(f"streaming {model} output -> {log_path}")
            outcome = run_opencode(cmd, timeout=per_attempt_timeout, jsonl_log_path=log_path)
            outcome.run_log_path = str(log_path)

            if outcome.classification == "DONE":
                record_health_success(model)
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
                record_health_failure(model, outcome.reason, sibling_models=models)
                break  # non-retryable: stop retrying this model, advance to the next
            # retryable + clean tree: retry same model once with a fresh session
            session_id = None  # fresh temp session for the retry attempt
        else:
            # both attempts were retryable and still failed -- exhausted, not
            # just skipped, so it counts toward this model's health too
            record_health_failure(model, outcome.reason, sibling_models=models)

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
            "run_log_path": getattr(outcome, "run_log_path", None),
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
        "run_log_path": getattr(outcome, "run_log_path", None),
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
    if config.get("rotate_providers", True):
        models = rotate_models_by_provider(models)
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
