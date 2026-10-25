#!/usr/bin/env python3
"""Unit tests for reference_validator.py UUID support."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.reference_validator import ReferenceValidator


class TestReferenceValidatorUUID(unittest.TestCase):
    """Test UUID support in reference validator."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir)
        self.storage_dir = self.config_dir / ".storage"
        self.storage_dir.mkdir(exist_ok=True)

        # Create mock entity registry
        self.entity_registry_data = {
            "version": 1,
            "minor_version": 1,
            "data": {
                "entities": [
                    {
                        "entity_id": "binary_sensor.test_motion_battery",
                        "id": "88a52f17bf43cb276836f06ac5c07444",  # UUID from the issue
                        "platform": "test",
                        "unique_id": "test_motion_battery",
                        "device_id": "0c086f69ee6b3fa8411af7194876cbd7",
                        "disabled_by": None,
                    },
                    {
                        "entity_id": "sensor.disabled_sensor",
                        "id": "11223344556677889900aabbccddeeff",
                        "platform": "test",
                        "unique_id": "disabled_sensor",
                        "device_id": "disabled_device_id_123456789012",
                        "disabled_by": "user",
                    },
                    {
                        "entity_id": "sensor.normal_sensor",
                        "id": "aabbccddeeff00112233445566778899",
                        "platform": "test",
                        "unique_id": "normal_sensor",
                        "disabled_by": None,
                    },
                    {
                        "entity_id": "sensor.complex",
                        "id": "complexsensoridfortest12345678900",
                        "platform": "test",
                        "unique_id": "complex_sensor",
                        "disabled_by": None,
                    },
                ]
            },
        }

        # Create mock device registry
        self.device_registry_data = {
            "version": 1,
            "minor_version": 1,
            "data": {
                "devices": [
                    {
                        "id": "0c086f69ee6b3fa8411af7194876cbd7",  # Device ID
                        "name": "Test Motion Sensor",
                        "manufacturer": "Test",
                        "model": "Motion Sensor",
                        "disabled_by": None,
                    },
                    {
                        "id": "disabled_device_id_123456789012",
                        "name": "Disabled Device",
                        "manufacturer": "Test",
                        "model": "Disabled",
                        "disabled_by": "user",
                    },
                ]
            },
        }

        # Create mock area registry
        self.area_registry_data = {
            "version": 1,
            "minor_version": 1,
            "data": {"areas": [{"id": "living_room", "name": "Living Room"}]},
        }

        # Write registry files
        with open(self.storage_dir / "core.entity_registry", "w") as f:
            json.dump(self.entity_registry_data, f)

        with open(self.storage_dir / "core.device_registry", "w") as f:
            json.dump(self.device_registry_data, f)

        with open(self.storage_dir / "core.area_registry", "w") as f:
            json.dump(self.area_registry_data, f)
        self.validator = ReferenceValidator(str(self.config_dir))

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_is_uuid_format(self):
        """Test UUID format detection."""
        # Valid UUID format (32 hex chars)
        self.assertTrue(
            self.validator.is_uuid_format("88a52f17bf43cb276836f06ac5c07444")
        )
        self.assertTrue(
            self.validator.is_uuid_format("aabbccddeeff00112233445566778899")
        )

        # Invalid formats
        self.assertFalse(self.validator.is_uuid_format("sensor.kitchen_motion"))
        self.assertFalse(
            self.validator.is_uuid_format("88a52f17bf43cb276836f06ac5c0744")
        )  # Too short
        self.assertFalse(
            self.validator.is_uuid_format("88a52f17bf43cb276836f06ac5c074455")
        )  # Too long
        self.assertFalse(
            self.validator.is_uuid_format("88a52f17-bf43-cb27-6836-f06ac5c07444")
        )  # With hyphens
        self.assertFalse(
            self.validator.is_uuid_format("gghhiijjkkllmmnnooppqqrrssttuu99")
        )  # Invalid hex

    def test_extract_entity_registry_ids(self):
        """Test extraction of entity registry UUIDs."""
        # Test device-based automation (like in the GitHub issue)
        automation_data = {
            "triggers": [
                {
                    "type": "battery_level",
                    "device_id": "0c086f69ee6b3fa8411af7194876cbd7",
                    "entity_id": "88a52f17bf43cb276836f06ac5c07444",  # UUID entity ID
                    "domain": "sensor",
                    "trigger": "device",
                    "below": 20,
                }
            ]
        }

        registry_ids = self.validator.extract_entity_registry_ids(automation_data)
        self.assertEqual(registry_ids, {"88a52f17bf43cb276836f06ac5c07444"})

    def test_extract_entity_registry_ids_mixed(self):
        """Test extraction with mixed normal entity IDs and registry IDs."""
        mixed_data = {
            "entity_id": "sensor.normal_entity",  # Normal format
            "triggers": [
                {
                    "entity_id": "aabbccddeeff00112233445566778899",  # UUID format
                    "platform": "state",
                }
            ],
        }

        registry_ids = self.validator.extract_entity_registry_ids(mixed_data)
        self.assertEqual(registry_ids, {"aabbccddeeff00112233445566778899"})

    def test_get_entity_registry_id_mapping(self):
        """Test entity registry ID to entity_id mapping."""
        mapping = self.validator.get_entity_registry_id_mapping()

        expected_mapping = {
            "88a52f17bf43cb276836f06ac5c07444": "binary_sensor.test_motion_battery",
            "11223344556677889900aabbccddeeff": "sensor.disabled_sensor",
            "aabbccddeeff00112233445566778899": "sensor.normal_sensor",
            "complexsensoridfortest12345678900": "sensor.complex",
        }

        self.assertEqual(mapping, expected_mapping)

    def test_validate_valid_entity_registry_id(self):
        """Test validation of valid entity registry ID."""
        # Create a test automation file with UUID entity reference
        automation_data = [
            {
                "id": "test_automation",
                "alias": "Test Device Automation",
                "triggers": [
                    {
                        "type": "battery_level",
                        "device_id": "0c086f69ee6b3fa8411af7194876cbd7",
                        "entity_id": "88a52f17bf43cb276836f06ac5c07444",  # Valid UUID
                        "domain": "sensor",
                        "trigger": "device",
                        "below": 20,
                    }
                ],
                "action": [
                    {"service": "notify.mobile_app", "data": {"message": "Low battery"}}
                ],
            }
        ]

        test_file = self.config_dir / "test_automation.yaml"
        with open(test_file, "w") as f:
            yaml.dump(automation_data, f)

        # Validate the file
        result = self.validator.validate_file_references(test_file)
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)

    def test_validate_invalid_entity_registry_id(self):
        """Test validation of invalid entity registry ID."""
        # Create test automation with invalid UUID (32 hex chars but not in registry)
        automation_data = [
            {
                "id": "test_automation",
                "alias": "Test Device Automation",
                "triggers": [
                    {
                        "entity_id": "ffffffffffffffffffffffffffffffff",  # 32 hex chars
                        "platform": "state",
                    }
                ],
            }
        ]

        test_file = self.config_dir / "test_automation.yaml"
        with open(test_file, "w") as f:
            yaml.dump(automation_data, f)

        # Validate the file
        result = self.validator.validate_file_references(test_file)
        self.assertFalse(result)
        self.assertTrue(
            any(
                "Unknown entity registry ID" in error for error in self.validator.errors
            )
        )

    def test_validate_disabled_entity_registry_id(self):
        """Test validation of entity registry ID pointing to disabled entity."""
        # Create test automation with UUID pointing to disabled entity
        automation_data = [
            {
                "id": "test_automation",
                "triggers": [
                    {
                        "entity_id": "11223344556677889900aabbccddeeff",  # UUID
                        "platform": "state",
                    }
                ],
            }
        ]

        test_file = self.config_dir / "test_automation.yaml"
        with open(test_file, "w") as f:
            yaml.dump(automation_data, f)

        # Validate the file
        result = self.validator.validate_file_references(test_file)
        self.assertTrue(result)  # Should pass validation but generate warning
        self.assertTrue(
            any("disabled entity" in warning for warning in self.validator.warnings)
        )

    def test_validate_mixed_entity_formats(self):
        """Test validation with both normal entity IDs and registry UUIDs."""
        automation_data = [
            {
                "id": "mixed_automation",
                "triggers": [
                    {
                        "platform": "state",
                        "entity_id": "binary_sensor.test_motion_battery",  # Normal
                    },
                    {
                        "entity_id": "88a52f17bf43cb276836f06ac5c07444",  # UUID format
                        "platform": "device",
                    },
                ],
            }
        ]

        test_file = self.config_dir / "test_automation.yaml"
        with open(test_file, "w") as f:
            yaml.dump(automation_data, f)

        # Validate the file
        result = self.validator.validate_file_references(test_file)
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)

    def test_extract_entity_references_excludes_uuids(self):
        """Test that normal entity reference extraction excludes UUIDs."""
        mixed_data = {
            "entity_id": "sensor.normal_entity",
            "triggers": [
                {
                    "entity_id": "88a52f17bf43cb276836f06ac5c07444",  # UUID excluded
                    "platform": "state",
                },
                {
                    "entity_id": "binary_sensor.another_sensor",  # Normal included
                    "platform": "state",
                },
            ],
        }

        entity_refs = self.validator.extract_entity_references(mixed_data)
        # Should only contain normal format entity IDs
        expected_refs = {"sensor.normal_entity", "binary_sensor.another_sensor"}
        self.assertEqual(entity_refs, expected_refs)

    def test_is_template(self):
        """Test template detection."""
        # Valid template expressions
        self.assertTrue(
            self.validator.is_template("{{ states('sensor.temperature') }}")
        )
        self.assertTrue(
            self.validator.is_template(
                "Temperature is {{ state_attr('sensor.temp', 'value') }}°C"
            )
        )
        self.assertTrue(
            self.validator.is_template("{{states('binary_sensor.motion')}}")
        )
        self.assertTrue(self.validator.is_template("Value: {{ 25 + 5 }}"))

        # Invalid/non-template expressions
        self.assertFalse(self.validator.is_template("sensor.temperature"))
        self.assertFalse(self.validator.is_template("normal text"))
        self.assertFalse(self.validator.is_template("{ single brace }"))
        self.assertFalse(self.validator.is_template(""))

    def test_should_skip_entity_validation(self):
        """Test entity validation skip logic."""
        # Should skip - HA tags
        self.assertTrue(
            self.validator.should_skip_entity_validation("!input sensor_name")
        )
        self.assertTrue(self.validator.should_skip_entity_validation("!secret api_key"))
        self.assertTrue(
            self.validator.should_skip_entity_validation("!include entities.yaml")
        )

        # Should skip - UUID format
        self.assertTrue(
            self.validator.should_skip_entity_validation(
                "88a52f17bf43cb276836f06ac5c07444"
            )
        )

        # Should skip - Templates
        self.assertTrue(
            self.validator.should_skip_entity_validation("{{ states('sensor.temp') }}")
        )
        self.assertTrue(
            self.validator.should_skip_entity_validation(
                "Temperature {{ sensor.temp }}"
            )
        )

        # Should skip - Special keywords
        self.assertTrue(self.validator.should_skip_entity_validation("all"))
        self.assertTrue(self.validator.should_skip_entity_validation("none"))

        # Should NOT skip - Normal entity IDs
        self.assertFalse(
            self.validator.should_skip_entity_validation("sensor.temperature")
        )
        self.assertFalse(
            self.validator.should_skip_entity_validation("binary_sensor.motion")
        )
        self.assertFalse(
            self.validator.should_skip_entity_validation("light.living_room")
        )

    def test_extract_entity_references_with_templates(self):
        """Test entity reference extraction skips templates."""
        config_data = {
            "entity_id": "sensor.normal",  # Should be included
            "entity_ids": [
                "{{ states('sensor.template') }}",  # Should be skipped (template)
                "binary_sensor.door",  # Should be included
                "all",  # Should be skipped (special keyword)
                "none",  # Should be skipped (special keyword)
            ],
        }

        entity_refs = self.validator.extract_entity_references(config_data)
        expected_refs = {"sensor.normal", "binary_sensor.door"}
        self.assertEqual(entity_refs, expected_refs)

    def test_extract_entity_references_with_blueprint_inputs(self):
        """Test entity reference extraction skips blueprint inputs."""
        blueprint_data = {
            "entity_id": "!input motion_sensor",  # Should be skipped
            "entity_ids": [
                "!input door_sensor",  # Should be skipped
                "binary_sensor.actual_door",  # Should be included
                "!secret api_entity",  # Should be skipped
            ],
        }

        entity_refs = self.validator.extract_entity_references(blueprint_data)
        expected_refs = {"binary_sensor.actual_door"}
        self.assertEqual(entity_refs, expected_refs)

    def test_special_keywords_class_variable(self):
        """Test that special keywords are defined as class variable."""
        self.assertIn("all", ReferenceValidator.SPECIAL_KEYWORDS)
        self.assertIn("none", ReferenceValidator.SPECIAL_KEYWORDS)
        self.assertIsInstance(ReferenceValidator.SPECIAL_KEYWORDS, set)

    def test_validate_file_with_mixed_entity_types(self):
        """Test validation with templates, UUIDs, and normal entities mixed."""
        automation_data = [
            {
                "id": "complex_automation",
                "alias": "Complex Mixed Automation",
                "trigger": {
                    "platform": "template",
                    "value_template": (
                        "{{ states('sensor.complex') == 'on' }}"  # Template, ignored
                    ),
                },
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": "88a52f17bf43cb276836f06ac5c07444",  # Valid UUID
                        "state": "on",
                    }
                ],
                "action": [
                    {
                        "service": "light.turn_on",
                        "target": {
                            "entity_id": ["all"]  # Special keyword, should be ignored
                        },
                    },
                    {
                        "service": "notify.send",
                        "data": {
                            "message": (
                                "{{ now() }} - Motion detected"  # Template in data
                            )
                        },
                    },
                ],
            }
        ]

        test_file = self.config_dir / "complex_test.yaml"
        with open(test_file, "w") as f:
            yaml.dump(automation_data, f)

        # Should validate successfully
        result = self.validator.validate_file_references(test_file)
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)


if __name__ == "__main__":
    unittest.main()
