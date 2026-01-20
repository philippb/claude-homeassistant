#!/usr/bin/env python3
"""Official Home Assistant configuration validator using the actual HA package.

This leverages Home Assistant's own validation tools for the most
accurate results.
"""

import subprocess
import sys
from pathlib import Path
from typing import List


class HAOfficialValidator:
    """Validates Home Assistant configuration using the official HA package."""

    def __init__(self, config_dir: Path = Path("config")):
        """Initialize the HAOfficialValidator."""
        self.config_dir = config_dir.resolve()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def run_ha_check_config(self) -> bool:
        """Run Home Assistant's official check_config script."""
        try:
            # Use the hass command to check configuration
            cmd = [
                sys.executable,
                "-m",
                "homeassistant",
                "--config",
                str(self.config_dir),
                "--script",
                "check_config",
            ]

            # Run the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.config_dir),
            )

            # Parse the output
            self.parse_check_config_output(result.stdout, result.stderr)

            # Return success if exit code is 0
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.errors.append("Home Assistant configuration check timed out")
            return False
        except FileNotFoundError:
            self.errors.append(
                "Home Assistant not found. "
                "Please install with: pip install homeassistant"
            )
            return False
        except Exception as e:
            self.errors.append(f"Failed to run Home Assistant config check: {e}")
            return False

    def parse_check_config_output(self, stdout: str, stderr: str):
        """Parse Home Assistant check_config output."""
        # Parse stdout
        if stdout:
            lines = stdout.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Look for specific patterns
                if "Testing configuration at" in line:
                    self.info.append(f"HA Check: {line}")
                elif "Configuration check successful!" in line:
                    self.info.append(f"HA Check: {line}")
                elif "errors" in line.lower() and "found" in line.lower():
                    if "0 errors" in line.lower():
                        self.info.append(f"HA Check: {line}")
                    else:
                        self.errors.append(f"HA Check: {line}")
                elif "ERROR" in line or "Error" in line:
                    self.errors.append(f"HA Check: {line}")
                elif "WARNING" in line or "Warning" in line:
                    self.warnings.append(f"HA Check: {line}")
                else:
                    # Include other informational lines
                    if line and not line.startswith("INFO:"):
                        self.info.append(f"HA Check: {line}")

        # Parse stderr for actual errors
        if stderr:
            lines = stderr.split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Filter out debug/info messages
                if any(x in line.lower() for x in ["debug", "info:", "starting"]):
                    continue

                # Skip common non-error messages
                if any(
                    x in line.lower()
                    for x in [
                        "voluptuous",
                        "setup of domain",
                        "setup of platform",
                        "loading",
                        "initialized",
                    ]
                ):
                    continue

                # This is likely an actual error
                self.errors.append(f"HA Error: {line}")

    def validate_all(self) -> bool:
        """Run complete validation using Home Assistant."""
        if not self.config_dir.exists():
            self.errors.append(f"Config directory {self.config_dir} does not exist")
            return False

        # Check if configuration.yaml exists
        config_file = self.config_dir / "configuration.yaml"
        if not config_file.exists():
            self.errors.append("configuration.yaml not found")
            return False

        # Run the official Home Assistant validation
        return self.run_ha_check_config()

    def print_results(self):
        """Print validation results."""
        if self.info:
            print("INFO:")
            for info in self.info:
                print(f"  ℹ️  {info}")
            print()

        if self.errors:
            print("ERRORS:")
            for error in self.errors:
                print(f"  ❌ {error}")
            print()

        if self.warnings:
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")
            print()

        if not self.errors and not self.warnings:
            print("✅ Home Assistant configuration is valid!")
        elif not self.errors:
            print("✅ Home Assistant configuration is valid (with warnings)")
        else:
            print("❌ Home Assistant configuration validation failed")


def main():
    """Run Home Assistant configuration validation from command line."""
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"

    validator = HAOfficialValidator(Path(config_dir))
    is_valid = validator.validate_all()
    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
