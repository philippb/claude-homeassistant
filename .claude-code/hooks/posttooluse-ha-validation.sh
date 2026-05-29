#!/bin/bash
# Post-tool-use hook to validate Home Assistant configuration after file changes

# Determine the HA config directory, honoring LOCAL_CONFIG_PATH (env or .env),
# falling back to the default "config". Mirrors the Makefile behaviour.
CONFIG_PATH="${LOCAL_CONFIG_PATH:-}"
if [ -z "$CONFIG_PATH" ] && [ -f ".env" ]; then
    CONFIG_PATH=$(grep -E '^LOCAL_CONFIG_PATH=' .env | tail -1 | cut -d= -f2- | tr -d '"'\''')
fi
CONFIG_PATH="${CONFIG_PATH:-config}"
CONFIG_PATH="${CONFIG_PATH%/}"  # strip trailing slash

# Check if we're in a home assistant config project
if [ ! -f "$CONFIG_PATH/configuration.yaml" ]; then
    exit 0  # Not a HA project, skip
fi

# Check if the edit was to a YAML file in the config directory or if it's a write/edit operation
if [[ "$CLAUDE_TOOL_NAME" == "Edit" || "$CLAUDE_TOOL_NAME" == "Write" || "$CLAUDE_TOOL_NAME" == "MultiEdit" || "$CLAUDE_TOOL_NAME" == "NotebookEdit" ]]; then
    # Check if the file path is a YAML file under the config directory
    if [[ "$CLAUDE_TOOL_ARGS" =~ ${CONFIG_PATH}/.*\.(yaml|yml) ]] || [[ "$CLAUDE_TOOL_ARGS" =~ config/.*\.(yaml|yml) ]]; then
        echo "🔍 Running Home Assistant configuration validation after file change..."

        # Check if validation tools exist
        if [ ! -f "tools/run_tests.py" ] || [ ! -d "venv" ]; then
            echo "⚠️  Home Assistant validation tools not found. Please run setup first."
            exit 0
        fi

        # Run validation (we're already in project root)
        source venv/bin/activate
        python tools/run_tests.py "$CONFIG_PATH"

        validation_result=$?

        if [ $validation_result -ne 0 ]; then
            echo ""
            echo "❌ Home Assistant configuration validation failed!"
            echo "   Please fix the errors above before pushing to Home Assistant."
            echo ""
            # Don't exit with error code to avoid blocking Claude, just warn
        else
            echo "✅ Home Assistant configuration validation passed!"
        fi
    fi
fi
