#!/usr/bin/env python3
"""Home Assistant configuration validator using HA's built-in validation.

This script performs deep validation using Home Assistant's own
configuration checking.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


class HAYamlLoader(yaml.SafeLoader):
    """Custom YAML loader that handles Home Assistant specific tags."""

    pass


def include_constructor(loader, node):
    """Handle !include tag."""
    filename = loader.construct_scalar(node)
    return f"!include {filename}"

def include_dir_named_constructor(loader, node):
    """Handle !include_dir_named tag."""
    dirname = loader.construct_scalar(node)
    return f"!include_dir_named {dirname}"

def include_dir_merge_named_constructor(loader, node):
    """Handle !include_dir_merge_named tag."""
    dirname = loader.construct_scalar(node)
    return f"!include_dir_merge_named {dirname}"


def include_dir_merge_list_constructor(loader, node):
    """Handle !include_dir_merge_list tag."""
    dirname = loader.construct_scalar(node)
    return f"!include_dir_merge_list {dirname}"


def include_dir_list_constructor(loader, node):
    """Handle !include_dir_list tag."""
    dirname = loader.construct_scalar(node)
    return f"!include_dir_list {dirname}"


def input_constructor(loader, node):
    """Handle !input tag for blueprints."""
    input_name = loader.construct_scalar(node)
    return f"!input {input_name}"


def secret_constructor(loader, node):
    """Handle !secret tag."""
    secret_name = loader.construct_scalar(node)
    return f"!secret {secret_name}"


# Register custom constructors
HAYamlLoader.add_constructor("!include", include_constructor)
HAYamlLoader.add_constructor(
    "!include_dir_named", include_dir_named_constructor
)
HAYamlLoader.add_constructor(
    "!include_dir_merge_named", include_dir_merge_named_constructor
)
HAYamlLoader.add_constructor(
    "!include_dir_merge_list", include_dir_merge_list_constructor
)
HAYamlLoader.add_constructor("!include_dir_list", include_dir_list_constructor)
HAYamlLoader.add_constructor("!input", input_constructor)
HAYamlLoader.add_constructor("!secret", secret_constructor)


class HAConfigValidator:
    """Validates Home Assistant configuration using HA's check_config tool."""

    def __init__(self, config_dir: str = "config"):
        """Initialize the validator with config directory."""
        self.config_dir = Path(config_dir).resolve()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def check_ha_installation(self) -> bool:
        """Check if Home Assistant is available for configuration checking."""
        try:
            # Try to run hass --version
            result = subprocess.run(
                ["hass", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self.info.append(f"Using Home Assistant: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try python -m homeassistant --version
        try:
            result = subprocess.run(
                ["python", "-m", "homeassistant", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                self.info.append(f"Using Home Assistant: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        self.warnings.append(
            "Home Assistant not found in PATH. Will perform basic validation only."
        )
        return False

    def run_ha_check_config(self) -> bool:
        """Run Home Assistant's check_config script."""
        if not self.check_ha_installation():
            return self.run_basic_validation()

        try:
            # First try the hass command
            cmd = [
                "hass",
                "--config",
                str(self.config_dir),
                "--script",
                "check_config",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0 and "No module named" in result.stderr:
                # Try alternative command
                cmd = [
                    "python",
                    "-m",
                    "homeassistant",
                    "--config",
                    str(self.config_dir),
                    "--script",
                    "check_config",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Parse output
            if result.stdout:
                self.parse_check_config_output(result.stdout)

            if result.stderr:
                self.parse_check_config_errors(result.stderr)

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.errors.append("Home Assistant configuration check timed out")
            return False
        except Exception as e:
            self.errors.append(f"Failed to run HA config check: {e}")
            return self.run_basic_validation()

    def parse_check_config_output(self, output: str):
        """Parse Home Assistant check_config output."""
        lines = output.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for common patterns
            if line.startswith("ERROR"):
                self.errors.append(f"HA Check: {line}")
            elif line.startswith("WARNING"):
                self.warnings.append(f"HA Check: {line}")
            elif "successful" in line.lower():
                self.info.append(f"HA Check: {line}")
            elif "error" in line.lower():
                self.errors.append(f"HA Check: {line}")
            elif "warning" in line.lower():
                self.warnings.append(f"HA Check: {line}")

    def parse_check_config_errors(self, stderr: str):
        """Parse Home Assistant check_config error output."""
        lines = stderr.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Filter out common non-error messages
            if any(x in line.lower() for x in ["debug", "info", "starting"]):
                continue

            if line:
                self.errors.append(f"HA Error: {line}")

    def run_basic_validation(self) -> bool:
        """Run basic configuration validation without HA."""
        all_valid = True

        # Check basic file structure
        config_file = self.config_dir / "configuration.yaml"
        if not config_file.exists():
            self.errors.append("configuration.yaml not found")
            return False

        # Validate configuration.yaml syntax and basic structure
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                self.errors.append("configuration.yaml must contain a dictionary")
                all_valid = False
            else:
                # Check for required sections
                if "homeassistant" not in config:
                    self.warnings.append(
                        "Missing 'homeassistant' section in configuration.yaml"
                    )

                # Check for common mistakes
                self.validate_basic_config_structure(config)

        except yaml.YAMLError as e:
            self.errors.append(f"YAML syntax error in configuration.yaml: {e}")
            all_valid = False
        except Exception as e:
            self.errors.append(f"Error reading configuration.yaml: {e}")
            all_valid = False

        # Validate other common files
        self.validate_automations_file()
        self.validate_scripts_file()
        self.validate_secrets_file()

        return all_valid

    def validate_basic_config_structure(self, config: Dict[str, Any]):
        """Validate basic configuration structure."""
        # Check homeassistant section
        if "homeassistant" in config:
            ha_config = config["homeassistant"]
            if isinstance(ha_config, dict):
                # Check for required fields
                if "latitude" not in ha_config or "longitude" not in ha_config:
                    self.warnings.append(
                        "Missing latitude/longitude in homeassistant section"
                    )

                if "time_zone" not in ha_config:
                    self.warnings.append("Missing time_zone in homeassistant section")

        # Check for deprecated keys
        deprecated_keys = ["discovery", "introduction", "cloud"]
        for key in deprecated_keys:
            if key in config:
                if key == "cloud":
                    self.warnings.append(f"'{key}' configuration should be done via UI")
                else:
                    self.warnings.append(f"'{key}' is deprecated and can be removed")

        # Check for common integration configurations
        self.check_integration_configs(config)

    def check_integration_configs(self, config: Dict[str, Any]):
        """Check common integration configurations."""
        # Check logger configuration
        if "logger" in config:
            logger_config = config["logger"]
            if isinstance(logger_config, dict):
                if "logs" in logger_config and not isinstance(
                    logger_config["logs"], dict
                ):
                    self.errors.append("logger.logs must be a dictionary")

        # Check recorder configuration
        if "recorder" in config:
            recorder_config = config["recorder"]
            if isinstance(recorder_config, dict):
                if "db_url" in recorder_config:
                    db_url = recorder_config["db_url"]
                    if not isinstance(db_url, str) or not db_url.startswith(
                        ("sqlite:///", "mysql://", "postgresql://")
                    ):
                        self.warnings.append("recorder.db_url format may be invalid")

        # Check HTTP configuration
        if "http" in config:
            http_config = config["http"]
            if isinstance(http_config, dict):
                if "ssl_certificate" in http_config or "ssl_key" in http_config:
                    ssl_cert = http_config.get("ssl_certificate")
                    ssl_key = http_config.get("ssl_key")
                    if ssl_cert and not Path(ssl_cert).exists():
                        self.errors.append(
                            f"SSL certificate file not found: {ssl_cert}"
                        )
                    if ssl_key and not Path(ssl_key).exists():
                        self.errors.append(f"SSL key file not found: {ssl_key}")

    def validate_automations_file(self):
        """Validate automations.yaml file."""
        automations_file = self.config_dir / "automations.yaml"
        if not automations_file.exists():
            return

        try:
            with open(automations_file, "r") as f:
                automations = yaml.safe_load(f)

            if automations is not None and not isinstance(automations, list):
                self.errors.append("automations.yaml must contain a list")
            elif isinstance(automations, list):
                for i, automation in enumerate(automations):
                    if not isinstance(automation, dict):
                        self.errors.append(f"Automation {i} must be a dictionary")
                        continue

                    # Check required fields (both singular and plural forms are valid)
                    # Blueprint automations use 'use_blueprint' instead of
                    # direct triggers/actions
                    if "use_blueprint" not in automation:
                        if "trigger" not in automation and "triggers" not in automation:
                            self.errors.append(
                                f"Automation {i} missing required 'trigger' or "
                                f"'triggers'"
                            )
                        if "action" not in automation and "actions" not in automation:
                            self.errors.append(
                                f"Automation {i} missing required 'action' or 'actions'"
                            )

        except yaml.YAMLError as e:
            self.errors.append(f"YAML syntax error in automations.yaml: {e}")
        except Exception as e:
            self.errors.append(f"Error reading automations.yaml: {e}")

    def validate_scripts_file(self):
        """Validate scripts.yaml file."""
        scripts_file = self.config_dir / "scripts.yaml"
        if not scripts_file.exists():
            return

        try:
            with open(scripts_file, "r") as f:
                scripts = yaml.safe_load(f)

            if scripts is not None and not isinstance(scripts, dict):
                self.errors.append("scripts.yaml must contain a dictionary")
            elif isinstance(scripts, dict):
                for script_name, script_config in scripts.items():
                    if not isinstance(script_config, dict):
                        self.errors.append(
                            f"Script '{script_name}' must be a dictionary"
                        )
                        continue

                    # Check required fields
                    # Blueprint scripts use 'use_blueprint' instead of direct sequence
                    if (
                        "use_blueprint" not in script_config
                        and "sequence" not in script_config
                    ):
                        self.errors.append(
                            f"Script '{script_name}' missing required "
                            f"'sequence' or 'use_blueprint'"
                        )

        except yaml.YAMLError as e:
            self.errors.append(f"YAML syntax error in scripts.yaml: {e}")
        except Exception as e:
            self.errors.append(f"Error reading scripts.yaml: {e}")

    def validate_secrets_file(self):
        """Validate secrets.yaml file exists and is accessible."""
        secrets_file = self.config_dir / "secrets.yaml"
        if not secrets_file.exists():
            self.warnings.append("secrets.yaml not found (this is optional)")
            return

        try:
            with open(secrets_file, "r") as f:
                secrets = yaml.safe_load(f)

            if secrets is not None and not isinstance(secrets, dict):
                self.errors.append("secrets.yaml must contain a dictionary")

            # We don't validate secret values for security reasons

        except yaml.YAMLError as e:
            self.errors.append(f"YAML syntax error in secrets.yaml: {e}")
        except Exception as e:
            self.errors.append(f"Error reading secrets.yaml: {e}")

    def validate_all(self) -> bool:
        """Run all validation checks."""
        if not self.config_dir.exists():
            self.errors.append(f"Config directory {self.config_dir} does not exist")
            return False

        # Try HA's built-in validation first
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
    """Run main function for command line usage."""
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"

    validator = HAConfigValidator(config_dir)
    is_valid = validator.validate_all()
    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
