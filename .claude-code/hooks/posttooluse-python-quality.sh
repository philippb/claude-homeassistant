#!/bin/bash
#
# Post-Tool-Use Hook: Python Code Quality Checks
# Runs automatically after Claude Code tools are used
#
# This hook runs:
# - Black (code formatting)
# - isort (import sorting)
# - flake8 (style checking)
# - pylint (code analysis)
# - mypy (type checking)
# - pytest (tests if they exist)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TOOLS_DIR="tools"
TEST_DIR="tests"

# Check if we're in a Python project with our development setup
if [[ ! -d "$TOOLS_DIR" ]] || [[ ! -f "pyproject.toml" ]]; then
    # Not a Python project with our dev setup, skip silently
    exit 0
fi

echo -e "${BLUE}🐍 Running Python Code Quality Checks...${NC}"

# Function to run command and show result
run_check() {
    local name="$1"
    local command="$2"
    local icon="$3"

    echo -e "${BLUE}${icon} ${name}...${NC}"

    if eval "$command" > /tmp/python_check.log 2>&1; then
        echo -e "${GREEN}✅ ${name} passed${NC}"
        return 0
    else
        echo -e "${RED}❌ ${name} failed${NC}"
        echo -e "${YELLOW}📋 Output:${NC}"
        cat /tmp/python_check.log
        return 1
    fi
}

# Track if any checks failed
FAILED=0

# Check if Python files were modified or if we should force run
FORCE_RUN="${FORCE_PYTHON_CHECKS:-false}"
PYTHON_FILES_EXIST=$(find tools/ -name "*.py" 2>/dev/null | wc -l)

if [[ "$FORCE_RUN" == "true" ]] || [[ "$PYTHON_FILES_EXIST" -gt 0 ]] && [[ -d tools/ ]]; then
    echo -e "${BLUE}📝 Python files detected, running quality checks...${NC}"

    # 1. Code Formatting (Ruff)
    echo -e "\n${BLUE}🎨 Code Formatting${NC}"
    if ! run_check "Ruff formatting" "task dev:format" "🖤"; then
        FAILED=1
    fi

    # 2. Style Checking and Code Analysis (Ruff)
    echo -e "\n${BLUE}📏 Style Checking and Code Analysis${NC}"
    if ! run_check "Ruff style check" "uv run ruff check $TOOLS_DIR/" "🔍"; then
        FAILED=1
    fi

    # 3. Type Checking (mypy) - Allow to fail but show results
    echo -e "\n${BLUE}🔧 Type Checking${NC}"
    echo -e "${BLUE}🔍 Running mypy...${NC}"
    if uv run mypy $TOOLS_DIR/ > /tmp/mypy.log 2>&1; then
        echo -e "${GREEN}✅ Mypy type checking passed${NC}"
    else
        ERROR_COUNT=$(grep -c "error:" /tmp/mypy.log 2>/dev/null || echo "0")
        if [[ "$ERROR_COUNT" -gt 0 ]]; then
            echo -e "${YELLOW}⚠️  Mypy found ${ERROR_COUNT} type issues (non-blocking)${NC}"
            # Show first few errors
            head -10 /tmp/mypy.log
        else
            echo -e "${GREEN}✅ Mypy type checking passed${NC}"
        fi
    fi

    # 4. Tests (if they exist)
    if [[ -d "$TEST_DIR" ]] && find "$TEST_DIR" -name "test_*.py" 2>/dev/null | grep -q .; then
        echo -e "\n${BLUE}🧪 Running Tests${NC}"
        if ! run_check "pytest tests" "task dev:test" "🧪"; then
            FAILED=1
        fi
    else
        echo -e "\n${YELLOW}📝 No tests found in $TEST_DIR, skipping test run${NC}"
    fi

    # Summary
    echo -e "\n${BLUE}📊 Python Quality Check Summary${NC}"
    if [[ $FAILED -eq 0 ]]; then
        echo -e "${GREEN}✅ All critical checks passed!${NC}"
        echo -e "${GREEN}🎉 Code is ready for commit${NC}"
    else
        echo -e "${RED}❌ Some critical checks failed${NC}"
        echo -e "${YELLOW}🔧 Please fix the issues above before committing${NC}"
        # Don't exit with error - let user decide whether to commit
    fi

else
    echo -e "${BLUE}📝 No recent Python file changes detected, skipping quality checks${NC}"
fi

# Cleanup
rm -f /tmp/python_check.log /tmp/pylint.log /tmp/mypy.log

echo -e "${BLUE}🏁 Python quality checks completed${NC}"
exit 0
