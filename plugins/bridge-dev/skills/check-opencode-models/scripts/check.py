# /// script
# dependencies = ["filelock"]
# ///
"""Fast availability + latency check for the check-opencode-models skill.

Two stages per model, both cheap compared to benchmark-opencode-models:
  1. Ping (reuses opencode-bridge's dispatch.ping_model) -- reachability/auth
     only, no repo touched. A model that fails ping skips stage 2 entirely.
  2. Prompt test -- one real, minimal single-shot dispatch (add a one-line
     function to a throwaway repo) with its own timeout, independently
     verified. This exists because ping's own prompt ("reply OK") is too
     trivial to reveal whether a model is *slow* under an actual coding
     task -- a model can ping fine in 2s and still take 90s to do anything
     real. `--slow-threshold` flags any prompt-test elapsed time above it.

This says nothing about quality/completeness/discipline across a range of
task shapes -- for that, use benchmark-opencode-models instead.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DISPATCH_DIR = os.path.normpath(os.path.join(THIS_DIR, "..", "..", "opencode-bridge", "scripts"))
sys.path.insert(0, DISPATCH_DIR)
import dispatch  # noqa: E402

PROMPT_TASK = "在 calc.py 新增函式 add_one(x),回傳 x + 1。只能修改 calc.py。"
PROMPT_SEED = "# stub -- implement add_one(x) here\n"


def _seed_repo(repo_dir):
    if os.path.exists(repo_dir):
        shutil.rmtree(repo_dir)
    os.makedirs(repo_dir, exist_ok=True)
    with open(os.path.join(repo_dir, "calc.py"), "w") as f:
        f.write(PROMPT_SEED)
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)


def _verify(repo_dir):
    code = "import calc\nassert calc.add_one(4) == 5\nprint('OK')\n"
    try:
        r = subprocess.run(
            ["python3", "-c", code], cwd=repo_dir,
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0 and "OK" in r.stdout
    except Exception:
        return False


def run_prompt_test(model, repo_root, timeout):
    slug = model.replace("/", "_").replace(":", "_")
    repo_dir = os.path.join(repo_root, f"check__{slug}")
    _seed_repo(repo_dir)
    cmd = dispatch.build_command(task=PROMPT_TASK, repo=repo_dir, model=model, session_id=None)
    start = time.monotonic()
    outcome = dispatch.run_opencode(cmd, timeout=timeout)
    elapsed = round(time.monotonic() - start, 1)
    correct = outcome.classification == "DONE" and _verify(repo_dir)
    return {
        "prompt_state": outcome.classification,
        "prompt_elapsed": elapsed,
        "correct": correct,
        "issues": outcome.reason if outcome.classification != "DONE" else None,
    }


def check_one(model, ping_timeout, prompt_timeout, slow_threshold, repo_root):
    ping_outcome = dispatch.ping_model(model, timeout=ping_timeout)
    available = ping_outcome.classification == "DONE"
    result = {
        "model": model,
        "available": available,
        "classification": ping_outcome.classification,
        "reason": ping_outcome.reason,
        "prompt_state": None,
        "prompt_elapsed": None,
        "correct": None,
        "slow": None,
    }
    if not available:
        return result

    prompt_result = run_prompt_test(model, repo_root, prompt_timeout)
    result.update(prompt_result)
    result["slow"] = (
        prompt_result["prompt_state"] != "DONE"
        or prompt_result["prompt_elapsed"] is None
        or prompt_result["prompt_elapsed"] > slow_threshold
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, help="comma-separated model list")
    parser.add_argument("--ping-timeout", type=float, default=30)
    parser.add_argument("--prompt-timeout", type=float, default=150, help="timeout for the real single-shot prompt test")
    parser.add_argument(
        "--slow-threshold", type=float, default=45,
        help=(
            "prompt-test elapsed seconds above this is flagged slow. Default calibrated from 11 "
            "already-confirmed-correct models' real add_one() elapsed times: a fast cluster at "
            "17.6-26.5s (opencode-zen, most openrouter free) and a slower-but-still-correct cluster "
            "at 83.7-119.6s (litellm-routed models) -- 45s sits near the geometric mean of those two "
            "clusters, giving margin on both sides against normal run-to-run jitter."
        ),
    )
    parser.add_argument("--repo-root", default="/tmp/check-opencode-models-repos")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--out", help="optional path to write the JSON report")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    os.makedirs(args.repo_root, exist_ok=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = [
            ex.submit(check_one, m, args.ping_timeout, args.prompt_timeout, args.slow_threshold, args.repo_root)
            for m in models
        ]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            if not r["available"]:
                status = r["classification"]
                detail = r["reason"]
            elif r["prompt_state"] != "DONE":
                status = r["prompt_state"]
                detail = r["issues"]
            elif not r["correct"]:
                status = "WRONG"
                detail = f"elapsed={r['prompt_elapsed']}s"
            else:
                status = "SLOW" if r["slow"] else "OK"
                detail = f"elapsed={r['prompt_elapsed']}s"
            print(f"[{status:>8}] {r['model']:<55}" + (f"  {detail[:100]}" if detail else ""), flush=True)
            results.append(r)

    results.sort(key=lambda r: (not r["available"], bool(r["slow"]), r["model"]))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nWrote {args.out}")

    reachable = [r for r in results if r["available"]]
    usable_now = [r for r in reachable if r["prompt_state"] == "DONE" and r["correct"] and not r["slow"]]
    slow = [r["model"] for r in reachable if r["slow"] and r["prompt_state"] == "DONE" and r["correct"]]
    wrong = [r["model"] for r in reachable if r["prompt_state"] == "DONE" and not r["correct"]]
    prompt_failed = [r["model"] for r in reachable if r["prompt_state"] not in ("DONE",)]
    unreachable = [r["model"] for r in results if not r["available"]]

    print(f"\n{len(usable_now)}/{len(models)} usable right now (reachable, correct, not slow).")
    if slow:
        print(f"Slow (>{args.slow_threshold}s): " + ", ".join(slow))
    if wrong:
        print("Reachable but wrong output: " + ", ".join(wrong))
    if prompt_failed:
        print("Reachable but prompt dispatch failed/timed out: " + ", ".join(prompt_failed))
    if unreachable:
        print("Not reachable (ping failed): " + ", ".join(unreachable))


if __name__ == "__main__":
    main()
