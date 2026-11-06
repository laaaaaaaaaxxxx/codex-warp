#!/bin/bash
# Hook script for Codex PreCompact event.
# Pre-turn compaction runs before UserPromptSubmit, so Warp would keep showing
# the previous turn as done until compaction ends.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/should-use-structured.sh"

if ! should_use_structured; then
    exit 0
fi

source "$SCRIPT_DIR/build-payload.sh"

INPUT=$(cat)
TURN_ID=$(echo "$INPUT" | jq -r '.turn_id')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')

# guard: a prompt_submit during mid-turn compaction would clear the query Warp shows.
if [ "$(cat "$PLUGIN_DATA/$SESSION_ID.turn" 2>/dev/null)" = "$TURN_ID" ]; then
    exit 0
fi

BODY=$(build_payload "$INPUT" "prompt_submit")

"$SCRIPT_DIR/warp-notify.sh" "warp://cli-agent" "$BODY"
