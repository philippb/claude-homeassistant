#!/bin/bash
# Pre-tool-use hook to validate Home Assistant configuration before pushing

# Check if we're in a home assistant config project and about to run a push/sync command
if [ ! -f "config/configuration.yaml" ]; then
    exit 0  # Not a HA project, skip
fi

# Check if this is a bash command that might push to HA
if [[ "$CLAUDE_TOOL_NAME" == "Bash" ]]; then
    # Check if the command contains rsync, scp, or other sync commands to homeassistant
    if [[ "$CLAUDE_TOOL_ARGS" =~ (rsync|scp).*homeassistant ]]; then
        echo "🛡️  Pre-push validation: Checking Home Assistant configuration before sync..."

        # Check if validation tools exist
        if [ ! -f "tools/run_tests.py" ]; then
            echo "❌ Home Assistant validation tools not found. Please run setup first."
            echo "🚫 Blocking push to prevent invalid configuration upload."
            exit 1
        fi

        # Run validation (we're already in project root)
        uv run python tools/run_tests.py

        validation_result=$?

        if [ $validation_result -ne 0 ]; then
            echo ""
            echo "🚫 BLOCKING PUSH: Home Assistant configuration validation failed!"
            echo "   Please fix the errors above before pushing to Home Assistant."
            echo "   This prevents uploading an invalid configuration that could break HA."
            echo ""
            exit 1  # Block the command
        else
            echo "✅ Pre-push validation passed! Safe to sync to Home Assistant."
        fi
    fi
fi
