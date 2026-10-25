"""Unit tests for validator improvements including blueprint support and validation."""

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.ha_config_validator import HAConfigValidator
from tools.yaml_validator import YAMLValidator


class TestValidatorImprovements(unittest.TestCase):
    """Test validator improvements for blueprint support and automation validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)

        self.yaml_validator = YAMLValidator(str(self.config_dir))
        self.ha_validator = HAConfigValidator(str(self.config_dir))

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_blueprint_automation_validation(self):
        """Test that blueprint-based automations pass validation."""
        # Blueprint automation using use_blueprint instead of triggers/actions
        blueprint_automation = [
            {
                "id": "blueprint_test",
                "alias": "Motion-activated Light",
                "use_blueprint": {
                    "path": "homeassistant/motion_light.yaml",
                    "input": {
                        "motion_entity": "binary_sensor.motion",
                        "light_target": "light.living_room",
                    },
                },
            }
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(blueprint_automation, f)

        # Should pass validation with both validators
        result = self.yaml_validator.validate_automations_structure(automations_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)

    def test_plural_triggers_actions_validation(self):
        """Test that automations with plural triggers/actions pass validation."""
        automation_with_plurals = [
            {
                "id": "plural_test",
                "alias": "Automation with plural fields",
                "triggers": [  # plural form
                    {"platform": "state", "entity_id": "sensor.test"},
                    {"platform": "time", "at": "12:00:00"},
                ],
                "actions": [  # plural form
                    {"service": "light.turn_on", "entity_id": "light.test"},
                    {"service": "notify.send", "data": {"message": "Test"}},
                ],
            }
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(automation_with_plurals, f)

        # Should pass validation
        result = self.yaml_validator.validate_automations_structure(automations_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)

    def test_singular_triggers_actions_validation(self):
        """Test automations with singular triggers/actions still pass."""
        automation_with_singulars = [
            {
                "id": "singular_test",
                "alias": "Automation with singular fields",
                "trigger": {
                    "platform": "state",
                    "entity_id": "sensor.test",
                },  # singular form
                "action": {
                    "service": "light.turn_on",
                    "entity_id": "light.test",
                },  # singular form
            }
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(automation_with_singulars, f)

        # Should pass validation
        result = self.yaml_validator.validate_automations_structure(automations_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)

    def test_automation_missing_required_fields(self):
        """Test that automations missing both trigger forms fail validation."""
        invalid_automation = [
            {
                "id": "invalid_test",
                "alias": "Invalid automation - missing triggers/actions",
                # Missing both trigger/triggers and action/actions
            }
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(invalid_automation, f)

        # Should fail validation
        result = self.yaml_validator.validate_automations_structure(automations_file)
        self.assertFalse(result)
        self.assertTrue(
            any(
                "missing" in error and "trigger" in error
                for error in self.yaml_validator.errors
            )
        )
        self.assertTrue(
            any(
                "missing" in error and "action" in error
                for error in self.yaml_validator.errors
            )
        )

    def test_blueprint_script_validation(self):
        """Test that blueprint-based scripts pass validation."""
        blueprint_scripts = {
            "blueprint_script": {
                "alias": "Blueprint Script",
                "use_blueprint": {
                    "path": "custom/notification_script.yaml",
                    "input": {"message": "Test message", "target": "mobile_app"},
                },
            }
        }

        scripts_file = self.config_dir / "scripts.yaml"
        with open(scripts_file, "w") as f:
            yaml.dump(blueprint_scripts, f)

        # Should pass validation
        result = self.yaml_validator.validate_scripts_structure(scripts_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)

    def test_regular_script_validation(self):
        """Test that regular scripts with sequence still pass validation."""
        regular_scripts = {
            "regular_script": {
                "alias": "Regular Script",
                "sequence": [
                    {"service": "light.turn_on", "entity_id": "light.test"},
                    {"delay": {"seconds": 5}},
                    {"service": "light.turn_off", "entity_id": "light.test"},
                ],
            }
        }

        scripts_file = self.config_dir / "scripts.yaml"
        with open(scripts_file, "w") as f:
            yaml.dump(regular_scripts, f)

        # Should pass validation
        result = self.yaml_validator.validate_scripts_structure(scripts_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)

    def test_script_missing_required_fields(self):
        """Test that scripts missing both sequence and use_blueprint fail validation."""
        invalid_scripts = {
            "invalid_script": {
                "alias": "Invalid Script",
                # Missing both sequence and use_blueprint
            }
        }

        scripts_file = self.config_dir / "scripts.yaml"
        with open(scripts_file, "w") as f:
            yaml.dump(invalid_scripts, f)

        # Should fail validation
        result = self.yaml_validator.validate_scripts_structure(scripts_file)
        self.assertFalse(result)
        self.assertTrue(
            any(
                "missing" in error and ("sequence" in error or "use_blueprint" in error)
                for error in self.yaml_validator.errors
            )
        )

    def test_ha_config_validator_blueprint_automation(self):
        """Test HAConfigValidator with blueprint automations."""
        blueprint_automation = [
            {
                "id": "ha_blueprint_test",
                "alias": "HA Blueprint Test",
                "use_blueprint": {
                    "path": "test.yaml",
                    "input": {"entity": "sensor.test"},
                },
            }
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(blueprint_automation, f)

        # Validate using ha_config_validator
        self.ha_validator.validate_automations_file()

        # Should pass without errors
        self.assertEqual(len(self.ha_validator.errors), 0)

    def test_ha_config_validator_blueprint_script(self):
        """Test HAConfigValidator with blueprint scripts."""
        blueprint_scripts = {
            "ha_blueprint_script": {
                "alias": "HA Blueprint Script",
                "use_blueprint": {
                    "path": "test_script.yaml",
                    "input": {"message": "test"},
                },
            }
        }

        scripts_file = self.config_dir / "scripts.yaml"
        with open(scripts_file, "w") as f:
            yaml.dump(blueprint_scripts, f)

        # Validate using ha_config_validator
        self.ha_validator.validate_scripts_file()

        # Should pass without errors
        self.assertEqual(len(self.ha_validator.errors), 0)

    def test_mixed_automation_validation(self):
        """Test validation with mix of blueprint and regular automations."""
        mixed_automations = [
            {
                "id": "blueprint_auto",
                "alias": "Blueprint Automation",
                "use_blueprint": {
                    "path": "motion.yaml",
                    "input": {"sensor": "binary_sensor.motion"},
                },
            },
            {
                "id": "regular_auto",
                "alias": "Regular Automation",
                "trigger": {"platform": "state", "entity_id": "sensor.temp"},
                "action": {
                    "service": "climate.set_temperature",
                    "data": {"temperature": 20},
                },
            },
            {
                "id": "plural_auto",
                "alias": "Plural Automation",
                "triggers": [{"platform": "time", "at": "08:00:00"}],
                "actions": [{"service": "light.turn_on"}],
            },
        ]

        automations_file = self.config_dir / "automations.yaml"
        with open(automations_file, "w") as f:
            yaml.dump(mixed_automations, f)

        # Should all pass validation
        result = self.yaml_validator.validate_automations_structure(automations_file)
        self.assertTrue(result)
        self.assertEqual(len(self.yaml_validator.errors), 0)


if __name__ == "__main__":
    unittest.main()
