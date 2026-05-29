"""Tests that the validators honor a configurable config directory argument.

The Makefile passes $(LOCAL_CONFIG_PATH) to the validators so the tooling can
operate on a config dir other than the default ./config. These tests prove the
path argument is actually read (not ignored in favour of a hardcoded "config").
"""

# pylint: disable=import-error

import subprocess
import sys
from pathlib import Path

YAML_VALIDATOR = Path(__file__).parent.parent / "tools" / "yaml_validator.py"


def _run(config_dir):
    """Run yaml_validator.py against config_dir, return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(YAML_VALIDATOR), str(config_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_validates_passed_dir_valid(tmp_path):
    """A valid configuration.yaml in the passed dir → exit 0."""
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n  name: Test\n")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_validates_passed_dir_invalid(tmp_path):
    """Invalid YAML in the passed dir → non-zero exit.

    Proves the tool reads the supplied path rather than the default ./config:
    the repo's own ./config is valid, so a failure here can only come from the
    temp dir we pointed it at.
    """
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n  name: [unclosed\n")
    result = _run(tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
