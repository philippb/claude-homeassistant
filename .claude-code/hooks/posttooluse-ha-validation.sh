#!/bin/bash
# Post-tool-use hook to validate Home Assistant configuration after file changes

# Check if we're in a home assistant config project
if [ ! -f "config/configuration.yaml" ]; then
    exit 0  # Not a HA project, skip
fi

# Check if the edit was to a YAML file in the config directory or if it's a write/edit operation
if [[ "$CLAUDE_TOOL_NAME" == "Edit" || "$CLAUDE_TOOL_NAME" == "Write" || "$CLAUDE_TOOL_NAME" == "MultiEdit" || "$CLAUDE_TOOL_NAME" == "NotebookEdit" ]]; then
    # Check if the file path contains config/ and is a YAML file
    if [[ "$CLAUDE_TOOL_ARGS" =~ config/.*\.(yaml|yml) ]]; then
        echo "🔍 Running Home Assistant configuration validation after file change..."

        # Check if validation tools exist
        if [ ! -f "tools/run_tests.py" ]; then
            echo "⚠️  Home Assistant validation tools not found. Please run setup first."
            exit 0
        fi

        # Run validation (we're already in project root)
        uv run python tools/run_tests.py

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
