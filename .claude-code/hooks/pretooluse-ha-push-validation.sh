#!/bin/bash
# Pre-tool-use hook to validate Home Assistant configuration before pushing
# Claude Code passes the tool call as JSON on stdin; exit code 2 blocks the command

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Check if we're in a home assistant config project
if [ ! -f "config/configuration.yaml" ]; then
    exit 0  # Not a HA project, skip
fi

command=$(jq -r '.tool_input.command // empty')

# Load HA_HOST so direct rsync/scp to the configured host is caught too
if [ -f ".env" ]; then
    HA_HOST=$(grep -E '^HA_HOST=' .env | cut -d= -f2-)
fi
host_pattern="homeassistant"
if [ -n "$HA_HOST" ]; then
    host_pattern="(homeassistant|${HA_HOST##*@})"
fi

# Check if the command pushes config to HA
if [[ ! "$command" =~ make[[:space:]]+push ]] && [[ ! "$command" =~ (rsync|scp).*${host_pattern}.*: ]]; then
    exit 0
fi

# Pulling (remote is the source) is fine
if [[ "$command" =~ (rsync|scp).*${host_pattern}:[^[:space:]]*[[:space:]]+[^[:space:]]*config/?([[:space:]]|$) ]]; then
    exit 0
fi

# Check if validation tools exist
if [ ! -f "tools/run_tests.py" ] || [ ! -d "venv" ]; then
    echo "❌ Home Assistant validation tools not found. Please run setup first." >&2
    echo "🚫 Blocking push to prevent invalid configuration upload." >&2
    exit 2
fi

source venv/bin/activate
output=$(python tools/run_tests.py 2>&1)

if [ $? -ne 0 ]; then
    echo "$output" | tail -40 >&2
    echo "" >&2
    echo "🚫 BLOCKING PUSH: Home Assistant configuration validation failed!" >&2
    echo "   Fix the errors above before pushing to Home Assistant." >&2
    exit 2
fi

echo "✅ Pre-push validation passed! Safe to sync to Home Assistant."
