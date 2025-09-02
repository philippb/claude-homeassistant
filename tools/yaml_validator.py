#!/usr/bin/env python3
"""YAML syntax validator for Home Assistant configuration files."""

import sys
from pathlib import Path
from typing import List

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
    "!include_dir_merge_named", include_dir_merge_named_constructor
)
HAYamlLoader.add_constructor(
    "!include_dir_named", include_dir_named_constructor
)
HAYamlLoader.add_constructor(
    "!include_dir_merge_list", include_dir_merge_list_constructor
)
HAYamlLoader.add_constructor("!include_dir_list", include_dir_list_constructor)
HAYamlLoader.add_constructor("!input", input_constructor)
HAYamlLoader.add_constructor("!secret", secret_constructor)


class YAMLValidator:
    """Validates YAML syntax and basic structure for Home Assistant files."""

    def __init__(self, config_dir: str = "config"):
        """Initialize the YAMLValidator."""
        self.config_dir = Path(config_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_yaml_syntax(self, file_path: Path) -> bool:
        """Validate YAML syntax of a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                yaml.load(f, Loader=HAYamlLoader)
            return True
        except yaml.YAMLError as e:
            self.errors.append(f"{file_path}: YAML syntax error - {e}")
            return False
        except UnicodeDecodeError as e:
            self.errors.append(f"{file_path}: Encoding error - {e}")
            return False
        except Exception as e:
            self.errors.append(f"{file_path}: Unexpected error - {e}")
            return False

    def validate_file_encoding(self, file_path: Path) -> bool:
        """Ensure file is UTF-8 encoded as required by Home Assistant."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.read()
            return True
        except UnicodeDecodeError:
            self.errors.append(f"{file_path}: File must be UTF-8 encoded")
            return False

    def validate_configuration_structure(self, file_path: Path) -> bool:
        """Validate basic Home Assistant configuration.yaml structure."""
        if file_path.name != "configuration.yaml":
            return True

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = yaml.load(f, Loader=HAYamlLoader)

            if not isinstance(config, dict):
                self.errors.append(f"{file_path}: Configuration must be a dictionary")
                return False

            # Check for common configuration issues
            if "homeassistant" not in config:
                self.warnings.append(f"{file_path}: Missing 'homeassistant' section")

            # Check for deprecated keys
            deprecated_keys = ["discovery", "introduction"]
            for key in deprecated_keys:
                if key in config:
                    self.warnings.append(f"{file_path}: '{key}' is deprecated")

            return True
        except Exception as e:
            self.errors.append(f"{file_path}: Failed to validate structure - {e}")
            return False

    def validate_automations_structure(self, file_path: Path) -> bool:
        """Validate automations.yaml structure."""
        if file_path.name != "automations.yaml":
            return True

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                automations = yaml.load(f, Loader=HAYamlLoader)

            if automations is None:
                return True  # Empty file is valid

            if not isinstance(automations, list):
                self.errors.append(f"{file_path}: Automations must be a list")
                return False

            all_valid = True
            for i, automation in enumerate(automations):
                if not isinstance(automation, dict):
                    self.errors.append(
                        f"{file_path}: Automation {i} must be a dictionary"
                    )
                    all_valid = False
                    continue

                # Check required fields (both singular and plural forms are valid)
                # Blueprint automations use 'use_blueprint' instead of
                # direct triggers/actions
                if "use_blueprint" not in automation:
                    if "trigger" not in automation and "triggers" not in automation:
                        self.errors.append(
                            f"{file_path}: Automation {i} missing 'trigger' "
                            f"or 'triggers'"
                        )
                        all_valid = False
                    if "action" not in automation and "actions" not in automation:
                        self.errors.append(
                            f"{file_path}: Automation {i} missing 'action' or 'actions'"
                        )
                        all_valid = False

                # Check for alias (recommended)
                if "alias" not in automation:
                    self.warnings.append(
                        f"{file_path}: Automation {i} missing 'alias' " f"(recommended)"
                    )

            return all_valid
        except Exception as e:
            self.errors.append(
                f"{file_path}: Failed to validate automations structure - {e}"
            )
            return False

    def validate_scripts_structure(self, file_path: Path) -> bool:
        """Validate scripts.yaml structure."""
        if file_path.name != "scripts.yaml":
            return True

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                scripts = yaml.load(f, Loader=HAYamlLoader)

            if scripts is None:
                return True  # Empty file is valid

            if not isinstance(scripts, dict):
                self.errors.append(f"{file_path}: Scripts must be a dictionary")
                return False

            all_valid = True
            for script_name, script_config in scripts.items():
                if not isinstance(script_config, dict):
                    self.errors.append(
                        f"{file_path}: Script '{script_name}' must be a " f"dictionary"
                    )
                    all_valid = False
                    continue

                # Check required fields
                # Blueprint scripts use 'use_blueprint' instead of direct sequence
                if (
                    "use_blueprint" not in script_config
                    and "sequence" not in script_config
                ):
                    self.errors.append(
                        f"{file_path}: Script '{script_name}' missing required "
                        f"'sequence' or 'use_blueprint'"
                    )
                    all_valid = False

            return all_valid
        except Exception as e:
            self.errors.append(
                f"{file_path}: Failed to validate scripts structure - {e}"
            )
            return False

    def get_yaml_files(self) -> List[Path]:
        """Get all YAML files in the config directory."""
        yaml_files: List[Path] = []
        for pattern in ["*.yaml", "*.yml"]:
            yaml_files.extend(self.config_dir.glob(pattern))

        # Skip blueprints directory - these are templates and don't need validation
        return yaml_files

    def validate_all(self) -> bool:
        """Validate all YAML files in the config directory."""
        if not self.config_dir.exists():
            self.errors.append(f"Config directory {self.config_dir} does not exist")
            return False

        yaml_files = self.get_yaml_files()
        if not yaml_files:
            self.warnings.append("No YAML files found in config directory")
            return True

        all_valid = True

        for file_path in yaml_files:
            # Skip secrets.yaml as it may contain sensitive data
            if file_path.name == "secrets.yaml":
                continue

            if not self.validate_file_encoding(file_path):
                all_valid = False
                continue

            if not self.validate_yaml_syntax(file_path):
                all_valid = False
                continue

            # Structure validation for specific files
            self.validate_configuration_structure(file_path)
            self.validate_automations_structure(file_path)
            self.validate_scripts_structure(file_path)

        return all_valid

    def print_results(self):
        """Print validation results."""
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
            print("✅ All YAML files are valid!")
        elif not self.errors:
            print("✅ YAML syntax is valid (with warnings)")
        else:
            print("❌ YAML validation failed")


def main():
    """Run YAML syntax validation from command line."""
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"

    validator = YAMLValidator(config_dir)
    is_valid = validator.validate_all()
    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
