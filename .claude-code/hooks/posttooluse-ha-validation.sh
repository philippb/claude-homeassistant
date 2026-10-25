#!/bin/bash
# Post-tool-use hook to validate Home Assistant configuration after file changes
# Claude Code passes the tool call as JSON on stdin; exit code 2 feeds stderr back to Claude

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Check if we're in a home assistant config project
if [ ! -f "config/configuration.yaml" ]; then
    exit 0  # Not a HA project, skip
fi

file_path=$(jq -r '.tool_input.file_path // empty')

# Only validate YAML files in the config directory
if [[ ! "$file_path" =~ /config/.*\.(yaml|yml)$ ]]; then
    exit 0
fi

# Check if validation tools exist
if [ ! -f "tools/run_tests.py" ] || [ ! -d "venv" ]; then
    echo "⚠️  Home Assistant validation tools not found. Please run setup first." >&2
    exit 0
fi

source venv/bin/activate
output=$(python tools/run_tests.py 2>&1)

if [ $? -ne 0 ]; then
    echo "$output" | tail -40 >&2
    echo "" >&2
    echo "❌ Home Assistant configuration validation failed after editing $file_path." >&2
    echo "   Fix the errors above before pushing to Home Assistant." >&2
    exit 2
fi

echo "✅ Home Assistant configuration validation passed!"
