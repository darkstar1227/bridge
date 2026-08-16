#!/bin/sh
# bridge-mind: focus timer
#
# UserPromptSubmit hook. Tracks elapsed working time and injects a single
# nudge when a session runs long, because ADHD time blindness means elapsed
# time is not felt — three hours and forty minutes register the same from
# the inside.
#
# Design constraints, all learned from skills that got disabled:
#   - Fires AT MOST ONCE per threshold per session. A repeating nudge is
#     noise, and a muted nudge protects nothing.
#   - Never blocks. Injects context only.
#   - Never scolds. It reports elapsed time; it does not grade the user.
#   - Silent on failure, always exit 0. A hook that breaks the prompt loop
#     gets uninstalled, and then it helps no one.
#
# State: .bridge/focus-state.json in the project directory (gitignored).
# A gap of more than 45 minutes between prompts counts as a new session.

set -u

STATE_DIR=".bridge"
STATE="$STATE_DIR/focus-state.json"

# Thresholds in minutes. First is the physical-break point, second is the
# "this has eaten the day" point.
T1=120
T2=240
GAP=2700 # 45 min in seconds; longer gap starts a fresh session

command -v jq >/dev/null 2>&1 || exit 0

now=$(date +%s 2>/dev/null) || exit 0

start=$now
last=$now
warned="[]"

if [ -f "$STATE" ]; then
  prev_start=$(jq -r '.session_start // empty' "$STATE" 2>/dev/null)
  prev_last=$(jq -r '.last_seen // empty' "$STATE" 2>/dev/null)
  prev_warned=$(jq -c '.warned // []' "$STATE" 2>/dev/null)

  if [ -n "$prev_start" ] && [ -n "$prev_last" ]; then
    gap=$((now - prev_last))
    if [ "$gap" -lt "$GAP" ]; then
      # Same session continues.
      start=$prev_start
      warned=${prev_warned:-"[]"}
    fi
  fi
fi

elapsed_min=$(( (now - start) / 60 ))

fire=""
if [ "$elapsed_min" -ge "$T2" ] && ! printf '%s' "$warned" | grep -q "$T2"; then
  fire="$T2"
elif [ "$elapsed_min" -ge "$T1" ] && ! printf '%s' "$warned" | grep -q "$T1"; then
  fire="$T1"
fi

# Persist state before emitting, so a failure downstream cannot cause a repeat.
mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
if [ -n "$fire" ]; then
  warned=$(printf '%s' "$warned" | jq -c --argjson t "$fire" '. + [$t]' 2>/dev/null) || warned="[$fire]"
fi
jq -n --argjson s "$start" --argjson l "$now" --argjson w "$warned" \
  '{session_start:$s, last_seen:$l, warned:$w}' > "$STATE" 2>/dev/null || exit 0

[ -n "$fire" ] || exit 0

hours=$((elapsed_min / 60))
mins=$((elapsed_min % 60))

if [ "$fire" = "$T1" ]; then
  body="You have been working for ${hours}h${mins}m without a break in this session. That is not a problem in itself — but ADHD time blindness means the elapsed time has not registered, so here it is as a number.\n\nTwo things worth a moment: are you still working on what you sat down to do, or did the thread drift? And has there been food, water, or standing up?\n\nMention this once, in one or two sentences, then continue with whatever the user asked. Do not repeat it later in the session, do not moralize, and do not refuse to keep working."
else
  body="This session has now run ${hours}h${mins}m. Long enough that the cost of continuing is likely exceeding the output — decision quality and error rate both degrade well before this point, and neither is noticeable from the inside.\n\nSuggest a stopping point: what is the smallest thing that would leave this in a resumable state (a commit, a note, a failing test that marks the spot)? Offer to do that now via bridge-mind:distraction-capture or a WIP commit.\n\nSay it once, briefly. If the user keeps going, help them — do not raise it again."
fi

jq -n --arg b "$body" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: ("⏱ bridge-mind focus timer\n\n" + $b)
  }
}' 2>/dev/null || exit 0

exit 0
