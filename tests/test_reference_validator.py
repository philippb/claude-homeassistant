"""Unit tests for reference_validator.py.

Tests for entity reference validation, specifically:
1. Template entities use default_entity_id/name (NOT unique_id)
2. Automation id is NOT treated as entity_id
3. zone.* references (except zone.home) are validated
4. persistent_notification.* references are validated
"""

# pylint: disable=import-error,redefined-outer-name

import json
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from tools.reference_validator import ReferenceValidator


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory for testing."""
    temp = Path(tempfile.mkdtemp(prefix="validator_test_"))
    storage = temp / ".storage"
    storage.mkdir()

    # Create minimal entity registry
    entity_registry = {
        "data": {
            "entities": [
                {"entity_id": "light.living_room", "id": "abc123"},
                {"entity_id": "sensor.temperature", "id": "def456"},
            ]
        }
    }
    (storage / "core.entity_registry").write_text(json.dumps(entity_registry))

    # Create minimal device registry
    device_registry = {"data": {"devices": []}}
    (storage / "core.device_registry").write_text(json.dumps(device_registry))

    yield temp
    if temp.exists():
        shutil.rmtree(temp)


class TestTemplateEntityDerivation:
    """Tests for template entity ID derivation."""

    def test_unique_id_not_used_for_entity_derivation(self, temp_config_dir):
        """Does not use unique_id to derive entity_id."""
        config = {
            "template": [
                {
                    "sensor": [
                        {
                            "name": "My Sensor",
                            "unique_id": "my_unique_sensor_id",
                            "state": "{{ 42 }}",
                        }
                    ]
                }
            ]
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        # Should derive from name, NOT unique_id
        assert "sensor.my_sensor" in entities
        assert "sensor.my_unique_sensor_id" not in entities

    def test_default_entity_id_used_when_present(self, temp_config_dir):
        """Uses default_entity_id when present."""
        config = {
            "template": [
                {
                    "sensor": [
                        {
                            "name": "My Sensor",
                            "default_entity_id": "custom_sensor_name",
                            "unique_id": "my_unique_id",
                            "state": "{{ 42 }}",
                        }
                    ]
                }
            ]
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        # Should use default_entity_id
        assert "sensor.custom_sensor_name" in entities
        # Should NOT use unique_id or name
        assert "sensor.my_unique_id" not in entities
        assert "sensor.my_sensor" not in entities

    def test_name_used_when_no_default_entity_id(self, temp_config_dir):
        """Name should be slugified when no default_entity_id."""
        config = {
            "template": [
                {
                    "sensor": [
                        {
                            "name": "Living Room Temperature",
                            "state": "{{ 72 }}",
                        }
                    ]
                }
            ]
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "sensor.living_room_temperature" in entities


class TestAutomationEntityDerivation:
    """Tests for automation entity ID derivation."""

    def test_automation_id_not_used_as_entity_id(self, temp_config_dir):
        """Automation 'id' field should NOT be used as entity_id."""
        automations = [
            {
                "id": "1234567890",
                "alias": "Turn On Lights",
                "trigger": [],
                "action": [],
            }
        ]
        (temp_config_dir / "automations.yaml").write_text(yaml.dump(automations))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        # Should NOT create entity from id
        assert "automation.1234567890" not in entities
        # Should create entity from alias
        assert "automation.turn_on_lights" in entities

    def test_automation_alias_slugified(self, temp_config_dir):
        """Automation alias should be properly slugified."""
        automations = [
            {
                "id": "abc123",
                "alias": "My-Complex Automation Name!",
                "trigger": [],
                "action": [],
            }
        ]
        (temp_config_dir / "automations.yaml").write_text(yaml.dump(automations))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        # Special chars removed, spaces/dashes become underscores
        assert "automation.my_complex_automation_name" in entities


class TestConfigEntityObjectIdValidation:
    """Tests that config-defined entities only accept valid object IDs."""

    def test_groups_yaml_ignores_invalid_object_ids(self, temp_config_dir):
        """Only valid group object IDs from groups.yaml should be tracked."""
        groups = {
            "valid_group": {"name": "Valid Group"},
            "Invalid Group": {"name": "Invalid Group"},
            "UPPERCASE_GROUP": {"name": "Uppercase Group"},
        }
        (temp_config_dir / "groups.yaml").write_text(yaml.dump(groups))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "group.valid_group" in entities
        assert "group.Invalid Group" not in entities
        assert "group.UPPERCASE_GROUP" not in entities

    def test_configuration_helpers_ignore_invalid_object_ids(self, temp_config_dir):
        """Only valid group/input helper keys from configuration.yaml are tracked."""
        config = {
            "group": {
                "kitchen_lights": {"name": "Kitchen Lights"},
                "Kitchen Lights": {"name": "Invalid Group Key"},
            },
            "input_boolean": {
                "vacation_mode": {"name": "Vacation Mode"},
                "Vacation Mode": {"name": "Invalid Helper Key"},
            },
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "group.kitchen_lights" in entities
        assert "group.Kitchen Lights" not in entities
        assert "input_boolean.vacation_mode" in entities
        assert "input_boolean.Vacation Mode" not in entities

        bad_reference = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "input_boolean.Vacation Mode",
                    },
                    "action": [],
                }
            ]
        }
        bad_file = temp_config_dir / "bad_reference.yaml"
        bad_file.write_text(yaml.dump(bad_reference))

        bad_validator = ReferenceValidator(str(temp_config_dir))
        assert not bad_validator.validate_file_references(bad_file)
        assert "input_boolean.Vacation Mode" in " ".join(bad_validator.errors)

        good_reference = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "input_boolean.vacation_mode",
                    },
                    "action": [],
                }
            ]
        }
        good_file = temp_config_dir / "good_reference.yaml"
        good_file.write_text(yaml.dump(good_reference))

        good_validator = ReferenceValidator(str(temp_config_dir))
        assert good_validator.validate_file_references(good_file)
        assert not good_validator.errors

    def test_legacy_template_sensors_ignore_invalid_object_ids(self, temp_config_dir):
        """Legacy template sensor keys must be valid object IDs."""
        config = {
            "sensor": [
                {
                    "platform": "template",
                    "sensors": {
                        "valid_sensor_name": {
                            "friendly_name": "Valid Sensor",
                            "value_template": "{{ 1 }}",
                        },
                        "Bad Name": {
                            "friendly_name": "Invalid Sensor",
                            "value_template": "{{ 2 }}",
                        },
                    },
                }
            ]
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "sensor.valid_sensor_name" in entities
        assert "sensor.Bad Name" not in entities

        bad_reference = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "sensor.Bad Name",
                    },
                    "action": [],
                }
            ]
        }
        bad_file = temp_config_dir / "bad_legacy_template_reference.yaml"
        bad_file.write_text(yaml.dump(bad_reference))

        bad_validator = ReferenceValidator(str(temp_config_dir))
        assert not bad_validator.validate_file_references(bad_file)
        assert "sensor.Bad Name" in " ".join(bad_validator.errors)

    def test_scripts_yaml_ignores_invalid_object_ids(self, temp_config_dir):
        """Script entities derived from scripts.yaml must use valid object IDs."""
        scripts = {
            "good_script": {"sequence": []},
            "Bad Script": {"sequence": []},
        }
        (temp_config_dir / "scripts.yaml").write_text(yaml.dump(scripts))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "script.good_script" in entities
        assert "script.Bad Script" not in entities

        bad_reference = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "script.Bad Script",
                    },
                    "action": [],
                }
            ]
        }
        bad_file = temp_config_dir / "bad_script_reference.yaml"
        bad_file.write_text(yaml.dump(bad_reference))

        bad_validator = ReferenceValidator(str(temp_config_dir))
        assert not bad_validator.validate_file_references(bad_file)
        assert "script.Bad Script" in " ".join(bad_validator.errors)


class TestSceneEntityDerivation:
    """Tests for scene entity ID derivation."""

    def test_scene_id_not_used_as_entity_id(self, temp_config_dir):
        """Scene 'id' field should NOT be used as entity_id."""
        scenes = [
            {
                "id": "1234567890",
                "name": "Movie Time!",
                "entities": {},
            }
        ]
        (temp_config_dir / "scenes.yaml").write_text(yaml.dump(scenes))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "scene.1234567890" not in entities
        assert "scene.movie_time" in entities


class TestNoIntegrationDomainSkip:
    """Tests that integration domains are not blindly accepted."""

    def test_unknown_weather_entity_produces_error(self, temp_config_dir):
        """Unknown weather.* should produce validation errors."""
        config = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "weather.fake_weather",
                    },
                    "action": [],
                }
            ]
        }
        (temp_config_dir / "test_config.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        validator.validate_file_references(temp_config_dir / "test_config.yaml")

        error_messages = " ".join(validator.errors)
        assert "weather.fake_weather" in error_messages


class TestRestoreStateFallback:
    """Tests for restore state diagnostics behavior."""

    def test_entity_in_restore_state_still_fails_validation(self, temp_config_dir):
        """Unknown entities in restore state should still fail validation."""
        restore_payload = {"data": [{"state": {"entity_id": "sensor.restored_entity"}}]}
        (temp_config_dir / ".storage" / "core.restore_state").write_text(
            json.dumps(restore_payload)
        )

        config = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "sensor.restored_entity",
                    },
                    "action": [],
                }
            ]
        }
        (temp_config_dir / "test_config.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        assert not validator.validate_file_references(
            temp_config_dir / "test_config.yaml"
        )

        error_messages = " ".join(validator.errors)
        assert "sensor.restored_entity" in error_messages

        warning_messages = " ".join(validator.warnings)
        assert "sensor.restored_entity" in warning_messages


class TestZoneValidation:
    """Tests for zone entity validation."""

    def test_zone_home_is_builtin(self, temp_config_dir):
        """Recognizes zone.home as a built-in."""
        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "zone.home" in entities

    def test_unknown_zone_produces_error(self, temp_config_dir):
        """Unknown zone.* references should produce validation errors."""
        # Use entity_id field to reference a zone - this is how zones
        # are referenced in conditions and other places
        config = {
            "automation": [
                {
                    "condition": {
                        "condition": "zone",
                        "entity_id": "zone.nonexistent_zone",
                    },
                    "action": [],
                }
            ]
        }
        (temp_config_dir / "test_config.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        validator.validate_file_references(temp_config_dir / "test_config.yaml")

        # Should have an error for the unknown zone
        error_messages = " ".join(validator.errors)
        assert "zone.nonexistent_zone" in error_messages

    def test_zone_not_in_builtin_domains(self, temp_config_dir):
        """Does not treat zone as a built-in domain."""
        validator = ReferenceValidator(str(temp_config_dir))

        assert "zone" not in validator.BUILTIN_DOMAINS
        assert not validator.is_builtin_domain("zone.some_zone")

    def test_configured_zone_is_valid(self, temp_config_dir):
        """Zones defined in configuration should be recognized."""
        config = {
            "zone": [
                {"name": "Work", "latitude": 40.0, "longitude": -74.0, "radius": 100}
            ]
        }
        (temp_config_dir / "configuration.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "zone.work" in entities

    def test_storage_zone_is_valid(self, temp_config_dir):
        """Zones defined in storage (UI) should be recognized."""
        zone_storage = {
            "data": {
                "items": [{"name": "Office", "latitude": 40.0, "longitude": -74.0}]
            }
        }
        (temp_config_dir / ".storage" / "core.zone").write_text(
            json.dumps(zone_storage)
        )

        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "zone.office" in entities


class TestPersistentNotificationValidation:
    """Tests for persistent_notification entity validation."""

    def test_persistent_notification_not_in_builtin_domains(self, temp_config_dir):
        """Does not treat persistent_notification as a built-in domain."""
        validator = ReferenceValidator(str(temp_config_dir))

        assert "persistent_notification" not in validator.BUILTIN_DOMAINS
        assert not validator.is_builtin_domain("persistent_notification.test")

    def test_unknown_persistent_notification_produces_error(self, temp_config_dir):
        """Unknown persistent_notification.* should produce validation errors."""
        config = {
            "automation": [
                {
                    "trigger": {
                        "platform": "state",
                        "entity_id": "persistent_notification.fake_notification",
                    },
                    "action": [],
                }
            ]
        }
        (temp_config_dir / "test_config.yaml").write_text(yaml.dump(config))

        validator = ReferenceValidator(str(temp_config_dir))
        validator.validate_file_references(temp_config_dir / "test_config.yaml")

        # Should have an error for the unknown persistent_notification
        error_messages = " ".join(validator.errors)
        assert "persistent_notification.fake_notification" in error_messages


class TestBuiltinEntities:
    """Tests for built-in entity handling."""

    def test_sun_sun_is_builtin(self, temp_config_dir):
        """Recognizes sun.sun as built-in."""
        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "sun.sun" in entities

    def test_zone_home_is_builtin(self, temp_config_dir):
        """Recognizes zone.home as built-in."""
        validator = ReferenceValidator(str(temp_config_dir))
        entities = validator.get_config_defined_entities()

        assert "zone.home" in entities

    def test_builtin_domains_is_empty(self, temp_config_dir):
        """BUILTIN_DOMAINS should be empty (no domain-wide skips)."""
        validator = ReferenceValidator(str(temp_config_dir))

        assert len(validator.BUILTIN_DOMAINS) == 0
