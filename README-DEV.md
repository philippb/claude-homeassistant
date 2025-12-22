# Development Setup for Home Assistant Config Tools

This directory contains a complete Python development environment with modern tooling for code quality, formatting, and testing.

## Quick Start

1. **Setup development environment:**
   ```bash
   make -f Makefile.dev dev-setup
   ```

2. **Format and check code:**
   ```bash
   make -f Makefile.dev dev-format
   make -f Makefile.dev dev-lint
   ```

3. **Run tests:**
   ```bash
   make -f Makefile.dev dev-test
   ```

## Development Tools Included

### Code Quality
- **Black** - Automatic code formatting (PEP8 compliant)
- **isort** - Import statement sorting
- **flake8** - Style guide enforcement with additional plugins
- **pylint** - Comprehensive code analysis
- **mypy** - Static type checking

### Testing
- **pytest** - Modern testing framework
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Mocking utilities

### Automation
- **pre-commit** - Git hooks for automated checks
- **yamllint** - YAML file validation (for HA configs)

## File Structure

```
public/
├── venv/                    # Symlinked to ../venv/
├── tools/                   # Python validation scripts
├── config/                  # Home Assistant configuration
├── pyproject.toml          # Python project configuration
├── requirements-dev.txt    # Development dependencies
├── .pre-commit-config.yaml # Pre-commit hook configuration
├── .yamllint.yml          # YAML linting rules
├── Makefile               # Main project commands
├── Makefile.dev          # Development-specific commands
└── README-DEV.md         # This file
```

## Available Commands

### Development Workflow
```bash
# Complete development setup
make -f Makefile.dev dev-setup

# Format code automatically
make -f Makefile.dev dev-format

# Run all code quality checks
make -f Makefile.dev dev-check-all

# Run tests with coverage
make -f Makefile.dev dev-test-coverage

# Full development workflow
make -f Makefile.dev dev-workflow
```

### Pre-commit Hooks
```bash
# Install git hooks
make -f Makefile.dev dev-pre-commit

# Run hooks on all files
make -f Makefile.dev dev-pre-commit-all
```

### Maintenance
```bash
# Update dependencies
make -f Makefile.dev dev-update-deps

# Clean development artifacts
make -f Makefile.dev dev-clean-dev
```

## Configuration Details

### Black (Code Formatting)
- Line length: 88 characters
- Target Python version: 3.12+
- Automatically formats all Python files

### isort (Import Sorting)
- Profile: black (compatible with Black formatter)
- Sections: FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, LOCALFOLDER

### flake8 (Style Checking)
- Max line length: 88 characters
- Ignores E203, W503, E501 (Black compatibility)
- Additional plugins: flake8-docstrings, flake8-bugbear

### mypy (Type Checking)
- Strict type checking enabled
- Ignores missing imports for third-party libraries
- Excludes test files from strict checking

### pylint (Code Analysis)
- Configured for Home Assistant development
- Disabled verbose warnings for cleaner output
- Max line length: 88 characters

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
- Code formatting (Black + isort)
- Style checking (flake8)
- Type checking (mypy)
- Code analysis (pylint)
- HA-specific validation

## Tips for Development

1. **Always format before committing:**
   ```bash
   make -f Makefile.dev dev-format
   ```

2. **Run the full workflow periodically:**
   ```bash
   make -f Makefile.dev dev-workflow
   ```

3. **Use coverage reports to identify untested code:**
   ```bash
   make -f Makefile.dev dev-test-coverage
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
# Recreate symlink if needed
rm venv && ln -sf ../venv venv

# Verify symlink works
ls -la venv
```

### Dependency Issues
```bash
# Update all development dependencies
make -f Makefile.dev dev-update-deps

# Clean and reinstall
make -f Makefile.dev dev-clean-dev
make -f Makefile.dev dev-install
```

### Pre-commit Issues
```bash
# Reinstall hooks
make -f Makefile.dev dev-pre-commit

# Skip hooks temporarily (not recommended)
git commit --no-verify -m "message"
```

This setup ensures consistent, high-quality Python code that integrates perfectly with the Home Assistant configuration management workflow.
