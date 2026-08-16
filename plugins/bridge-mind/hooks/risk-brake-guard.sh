#!/bin/sh
# bridge-mind: risk-brake guard
#
# PreToolUse hook on Bash. Matches the command against irreversible-action patterns
# and, on a hit, injects context telling Claude to run bridge-mind:risk-brake-thinking
# first.
#
# Deliberately NON-BLOCKING: it never denies the call. Description-based skill
# triggering is probabilistic; this makes the risk check deterministic without
# stalling unattended /loop or batch pipeline runs waiting on an answer nobody
# is present to give.
#
# Always exits 0. A guard that breaks the user's shell gets uninstalled, and then
# it protects nothing.

set -u

payload=$(cat 2>/dev/null) || exit 0
[ -n "$payload" ] || exit 0

# No jq means no reliable parse. Stay silent rather than guess.
command -v jq >/dev/null 2>&1 || exit 0

cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$cmd" ] || exit 0

klass=""

# Ordered most-costly first; first match wins.
if printf '%s' "$cmd" | grep -Eiq '(place_order|create_order|submit_order|submit_trade|market_order|limit_order)|--live\b|live[[:space:]]*=[[:space:]]*True|paper[[:space:]]*=[[:space:]]*False'; then
  klass="trade"
elif printf '%s' "$cmd" | grep -Eiq 'drop[[:space:]]+(table|database|schema)|truncate[[:space:]]+table|delete[[:space:]]+from[[:space:]]+[a-z_]'; then
  klass="destructive-sql"
elif printf '%s' "$cmd" | grep -Eiq 'supabase[[:space:]]+db[[:space:]]+(push|reset)|alembic[[:space:]]+(upgrade|downgrade)|prisma[[:space:]]+migrate[[:space:]]+(deploy|reset)|rails[[:space:]]+db:migrate'; then
  klass="migration"
elif printf '%s' "$cmd" | grep -Eiq 'terraform[[:space:]]+(apply|destroy)|kubectl[[:space:]]+(apply|delete|scale|drain|cordon)|kubectl[[:space:]]+rollout[[:space:]]+(undo|restart)|helm[[:space:]]+(upgrade|install|uninstall|rollback|delete)|flyctl[[:space:]]+deploy|vercel[[:space:]].*--prod'; then
  klass="deploy"
elif printf '%s' "$cmd" | grep -Eiq 'git[[:space:]]+push[[:space:]].*(--force([[:space:]]|$|=)|-f([[:space:]]|$))|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+clean[[:space:]]+-[a-zA-Z]*f'; then
  klass="force-push"
elif printf '%s' "$cmd" | grep -Eiq '(npm|pnpm|yarn|cargo)[[:space:]]+publish|gh[[:space:]]+release[[:space:]]+create|twine[[:space:]]+upload'; then
  klass="publish"
elif printf '%s' "$cmd" | grep -Eiq 'rm[[:space:]]+-[a-zA-Z]*[rf][a-zA-Z]*[[:space:]]|aws[[:space:]]+s3[[:space:]]+(rm|rb)|docker[[:space:]]+(compose[[:space:]]+)?down[[:space:]].*-v'; then
  klass="delete"
fi

[ -n "$klass" ] || exit 0

jq -n --arg k "$klass" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: (
      "⚠️ bridge-mind risk-brake guard: this command matches the \"" + $k +
      "\" irreversible-action class.\n\n" +
      "Before running it, invoke the bridge-mind:risk-brake-thinking skill: check " +
      ".bridge/decisions.jsonl for prior outcomes in this class, then emit the verdict " +
      "block (worst case, rollback command, cheaper test, past record).\n\n" +
      "Do not block an unattended run — if no one is present to answer, record the " +
      "decision and surface it in the final report instead. Trade-class actions with " +
      "real money are the one exception and should halt.\n\n" +
      "If this warning was already given for this same action earlier in the session, " +
      "do not repeat it. Proceed."
    )
  }
}' 2>/dev/null || exit 0

exit 0
