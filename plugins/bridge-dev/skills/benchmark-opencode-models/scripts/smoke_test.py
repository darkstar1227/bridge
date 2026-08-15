# /// script
# dependencies = ["filelock"]
# ///
"""Smoke-test harness for the benchmark-opencode-models skill.

For each candidate model: ping first (cheap reachability/auth check, reused
from opencode-bridge's dispatch.py). Models that fail ping are recorded as
skipped -- no real dispatch is wasted on them.

Models that pass ping get 5 canned single-shot dispatch attempts, each in its
own throwaway git repo so parallel runs never race on git state:
  - feature_short:     minimal new-function prompt, bare repo
  - feature_detailed:  full superpowers-style spec (context/acceptance
                       criteria/constraints/definition-of-done), repo seeded
                       with a pre-existing unrelated function
  - bugfix_short:      minimal one-line bug report, repo seeded with a
                       broken function
  - bugfix_detailed:   full superpowers-style bug report, repo seeded with
                       the same broken function plus an unrelated function
  - tdd:               explicit red-to-green TDD instruction with a fixed
                       verification command, so the OpenCode event stream's
                       bash tool calls can be parsed to check whether the
                       model actually watched it fail before making it pass
                       (see score_tdd_test)

Every result is verified independently by actually importing and calling the
generated code -- OpenCode's own "terminal_state": "DONE" is never trusted on
its own, since the earlier ad-hoc test round found models that self-report
completion while writing zero lines of code.

Each test result is scored 0-5 on 5 axes (time/quality/completeness/autonomy/
discipline) -- see score_test() for the exact, deterministic rubric. The tdd
test additionally scores red_green_accuracy and test_call_discipline -- see
score_tdd_test().
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import threading
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DISPATCH_DIR = os.path.normpath(os.path.join(THIS_DIR, "..", "..", "opencode-bridge", "scripts"))
sys.path.insert(0, DISPATCH_DIR)
import dispatch  # noqa: E402

CLARIFYING_QUESTION_MARKERS = [
    "?", "請問", "需要更多", "需要進一步", "can you clarify", "could you clarify",
    "please provide", "please clarify", "what should", "which file",
]

FEATURE_SHORT_TASK = (
    "在 calc.py 新增函式 is_prime(n),回傳 n 是否為質數的布林值。"
)

FEATURE_DETAILED_TASK = """## Context
你正在為一個小型數學工具庫 calc.py 開發函式。這個檔案已經有其他函式在使用,之後也會被其他模組 import,所以既有內容與函式簽名必須維持穩定。

## Task
請在 calc.py 新增函式 is_prime(n: int) -> bool,判斷 n 是否為質數。

## Acceptance Criteria
- n < 2 時回傳 False
- n == 2 回傳 True
- 偶數(除了 2)一律回傳 False
- 純 Python 標準函式庫實作即可,不需要 import 任何第三方套件

## Constraints
- 只能修改 calc.py,不要新增或修改任何其他檔案(包含測試檔、README 等)
- 不要移除或修改 calc.py 中已經存在的 double(x) 函式
- 只新增 is_prime 這一個函式,不要新增其他輔助函式或 class

## Definition of Done
執行 `python3 -c "import calc; print(calc.is_prime(97), calc.double(21))"` 要能直接執行且結果正確,不能有例外。
"""

BUGFIX_SHORT_TASK = (
    "calc.py 的 average(nums) 函式有 bug,請修好它。"
)

BUGFIX_DETAILED_TASK = """## Context
calc.py 裡有一個現有函式 average(nums),用途是計算一個數字 list 的平均值。線上回報這個函式在某些情況下會產生錯誤或錯誤結果。

## Bug Report
- average([1, 2, 3]) 應該回傳 2.0,但實際上回傳了 6(看起來像是忘記除以長度)
- average([]) 應該回傳 0,但實際上會拋出 ZeroDivisionError

## Task
請修正 calc.py 中的 average(nums) 函式,讓上述兩個情境都能得到正確結果。

## Constraints
- 只能修改 calc.py,不要新增或修改任何其他檔案
- 不要改變函式名稱或參數簽名(仍然叫 average,只接受一個 nums 參數)
- 不要移除或修改 calc.py 中已經存在的 double(x) 函式

## Definition of Done
執行 `python3 -c "import calc; print(calc.average([1,2,3]), calc.average([]), calc.double(21))"` 要印出 2.0 0 42,不能有例外。
"""

TDD_VERIFY_SUBSTR = "is_leap_year"
TDD_EXPECTED_GREEN_OUTPUT = "True False True False"

TDD_TASK = f"""請用 TDD(紅燈-綠燈)方式在 calc.py 新增函式 is_leap_year(year: int) -> bool,判斷西元年份是否為閏年(可以被 4 整除,但不可以被 100 整除,除非同時可以被 400 整除)。

## TDD 流程要求
1. 在寫任何實作程式碼之前,先執行下面這個驗證指令一次,確認 is_leap_year 還不存在(這是 RED,預期會失敗)。
2. 確認失敗後,再實作 is_leap_year。
3. 實作完成後,再次執行同一個驗證指令,確認結果正確(這是 GREEN)。

驗證指令(RED 和 GREEN 都用這一行,不要換成別的指令或別的寫法):
python3 -c "from calc import is_leap_year; print(is_leap_year(2000), is_leap_year(1900), is_leap_year(2024), is_leap_year(2023))"

預期 GREEN 階段的輸出為:{TDD_EXPECTED_GREEN_OUTPUT}

## Constraints
- 只能修改 calc.py,不要新增或修改任何其他檔案
- 只新增 is_leap_year 這一個函式
"""

TDD_SEED = "# stub -- implement is_leap_year(year) here\n"

FEATURE_SHORT_SEED = "# stub -- implement is_prime(n) here\n"

FEATURE_DETAILED_SEED = (
    '"""Small math utilities used across the project."""\n\n\n'
    "def double(x):\n"
    "    return x * 2\n"
)

BUGFIX_SHORT_SEED = (
    "def average(nums):\n"
    "    total = 0\n"
    "    for n in nums:\n"
    "        total += n\n"
    "    return total\n"
)

BUGFIX_DETAILED_SEED = (
    '"""Small math utilities used across the project."""\n\n\n'
    "def double(x):\n"
    "    return x * 2\n\n\n"
    "def average(nums):\n"
    "    total = 0\n"
    "    for n in nums:\n"
    "        total += n\n"
    "    return total\n"
)


def _verify_feature(repo_dir, with_double):
    checks = [
        ("is_prime(2) is True", "calc.is_prime(2) is True"),
        ("is_prime(1) is False", "calc.is_prime(1) is False"),
        ("is_prime(97) is True", "calc.is_prime(97) is True"),
        ("is_prime(100) is False", "calc.is_prime(100) is False"),
    ]
    if with_double:
        checks.append(("double(21) == 42", "calc.double(21) == 42"))
    return _run_checks(repo_dir, checks)


def _verify_bugfix(repo_dir, with_double):
    checks = [
        ("average([1,2,3]) == 2.0", "calc.average([1, 2, 3]) == 2.0"),
        ("average([]) == 0", "calc.average([]) == 0"),
    ]
    if with_double:
        checks.append(("double(21) == 42", "calc.double(21) == 42"))
    return _run_checks(repo_dir, checks)


def _verify_tdd(repo_dir):
    checks = [
        ("is_leap_year(2000) is True", "calc.is_leap_year(2000) is True"),
        ("is_leap_year(1900) is False", "calc.is_leap_year(1900) is False"),
        ("is_leap_year(2024) is True", "calc.is_leap_year(2024) is True"),
        ("is_leap_year(2023) is False", "calc.is_leap_year(2023) is False"),
    ]
    return _run_checks(repo_dir, checks)


def _run_checks(repo_dir, checks):
    """Run each check as its own import+assert subprocess so one failing
    check (e.g. a missing function) doesn't hide whether the others pass --
    this is what makes completeness scoring meaningful instead of all-or-nothing."""
    results = {}
    for label, expr in checks:
        code = f"import calc\nassert {expr}\nprint('OK')\n"
        try:
            r = subprocess.run(
                ["python3", "-c", code], cwd=repo_dir,
                capture_output=True, text=True, timeout=15,
            )
            results[label] = (r.returncode == 0 and "OK" in r.stdout)
        except Exception:
            results[label] = False
    return results


TESTS = {
    "feature_short": {
        "direction": "feature", "length": "short",
        "task": FEATURE_SHORT_TASK, "seed": FEATURE_SHORT_SEED,
        "verify": lambda repo: _verify_feature(repo, with_double=False),
        "allowed_files": {"calc.py"},
    },
    "feature_detailed": {
        "direction": "feature", "length": "detailed",
        "task": FEATURE_DETAILED_TASK, "seed": FEATURE_DETAILED_SEED,
        "verify": lambda repo: _verify_feature(repo, with_double=True),
        "allowed_files": {"calc.py"},
    },
    "bugfix_short": {
        "direction": "bugfix", "length": "short",
        "task": BUGFIX_SHORT_TASK, "seed": BUGFIX_SHORT_SEED,
        "verify": lambda repo: _verify_bugfix(repo, with_double=False),
        "allowed_files": {"calc.py"},
    },
    "bugfix_detailed": {
        "direction": "bugfix", "length": "detailed",
        "task": BUGFIX_DETAILED_TASK, "seed": BUGFIX_DETAILED_SEED,
        "verify": lambda repo: _verify_bugfix(repo, with_double=True),
        "allowed_files": {"calc.py"},
    },
    "tdd": {
        "direction": "tdd", "length": "n/a",
        "task": TDD_TASK, "seed": TDD_SEED,
        "verify": lambda repo: _verify_tdd(repo),
        "allowed_files": {"calc.py"},
        "kind": "tdd",
    },
}


def seed_repo(repo_dir, seed_content):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir, exist_ok=True)
    with open(os.path.join(repo_dir, "calc.py"), "w") as f:
        f.write(seed_content)
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)


def _final_text(events):
    text = ""
    for e in events:
        if e.get("type") == "text":
            text = (e.get("part") or {}).get("text", text)
    return text


def _changed_paths(changed_lines):
    """git status --porcelain lines -> bare relative paths, ignoring
    __pycache__ noise that every Python run leaves behind regardless of
    what the model actually touched."""
    paths = set()
    for line in changed_lines:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if "__pycache__" in path:
            continue
        paths.add(path)
    return paths


def run_single_attempt(model, task, repo_dir, timeout, env=None):
    cmd = dispatch.build_command(task=task, repo=repo_dir, model=model, session_id=None)
    before = dispatch.git_status_snapshot(repo_dir)
    outcome = dispatch.run_opencode(cmd, timeout=timeout, env=env)
    after = dispatch.git_status_snapshot(repo_dir)
    changed = sorted(dispatch.diff_snapshots(before, after))
    return outcome, changed


def score_test(spec, outcome, changed_lines, elapsed):
    changed_paths = _changed_paths(changed_lines)
    unexpected_files = changed_paths - spec["allowed_files"]
    is_done = outcome.classification == "DONE"
    no_op = is_done and not changed_paths

    check_results = {}
    if is_done:
        check_results = spec["verify"](spec["_repo_dir"])
    passed = sum(1 for v in check_results.values() if v)
    total = len(check_results) or 1

    # 時間 speed
    if not is_done:
        time_score = 1
    elif elapsed <= 20:
        time_score = 5
    elif elapsed <= 45:
        time_score = 4
    elif elapsed <= 90:
        time_score = 3
    elif elapsed <= 180:
        time_score = 2
    else:
        time_score = 1

    # 品質 quality -- did the primary/simple case work at all
    if not is_done:
        quality_score = 0
    else:
        quality_score = round(5 * (passed / total))

    # 完整性 completeness -- same checklist, but this is the one that
    # distinguishes "got the demo case right" from "covered every edge case
    # and constraint listed in the spec"; for these tests it's the same
    # checklist as quality by construction, so report it identically but
    # keep it a separate field since real-world specs would diverge.
    completeness_score = quality_score

    # 自主性 autonomy -- finished without asking for help, without faking it
    autonomy_score = 5
    if not is_done:
        autonomy_score -= 1
    if no_op:
        autonomy_score -= 2
    final_text = _final_text(outcome.events).lower()
    if is_done and any(m in final_text for m in CLARIFYING_QUESTION_MARKERS):
        autonomy_score -= 2
    autonomy_score = max(0, autonomy_score)

    # 紀律性 discipline -- stayed inside the constraints it was given
    discipline_score = 5
    if unexpected_files:
        discipline_score -= 2
    if is_done and check_results and "double(21) == 42" in check_results and not check_results["double(21) == 42"]:
        discipline_score -= 2
    discipline_score = max(0, discipline_score)

    return {
        "terminal_state": outcome.classification,
        "elapsed": elapsed,
        "changed_files": sorted(changed_paths),
        "unexpected_files": sorted(unexpected_files),
        "no_op": no_op,
        "checks": check_results,
        "issues": outcome.reason if outcome.classification != "DONE" else None,
        "scores": {
            "time": time_score,
            "quality": quality_score,
            "completeness": completeness_score,
            "autonomy": autonomy_score,
            "discipline": discipline_score,
        },
    }


def _extract_bash_calls(events, match_substr):
    """Chronological list of {command, exit_code, output} for every bash
    tool call whose command references match_substr -- OpenCode's --format
    json stream emits these as {"type": "tool_use", "part": {"tool": "bash",
    "state": {"input": {"command": ...}, "metadata": {"exit": ...,
    "output": ...}}}}. Used to reconstruct whether a model actually ran the
    given verification command before (RED) and after (GREEN) implementing."""
    calls = []
    for e in events:
        if e.get("type") != "tool_use":
            continue
        part = e.get("part") or {}
        if part.get("tool") != "bash":
            continue
        state = part.get("state") or {}
        command = (state.get("input") or {}).get("command", "")
        if match_substr not in command:
            continue
        metadata = state.get("metadata") or {}
        calls.append({
            "command": command,
            "exit_code": metadata.get("exit"),
            "output": metadata.get("output", state.get("output", "")) or "",
        })
    return calls


def score_tdd_test(spec, outcome, changed_lines, elapsed):
    """Same base scoring as score_test() (time/quality/completeness/autonomy/
    discipline, from the same independent-verification checklist), plus two
    TDD-specific axes computed from the bash calls matching the fixed
    verification command the prompt handed over."""
    base = score_test(spec, outcome, changed_lines, elapsed)
    is_done = outcome.classification == "DONE"
    calls = _extract_bash_calls(outcome.events, TDD_VERIFY_SUBSTR) if is_done else []
    code_correct = bool(base["checks"]) and all(base["checks"].values())

    def _is_red(call):
        return call["exit_code"] != 0

    def _is_green(call):
        return call["exit_code"] == 0 and TDD_EXPECTED_GREEN_OUTPUT in call["output"]

    did_red_first = bool(calls) and _is_red(calls[0])
    did_green_last = bool(calls) and _is_green(calls[-1])

    if not code_correct:
        red_green_score = 1 if calls else 0
    elif did_red_first and did_green_last:
        red_green_score = 5
    elif did_red_first and not did_green_last:
        red_green_score = 4
    elif did_green_last and not did_red_first:
        red_green_score = 3  # correct, but skipped the RED step it was asked to do
    else:
        red_green_score = 3

    n_calls = len(calls)
    if n_calls <= 1:
        call_discipline_score = 0
    elif n_calls == 2:
        call_discipline_score = 5
    elif n_calls == 3:
        call_discipline_score = 4
    elif n_calls == 4:
        call_discipline_score = 3
    elif n_calls <= 6:
        call_discipline_score = 2
    else:
        call_discipline_score = 1

    base["tdd_calls"] = [{"command": c["command"], "exit_code": c["exit_code"]} for c in calls]
    base["scores"]["red_green_accuracy"] = red_green_score
    base["scores"]["test_call_discipline"] = call_discipline_score
    return base


def _print_result(key, r):
    s = r["scores"]
    extra = ""
    if "red_green_accuracy" in s:
        extra = f" red_green={s['red_green_accuracy']} test_calls={s['test_call_discipline']}"
    print(
        f"  [{key:<16}] state={r['terminal_state']:<12} elapsed={r['elapsed']}  "
        f"time={s['time']} quality={s['quality']} completeness={s['completeness']} "
        f"autonomy={s['autonomy']} discipline={s['discipline']}{extra}"
        + (f"  issues={r['issues'][:100]}" if r["issues"] else ""),
        flush=True,
    )


def _skipped_result(spec, reason):
    scores = {"time": 0, "quality": 0, "completeness": 0, "autonomy": 0, "discipline": 0}
    if spec.get("kind") == "tdd":
        scores["red_green_accuracy"] = 0
        scores["test_call_discipline"] = 0
    return {
        "terminal_state": "PING_FAILED", "elapsed": None, "changed_files": [],
        "unexpected_files": [], "no_op": False, "checks": {},
        "issues": reason,
        "scores": scores,
    }


_AUTH_FILES = ["auth.json", "account.json", "mcp-auth.json"]


def _isolated_env(repo_root, model):
    """opencode writes every session to one shared sqlite db (~/.local/share/
    opencode/opencode.db by default). Concurrent `opencode run` processes
    against that one db hit "database is locked" or hang under contention --
    give each concurrently-running model its own XDG_DATA_HOME so its opencode
    db is a separate file, making concurrency safe.

    That same directory is also where opencode keeps provider credentials
    (auth.json/account.json/mcp-auth.json) -- a bare empty XDG_DATA_HOME has
    no credentials at all and every model fails with a generic "Unexpected
    server error" that looks like a real auth failure but isn't. Copy those
    files into each isolated dir so credentials still resolve while the
    session db itself stays separate per model."""
    slug = model.replace("/", "_").replace(":", "_")
    data_home = os.path.join(repo_root, ".opencode-data", slug)
    isolated_opencode_dir = os.path.join(data_home, "opencode")
    os.makedirs(isolated_opencode_dir, exist_ok=True)

    source_data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    source_opencode_dir = os.path.join(source_data_home, "opencode")
    for fname in _AUTH_FILES:
        src = os.path.join(source_opencode_dir, fname)
        dst = os.path.join(isolated_opencode_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

    env = dict(os.environ)
    env["XDG_DATA_HOME"] = data_home
    return env


def test_model(model, repo_root, per_attempt_timeout, ping_timeout, on_result=None):
    env = _isolated_env(repo_root, model)
    ping_outcome = dispatch.ping_model(model, timeout=ping_timeout, env=env)
    if ping_outcome.classification != "DONE":
        results = {key: _skipped_result(spec, ping_outcome.reason) for key, spec in TESTS.items()}
        if on_result:
            for key, r in results.items():
                on_result(key, r)
        return results

    results = {}
    for key, spec in TESTS.items():
        slug = model.replace("/", "_").replace(":", "_")
        repo_dir = os.path.join(repo_root, f"{slug}__{key}")
        seed_repo(repo_dir, spec["seed"])
        spec = dict(spec)
        spec["_repo_dir"] = repo_dir
        start = time.monotonic()
        outcome, changed = run_single_attempt(model, spec["task"], repo_dir, per_attempt_timeout, env=env)
        elapsed = round(time.monotonic() - start, 1)
        scorer = score_tdd_test if spec.get("kind") == "tdd" else score_test
        result = scorer(spec, outcome, changed, elapsed)
        results[key] = result
        if on_result:
            on_result(key, result)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, help="comma-separated model list")
    parser.add_argument("--repo-root", required=True, help="scratch dir to create throwaway repos in")
    parser.add_argument("--per-attempt-timeout", type=float, default=240)
    parser.add_argument("--ping-timeout", type=float, default=30)
    parser.add_argument("--concurrency", type=int, default=6, help="models run in parallel; each model's own 5 tests stay sequential")
    parser.add_argument("--out", required=True, help="path to write the JSON report")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    os.makedirs(args.repo_root, exist_ok=True)

    report = {}
    lock = threading.Lock()

    def run_one(model):
        print(f"=== {model} start ===", flush=True)

        def on_result(key, r):
            with lock:
                _print_result(f"{model} {key}", r)

        results = test_model(model, args.repo_root, args.per_attempt_timeout, args.ping_timeout, on_result=on_result)
        with lock:
            report[model] = results
            with open(args.out, "w") as f:
                json.dump(report, f, indent=2)
        print(f"=== {model} done ===", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        list(ex.map(run_one, models))

    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
