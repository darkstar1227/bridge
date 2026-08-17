---
name: sre-assessment
description: Runs an on-demand Site Reliability Engineering assessment of a project — SLO/SLI coverage, error budgets, observability (metrics/logs/traces/alerting), incident readiness (runbooks, on-call, postmortems), deploy safety (rollback, canary, feature flags), capacity/scaling, and dependency/failure-mode risk. Produces a scored report with prioritized fixes. User-driven only: invoke explicitly via `/bridge-dev:sre-assessment` or an explicit request like "run an SRE assessment" / "SRE 評估" — this skill has no auto-trigger phrases, so it never fires on ambient conversation and never consumes context unless asked for by name.
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# SRE Assessment

**Announce at start:** "I'm using the bridge-dev:sre-assessment skill to run an SRE assessment of this project."

## Purpose

Judge a project's operational reliability posture, not its feature correctness. A codebase can pass every test and still page someone at 3am with no runbook, no rollback path, and no idea why. This skill audits the project against standard SRE dimensions and returns a scored, prioritized report — it does not fix anything itself unless the user explicitly asks for fixes afterward.

This skill is **user-driven only** — no `triggers` phrases are configured, so it never auto-fires from ambient conversation. Only run it when the user explicitly asks (`/bridge-dev:sre-assessment`, "run an SRE assessment", "SRE 評估", "reliability audit").

## Step 1 — Scope the Target

Confirm scope with the user if ambiguous: whole repo, a specific service/directory, or a specific deploy target. Default to the whole repo if unstated.

## Step 2 — Gather Evidence (context-mode first)

Evidence-gathering here touches many files and configs whose raw bytes are not worth keeping in the conversation — use `ctx_batch_execute`/`ctx_execute_file` for the search/parse pass and only pull exact snippets into context when quoting them in the final report. For each dimension below, search for the presence/absence and quality of relevant artifacts:

| Dimension | What to look for |
|---|---|
| **SLO/SLI** | Defined SLOs/SLIs (docs, code, dashboards-as-code), error budget policy |
| **Observability** | Structured logging, metrics emission (Prometheus/OTel/etc.), distributed tracing, alerting rules, dashboards |
| **Incident readiness** | Runbooks, on-call rotation config/docs, postmortem docs/templates, escalation paths |
| **Deploy safety** | CI/CD pipeline config, rollback mechanism, canary/blue-green setup, feature flags, health checks/readiness probes |
| **Capacity & scaling** | Autoscaling config, resource limits/requests, load-test artifacts, known bottlenecks documented |
| **Dependency & failure-mode risk** | Timeouts/retries/circuit breakers on external calls, single points of failure, backup/DR docs, dependency inventory |
| **Security/config hygiene relevant to reliability** | Secrets management, config drift risk, infra-as-code presence |

If a `.codegraph/` index exists for the target, use `codegraph_explore`/`codegraph_node` to trace failure-mode-relevant code (external call sites, retry logic, health checks) instead of `grep`/whole-file `Read`. If missing, use built-in tools directly (indexing is the user's call, don't run it uninvited).

## Step 3 — Score Each Dimension

Score each dimension 0–5:

- **0** — absent, no evidence found
- **1–2** — present but ad hoc / undocumented / inconsistent
- **3** — present and functional, gaps remain
- **4** — solid, minor gaps only
- **5** — mature, documented, tested

Justify every score with concrete evidence (file paths, config snippets, or explicit absence after a real search — not assumption).

## Step 4 — Identify Top Risks

From the lowest-scoring dimensions, pull out the 3–5 concrete failure scenarios most likely to cause an incident or extend one (e.g. "no rollback path — a bad deploy stays live until someone manually reverts and redeploys," "external payment API call has no timeout — a hang there hangs the request pool"). Tie each to the evidence from Step 2, not to the score alone.

## Step 5 — Write the Report

Save to `docs/sre-assessments/sre-assessment-YYYY-MM-DD-<scope-slug>.md` (today's date, slug from the scoped target). Summarize the overall verdict and top risks directly in chat too — don't make the user open the file to learn the outcome.

Report template:

```markdown
# SRE Assessment: <scope>

_Reviewed: <today's date>_
_Scope: <repo/service/directory>_

## Overall Verdict

<One or two sentences: is this production-ready from a reliability standpoint, and why>

## Scorecard

| Dimension | Score (0-5) | Evidence |
|---|---|---|
| SLO/SLI | | |
| Observability | | |
| Incident Readiness | | |
| Deploy Safety | | |
| Capacity & Scaling | | |
| Dependency & Failure-Mode Risk | | |

## Top Risks

1. <failure scenario> — <evidence> — <why it matters>
...

## Prioritized Fixes

<Ordered by risk-reduction-per-effort, concrete and actionable — not vague advice>

## Assumptions / Open Questions

- [ASSUMPTION] <where evidence was ambiguous> — <why>
- [OPEN] <anything the user should clarify>
```

## Notes

- This is an audit, not a remediation. If the user wants fixes applied, treat that as a separate explicit follow-up request.
- A dimension scored 0 is a finding, not an accusation — some projects (internal tools, prototypes) legitimately don't need full SRE maturity. State the score and evidence; let the user judge whether it matters for this project's actual risk profile.
