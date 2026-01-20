# Development Setup for Home Assistant Config Tools

This directory contains a complete Python development environment with modern tooling for code quality, formatting, and testing.

## Quick Start

1. **Setup development environment:**
   ```bash
   task dev:setup
   ```

2. **Format and check code:**
   ```bash
   task dev:format
   task dev:lint
   ```

3. **Run tests:**
   ```bash
   task dev:test
   ```

## Development Tools Included

### Code Quality
- **ruff** - Automatic code formatting and linting (PEP8 compliant)
- **mypy** - Static type checking

### Testing
- **pytest** - Modern testing framework
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Mocking utilities

### Automation
- **prek** - Git hooks for automated checks
- **yamllint** - YAML file validation (for HA configs)

## File Structure

```
public/
├── .venv/                  # Python virtual environment, managed by uv
├── tools/                  # Python validation scripts
├── config/                 # Home Assistant configuration
├── pyproject.toml          # Python project configuration
├── .pre-commit-config.yaml # Pre-commit hook configuration
├── .yamllint.yml           # YAML linting rules
├── Taskfile.yaml           # Main project commands
├── Taskfile.dev.yaml       # Development-specific commands
└── README-DEV.md           # This file
```

## Available Commands

### Development Workflow
```bash
# Format code automatically
task dev:format

# Run all code quality checks
task dev:check-all

# Run tests with coverage
task dev:test-coverage

# Full development workflow
task dev:workflow
```

### Pre-commit Hooks
```bash
# Install git hooks
task dev:pre-commit-init

# Run hooks on all files
task dev:pre-commit
```

### Maintenance
```bash
# Update dependencies
task dev:update-deps

# Clean development artifacts
task dev:clean-dev
```

## Configuration Details

### ruff (code linting and formatting)
- Line length: 88 characters
- Target Python version: 3.13+
- Automatically formats all Python files

### mypy (Type Checking)
- Strict type checking enabled
- Ignores missing imports for third-party libraries
- Excludes test files from strict checking

### pytest (Testing)
- Coverage target: 80% minimum
- HTML coverage reports generated
- Test discovery in `tests/` directory

## Integration with Home Assistant Tools

This development setup works seamlessly with the existing Home Assistant validation tools:

- **YAML Validation**: Pre-commit hooks validate HA-specific YAML syntax
- **Entity Validation**: Reference validation runs automatically
- **Official HA Validation**: Integrated with Home Assistant's own validators

## Pre-commit Hooks

Automatically runs on git commits:
- Trailing whitespace removal
- End-of-file fixing
- YAML syntax checking (HA-compatible)
- Code formatting (ruff-format)
- Style checking (ruff-check)
- Type checking (mypy)
- HA-specific validation

## Tips for Development

1. **Always format before committing:**
   ```bash
   task dev:format
   ```

2. **Run the full workflow periodically:**
   ```bash
   task dev:workflow
   ```

3. **Use coverage reports to identify untested code:**
   ```bash
   task dev:test-coverage
   open htmlcov/index.html
   ```

4. **Pre-commit hooks catch issues early:**
   ```bash
   git add . && git commit -m "your changes"
   # Hooks run automatically
   ```

## Troubleshooting

### Virtual Environment Issues
```bash
rm .venv
uv sync
```

### Dependency Issues
```bash
# Update all development dependencies
task dev:update-deps

# Clean (reinstallation is done automatically with the other commands)
task dev:clean-dev
```

### Pre-commit Issues
```bash
# Reinstall hooks
task dev:pre-commit-init

# Skip hooks temporarily (not recommended)
git commit --no-verify -m "message"
```

This setup ensures consistent, high-quality Python code that integrates perfectly with the Home Assistant configuration management workflow.
