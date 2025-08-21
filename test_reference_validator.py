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

        # Write registry files
        with open(self.storage_dir / "core.entity_registry", "w") as f:
            json.dump(self.entity_registry_data, f)

        with open(self.storage_dir / "core.device_registry", "w") as f:
            json.dump(self.device_registry_data, f)

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


if __name__ == "__main__":
    unittest.main()
