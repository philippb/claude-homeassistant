#!/usr/bin/env python3
"""Entity and device reference validator for Home Assistant configuration files.

Validates that all entity references in configuration files actually exist.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypedDict

import yaml


class DomainSummary(TypedDict):
    """Type definition for domain summary dictionary."""

    count: int
    enabled: int
    disabled: int
    examples: List[str]


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
HAYamlLoader.add_constructor("!include_dir_named", include_dir_named_constructor)
HAYamlLoader.add_constructor(
    "!include_dir_merge_named", include_dir_merge_named_constructor
)
HAYamlLoader.add_constructor(
    "!include_dir_merge_list", include_dir_merge_list_constructor
)
HAYamlLoader.add_constructor("!include_dir_list", include_dir_list_constructor)
HAYamlLoader.add_constructor("!input", input_constructor)
HAYamlLoader.add_constructor("!secret", secret_constructor)


# pylint: disable=too-many-instance-attributes
class ReferenceValidator:
    """Validates entity and device references in Home Assistant config."""

    # Special keywords that are not entity IDs
    SPECIAL_KEYWORDS = {"all", "none"}

    _OBJECT_ID_RE = re.compile(r"^[a-z0-9_]+$")

    # Built-in entities that always exist but aren't in the entity registry
    # zone.home is a special, pre-defined, non-deletable zone
    # See: https://www.home-assistant.io/integrations/zone/
    BUILTIN_ENTITIES = {
        "sun.sun",
        "zone.home",
    }

    # No domain-wide skips - we validate all entity references
    # persistent_notification uses notification_id with services/triggers,
    # not entity IDs. See: home-assistant.io/integrations/persistent_notification/
    BUILTIN_DOMAINS: set = set()

    def __init__(self, config_dir: str = "config"):
        """Initialize the ReferenceValidator."""
        self.config_dir = Path(config_dir)
        self.storage_dir = self.config_dir / ".storage"
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # Cache for loaded registries
        self._entities: Optional[Dict[str, Any]] = None
        self._devices: Optional[Dict[str, Any]] = None
        self._areas: Optional[Dict[str, Any]] = None
        self._restore_entities: Optional[Set[str]] = None

    def load_entity_registry(self) -> Dict[str, Any]:
        """Load and cache entity registry."""
        if self._entities is None:
            registry_file = self.storage_dir / "core.entity_registry"
            if not registry_file.exists():
                self.errors.append(f"Entity registry not found: {registry_file}")
                return {}

            try:
                with open(registry_file, "r") as f:
                    data = json.load(f)
                    self._entities = {
                        entity["entity_id"]: entity
                        for entity in data.get("data", {}).get("entities", [])
                    }
            except Exception as e:
                self.errors.append(f"Failed to load entity registry: {e}")
                return {}

        return self._entities

    def load_device_registry(self) -> Dict[str, Any]:
        """Load and cache device registry."""
        if self._devices is None:
            registry_file = self.storage_dir / "core.device_registry"
            if not registry_file.exists():
                self.errors.append(f"Device registry not found: {registry_file}")
                return {}

            try:
                with open(registry_file, "r") as f:
                    data = json.load(f)
                    self._devices = {
                        device["id"]: device
                        for device in data.get("data", {}).get("devices", [])
                    }
            except Exception as e:
                self.errors.append(f"Failed to load device registry: {e}")
                return {}

        return self._devices

    def load_area_registry(self) -> Dict[str, Any]:
        """Load and cache area registry."""
        if self._areas is None:
            registry_file = self.storage_dir / "core.area_registry"
            if not registry_file.exists():
                self.warnings.append(f"Area registry not found: {registry_file}")
                return {}

            try:
                with open(registry_file, "r") as f:
                    data = json.load(f)
                    self._areas = {
                        area["id"]: area
                        for area in data.get("data", {}).get("areas", [])
                    }
            except Exception as e:
                self.warnings.append(f"Failed to load area registry: {e}")
                return {}

        return self._areas

    def load_restore_state_entities(self) -> Set[str]:
        """Load and cache entity_ids found in restore state storage.

        Restore state can contain stale entries and is not authoritative for
        reference validation. We use it only for diagnostics.
        """
        if self._restore_entities is None:
            restore_file = self.storage_dir / "core.restore_state"
            if not restore_file.exists():
                self._restore_entities = set()
                return self._restore_entities

            try:
                with open(restore_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                self.warnings.append(f"Failed to load restore state: {e}")
                self._restore_entities = set()
                return self._restore_entities

            items = payload.get("data", [])
            entities: Set[str] = set()
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    state = item.get("state")
                    if not isinstance(state, dict):
                        continue
                    entity_id = state.get("entity_id")
                    if isinstance(entity_id, str) and self._is_valid_entity_id(
                        entity_id
                    ):
                        entities.add(entity_id)

            self._restore_entities = entities

        return self._restore_entities

    @classmethod
    def _slugify_object_id(cls, value: str) -> str:
        """Best-effort HA-like slugify for deriving object_ids from names.

        Note: we intentionally do not "fix" user-provided object_ids (keys like
        input_boolean.foo). This helper is only used for name/alias-derived IDs.
        """
        slug = value.strip().lower()
        slug = re.sub(r"[^a-z0-9_]+", "_", slug)
        slug = re.sub(r"_+", "_", slug)
        return slug.strip("_")

    @classmethod
    def _is_valid_object_id(cls, value: str) -> bool:
        return bool(cls._OBJECT_ID_RE.fullmatch(value))

    @classmethod
    def _is_valid_entity_id(cls, value: str) -> bool:
        if "." not in value:
            return False
        domain, object_id = value.split(".", 1)
        return (
            bool(domain)
            and cls._is_valid_object_id(domain)
            and cls._is_valid_object_id(object_id)
        )

    def get_config_defined_entities(self) -> Set[str]:
        """Extract entities defined in config files (not in entity registry)."""
        entities: Set[str] = set()

        # Add built-in entities
        entities.update(self.BUILTIN_ENTITIES)

        # Extract from groups.yaml
        entities.update(self._extract_groups())

        # Extract from configuration.yaml (templates, input helpers, etc.)
        entities.update(self._extract_from_configuration())

        # Extract automation/script/scene entities from their config files
        entities.update(self._extract_automation_entities())
        entities.update(self._extract_script_entities())
        entities.update(self._extract_scene_entities())

        # Extract zone entities from configuration and storage
        entities.update(self._extract_zone_entities())

        # Extract platform-based entities (calendar, etc.) from configuration.yaml
        entities.update(self._extract_platform_entities())

        return entities

    def _extract_groups(self) -> Set[str]:
        """Extract group entities from groups.yaml."""
        entities: Set[str] = set()
        groups_file = self.config_dir / "groups.yaml"

        if groups_file.exists():
            try:
                with open(groups_file, "r", encoding="utf-8") as f:
                    data = yaml.load(f, Loader=HAYamlLoader)
                    if isinstance(data, dict):
                        for group_name in data.keys():
                            if isinstance(group_name, str) and self._is_valid_object_id(
                                group_name
                            ):
                                entities.add(f"group.{group_name}")
            except Exception:
                pass  # Ignore errors, will be caught by YAML validator

        return entities

    def _extract_from_configuration(self) -> Set[str]:
        """Extract entities defined in configuration.yaml."""
        entities: Set[str] = set()
        config_file = self.config_dir / "configuration.yaml"

        if not config_file.exists():
            return entities

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=HAYamlLoader)

            if not isinstance(data, dict):
                return entities

            # Extract groups
            if "group" in data and isinstance(data["group"], dict):
                for group_name in data["group"].keys():
                    if isinstance(group_name, str) and self._is_valid_object_id(
                        group_name
                    ):
                        entities.add(f"group.{group_name}")

            # Extract input helpers
            for input_type in [
                "input_boolean",
                "input_number",
                "input_text",
                "input_select",
                "input_datetime",
                "input_button",
            ]:
                if input_type in data and isinstance(data[input_type], dict):
                    for name in data[input_type].keys():
                        if isinstance(name, str) and self._is_valid_object_id(name):
                            entities.add(f"{input_type}.{name}")

            # Extract template entities
            if "template" in data:
                template_data = data["template"]
                if isinstance(template_data, list):
                    for item in template_data:
                        entities.update(self._extract_template_entities(item))
                elif isinstance(template_data, dict):
                    entities.update(self._extract_template_entities(template_data))

            # Extract sensors/binary_sensors defined directly
            for sensor_type in ["sensor", "binary_sensor"]:
                if sensor_type in data:
                    sensor_data = data[sensor_type]
                    if isinstance(sensor_data, list):
                        for item in sensor_data:
                            if isinstance(item, dict) and "platform" in item:
                                # Legacy template platform uses named keys
                                if item["platform"] == "template":
                                    sensors = item.get("sensors", {})
                                    for name in sensors.keys():
                                        if isinstance(
                                            name, str
                                        ) and self._is_valid_object_id(name):
                                            entities.add(f"{sensor_type}.{name}")
                                # Other platforms derive entity_id from name
                                name = item.get("name")
                                if isinstance(name, str):
                                    object_id = self._slugify_object_id(name)
                                    if object_id:
                                        entities.add(f"{sensor_type}.{object_id}")

        except Exception:
            pass  # Ignore errors

        return entities

    def _extract_template_entities(self, template_config: Any) -> Set[str]:
        """Extract entity names from template configuration.

        Per HA docs: default_entity_id controls automatic entity_id generation.
        unique_id exists to allow changing entity_id in the UI - it's NOT the entity_id.
        See: https://www.home-assistant.io/integrations/template/
        """
        entities: Set[str] = set()

        if not isinstance(template_config, dict):
            return entities

        # Template sensors, binary_sensors, etc.
        for entity_type in ["sensor", "binary_sensor", "number", "select", "button"]:
            if entity_type in template_config:
                type_data = template_config[entity_type]
                if isinstance(type_data, list):
                    for item in type_data:
                        if isinstance(item, dict):
                            # Use default_entity_id if present, else derive from name
                            # Do NOT use unique_id - it's for UI customization only
                            default_entity_id = item.get("default_entity_id")
                            name = item.get("name", "")
                            if default_entity_id:
                                default_entity_id = str(default_entity_id)
                                if "." in default_entity_id:
                                    # Some configs may provide full entity_id.
                                    # Only accept if well-formed.
                                    if self._is_valid_entity_id(default_entity_id):
                                        entities.add(default_entity_id)
                                else:
                                    # Only accept valid user-provided object_ids.
                                    if self._is_valid_object_id(default_entity_id):
                                        entities.add(
                                            f"{entity_type}.{default_entity_id}"
                                        )
                            elif name:
                                object_id = self._slugify_object_id(str(name))
                                if object_id:
                                    entities.add(f"{entity_type}.{object_id}")

        return entities

    def _extract_automation_entities(self) -> Set[str]:
        """Extract automation entities from automations.yaml.

        Per HA docs: The 'id' field is a unique identifier that allows changing
        the name and entity_id in the UI - it is NOT the entity_id itself.
        Entity_id is generated from the entity name (alias).
        Registry should be source of truth; alias-slug is a fallback heuristic.
        See: https://www.home-assistant.io/docs/automation/yaml/
        """
        entities: Set[str] = set()
        automations_file = self.config_dir / "automations.yaml"

        if automations_file.exists():
            try:
                with open(automations_file, "r", encoding="utf-8") as f:
                    data = yaml.load(f, Loader=HAYamlLoader)
                    if isinstance(data, list):
                        for automation in data:
                            if isinstance(automation, dict):
                                # Derive entity_id from alias (friendly name)
                                # Do NOT use 'id' field - it's for UI customization only
                                alias = automation.get("alias", "")
                                if alias:
                                    object_id = self._slugify_object_id(str(alias))
                                    if object_id:
                                        entities.add(f"automation.{object_id}")
            except Exception:
                pass

        return entities

    def _extract_script_entities(self) -> Set[str]:
        """Extract script entities from scripts.yaml."""
        entities: Set[str] = set()
        scripts_file = self.config_dir / "scripts.yaml"

        if scripts_file.exists():
            try:
                with open(scripts_file, "r", encoding="utf-8") as f:
                    data = yaml.load(f, Loader=HAYamlLoader)
                    if isinstance(data, dict):
                        for script_name in data.keys():
                            if isinstance(
                                script_name, str
                            ) and self._is_valid_object_id(script_name):
                                entities.add(f"script.{script_name}")
            except Exception:
                pass

        return entities

    def _extract_scene_entities(self) -> Set[str]:
        """Extract scene entities from scenes.yaml.

        Similar to automations, the `id` field in UI-managed scenes is a unique
        identifier and not the entity_id. We derive the entity_id from the
        friendly name as a fallback heuristic.
        """
        entities: Set[str] = set()
        scenes_file = self.config_dir / "scenes.yaml"

        if scenes_file.exists():
            try:
                with open(scenes_file, "r", encoding="utf-8") as f:
                    data = yaml.load(f, Loader=HAYamlLoader)
                    if isinstance(data, list):
                        for scene in data:
                            if isinstance(scene, dict):
                                name = scene.get("name", "")
                                if name:
                                    object_id = self._slugify_object_id(str(name))
                                    if object_id:
                                        entities.add(f"scene.{object_id}")
            except Exception:
                pass

        return entities

    def _extract_zone_entities(self) -> Set[str]:
        """Extract zone entities from configuration and storage.

        Zones can be defined in:
        1. configuration.yaml under 'zone:' key
        2. .storage/core.zone file (UI-configured zones)

        zone.home is a built-in that's always present and handled separately.
        See: https://www.home-assistant.io/integrations/zone/
        """
        entities: Set[str] = set()

        # Extract from configuration.yaml
        config_file = self.config_dir / "configuration.yaml"
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = yaml.load(f, Loader=HAYamlLoader)
                    if isinstance(data, dict) and "zone" in data:
                        zone_data = data["zone"]
                        if isinstance(zone_data, list):
                            for zone in zone_data:
                                if isinstance(zone, dict):
                                    name = zone.get("name", "")
                                    if name:
                                        object_id = self._slugify_object_id(str(name))
                                        if object_id:
                                            entities.add(f"zone.{object_id}")
            except Exception:
                pass

        # Extract from storage (UI-configured zones)
        zone_storage = self.storage_dir / "core.zone"
        if zone_storage.exists():
            try:
                with open(zone_storage, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("data", {}).get("items", [])
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get("name", "")
                            if name:
                                object_id = self._slugify_object_id(str(name))
                                if object_id:
                                    entities.add(f"zone.{object_id}")
            except Exception:
                pass

        return entities

    def _extract_platform_entities(self) -> Set[str]:
        """Extract entities from YAML platform configurations (e.g., calendar).

        Platform-based entities defined in YAML don't have unique IDs and
        won't appear in the entity registry. Entity IDs are derived from
        the platform's name fields (e.g., calendars list for CalDAV).
        """
        entities: Set[str] = set()
        config_file = self.config_dir / "configuration.yaml"

        if not config_file.exists():
            return entities

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=HAYamlLoader)

            if not isinstance(data, dict):
                return entities

            # Calendar platforms (CalDAV, etc.)
            if "calendar" in data:
                calendar_data = data["calendar"]
                if isinstance(calendar_data, list):
                    for item in calendar_data:
                        if isinstance(item, dict):
                            # CalDAV uses 'calendars' list of names
                            calendars = item.get("calendars", [])
                            if isinstance(calendars, list):
                                for name in calendars:
                                    if isinstance(name, str):
                                        object_id = self._slugify_object_id(name)
                                        if object_id:
                                            entities.add(f"calendar.{object_id}")
                            # Generic: platform with 'name' field
                            name = item.get("name")
                            if isinstance(name, str):
                                object_id = self._slugify_object_id(name)
                                if object_id:
                                    entities.add(f"calendar.{object_id}")

        except Exception:
            pass

        return entities

    def is_builtin_domain(self, entity_id: str) -> bool:
        """Check if entity belongs to a built-in domain."""
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        return domain in self.BUILTIN_DOMAINS

    def is_uuid_format(self, value: str) -> bool:
        """Check if a string matches UUID format (32 hex characters)."""
        # UUID format: 8-4-4-4-12 hex digits, but HA often stores without hyphens
        uuid_pattern = r"^[a-f0-9]{32}$"
        return bool(re.match(uuid_pattern, value))

    def is_template(self, value: str) -> bool:
        """Check if value is a Jinja2 template expression."""
        # Match template expressions like {{ ... }}
        return bool(re.search(r"\{\{.*?\}\}", value))

    def should_skip_entity_validation(self, value: str) -> bool:
        """Check if entity reference should be skipped during validation."""
        return (
            value.startswith("!")  # HA tags like !input, !secret
            or self.is_uuid_format(value)  # UUID format (device-based)
            or self.is_template(value)  # Template expressions
            or value in self.SPECIAL_KEYWORDS  # Special keywords like "all", "none"
        )

    def extract_entity_references(self, data: Any, path: str = "") -> Set[str]:
        """Extract entity references from configuration data."""
        entities = set()

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                # Common entity reference keys
                if key in ["entity_id", "entity_ids", "entities"]:
                    if isinstance(value, str):
                        if not self.should_skip_entity_validation(value):
                            entities.add(value)
                    elif isinstance(value, list):
                        for entity in value:
                            if isinstance(
                                entity, str
                            ) and not self.should_skip_entity_validation(entity):
                                entities.add(entity)

                # Device-related keys
                elif key in ["device_id", "device_ids"]:
                    # Device IDs are handled separately
                    pass

                # Area-related keys
                elif key in ["area_id", "area_ids"]:
                    # Area IDs are handled separately
                    pass

                # Service data might contain entity references
                elif key == "data" and isinstance(value, dict):
                    entities.update(self.extract_entity_references(value, current_path))

                # Templates might contain entity references
                elif isinstance(value, str) and any(
                    x in value for x in ["state_attr(", "states(", "is_state("]
                ):
                    entities.update(self.extract_entities_from_template(value))

                # Recursive search
                else:
                    entities.update(self.extract_entity_references(value, current_path))

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]" if path else f"[{i}]"
                entities.update(self.extract_entity_references(item, current_path))

        return entities

    def extract_entities_from_template(self, template: str) -> Set[str]:
        """Extract entity references from Jinja2 templates."""
        entities = set()

        # Common patterns for entity references in templates
        patterns = [
            r"states\('([^']+)'\)",  # states('entity.id')
            r'states\("([^"]+)"\)',  # states("entity.id")
            # states.domain.entity
            r"states\.([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)",
            r"is_state\('([^']+)'",  # is_state('entity.id', ...)
            r'is_state\("([^"]+)"',  # is_state("entity.id", ...)
            r"state_attr\('([^']+)'",  # state_attr('entity.id', ...)
            r'state_attr\("([^"]+)"',  # state_attr("entity.id", ...)
        ]

        for pattern in patterns:
            matches = re.findall(pattern, template)
            for match in matches:
                # Validate entity ID format
                if "." in match and len(match.split(".")) == 2:
                    entities.add(match)

        return entities

    def extract_device_references(self, data: Any) -> Set[str]:
        """Extract device references from configuration data."""
        devices = set()

        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["device_id", "device_ids"]:
                    if isinstance(value, str):
                        # Skip blueprint inputs and other HA tags
                        if not value.startswith("!") and not self.is_template(value):
                            devices.add(value)
                    elif isinstance(value, list):
                        for device in value:
                            if (
                                isinstance(device, str)
                                and not device.startswith("!")
                                and not self.is_template(device)
                            ):
                                devices.add(device)
                else:
                    devices.update(self.extract_device_references(value))

        elif isinstance(data, list):
            for item in data:
                devices.update(self.extract_device_references(item))

        return devices

    def extract_area_references(self, data: Any) -> Set[str]:
        """Extract area references from configuration data."""
        areas = set()

        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["area_id", "area_ids"]:
                    if isinstance(value, str):
                        # Skip blueprint inputs and other HA tags
                        if not value.startswith("!") and not self.is_template(value):
                            areas.add(value)
                    elif isinstance(value, list):
                        for area in value:
                            if isinstance(area, str) and not area.startswith("!"):
                                areas.add(area)
                else:
                    areas.update(self.extract_area_references(value))

        elif isinstance(data, list):
            for item in data:
                areas.update(self.extract_area_references(item))

        return areas

    def extract_entity_registry_ids(self, data: Any) -> Set[str]:
        """Extract entity registry UUID references from configuration data."""
        entity_registry_ids = set()

        if isinstance(data, dict):
            for key, value in data.items():
                # Look for entity_id fields containing UUIDs (device-based automations)
                if key == "entity_id" and isinstance(value, str):
                    if self.is_uuid_format(value):
                        entity_registry_ids.add(value)
                else:
                    entity_registry_ids.update(self.extract_entity_registry_ids(value))
        elif isinstance(data, list):
            for item in data:
                entity_registry_ids.update(self.extract_entity_registry_ids(item))

        return entity_registry_ids

    def get_entity_registry_id_mapping(self) -> Dict[str, str]:
        """Get mapping from entity registry ID to entity_id."""
        entities = self.load_entity_registry()
        return {
            entity_data["id"]: entity_data["entity_id"]
            for entity_data in entities.values()
            if "id" in entity_data
        }

    def validate_file_references(self, file_path: Path) -> bool:
        """Validate all references in a single file."""
        if file_path.name == "secrets.yaml":
            return True  # Skip secrets file

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=HAYamlLoader)
        except Exception as e:
            self.errors.append(f"{file_path}: Failed to load YAML - {e}")
            return False

        if data is None:
            return True  # Empty file is valid

        # Extract references
        entity_refs = self.extract_entity_references(data)
        device_refs = self.extract_device_references(data)
        area_refs = self.extract_area_references(data)
        entity_registry_ids = self.extract_entity_registry_ids(data)

        # Load registries
        entities = self.load_entity_registry()
        devices = self.load_device_registry()
        areas = self.load_area_registry()
        entity_id_mapping = self.get_entity_registry_id_mapping()

        # Get config-defined entities (groups, templates, input helpers, etc.)
        config_entities = self.get_config_defined_entities()
        restore_entities = self.load_restore_state_entities()

        all_valid = True

        # Validate entity references (normal entity_id format)
        for entity_id in entity_refs:
            # Skip UUID-format entity IDs, they're handled separately
            if self.is_uuid_format(entity_id):
                continue

            # Check if entity exists in registry, config, or is a built-in
            if entity_id in entities:
                # Surface disabled entities without failing validation.
                if entities[entity_id].get("disabled_by") is not None:
                    self.warnings.append(
                        f"{file_path}: References disabled entity '{entity_id}'"
                    )
                continue  # Found in entity registry

            if entity_id in config_entities:
                continue  # Found in config-defined entities

            if self.is_builtin_domain(entity_id):
                continue  # Built-in domain (zone.*, persistent_notification.*)

            if entity_id in restore_entities:
                # Restore state is diagnostic only. Unknown entities must still fail
                # validation because restore data can be stale after renames/removal.
                self.warnings.append(
                    f"{file_path}: Entity '{entity_id}' not in registry "
                    "but found in restore state"
                )

            self.errors.append(f"{file_path}: Unknown entity '{entity_id}'")
            all_valid = False

        # Validate entity registry ID references (UUID format)
        for registry_id in entity_registry_ids:
            if registry_id not in entity_id_mapping:
                self.errors.append(
                    f"{file_path}: Unknown entity registry ID '{registry_id}'"
                )
                all_valid = False
            else:
                # Check if the mapped entity is disabled
                actual_entity_id = entity_id_mapping[registry_id]
                if actual_entity_id in entities:
                    entity_data = entities[actual_entity_id]
                    if entity_data.get("disabled_by") is not None:
                        self.warnings.append(
                            f"{file_path}: Entity registry ID '{registry_id}' "
                            f"references disabled entity '{actual_entity_id}'"
                        )

        # Validate device references
        for device_id in device_refs:
            if device_id not in devices:
                self.errors.append(f"{file_path}: Unknown device '{device_id}'")
                all_valid = False

        # Validate area references
        for area_id in area_refs:
            if area_id not in areas:
                self.warnings.append(f"{file_path}: Unknown area '{area_id}'")

        return all_valid

    def get_yaml_files(self) -> List[Path]:
        """Get all YAML files to validate."""
        yaml_files: List[Path] = []
        for pattern in ["*.yaml", "*.yml"]:
            yaml_files.extend(self.config_dir.glob(pattern))

        # Skip blueprints directory - these are templates with !input tags
        return yaml_files

    def validate_all(self) -> bool:
        """Validate all references in the config directory."""
        if not self.config_dir.exists():
            self.errors.append(f"Config directory {self.config_dir} does not exist")
            return False

        yaml_files = self.get_yaml_files()
        if not yaml_files:
            self.warnings.append("No YAML files found in config directory")
            return True

        all_valid = True

        for file_path in yaml_files:
            if not self.validate_file_references(file_path):
                all_valid = False

        return all_valid

    def get_entity_summary(self) -> Dict[str, DomainSummary]:
        """Get summary of available entities by domain."""
        entities = self.load_entity_registry()

        summary: Dict[str, DomainSummary] = {}
        for entity_id, entity_data in entities.items():
            domain = entity_id.split(".")[0]
            if domain not in summary:
                summary[domain] = {
                    "count": 0,
                    "enabled": 0,
                    "disabled": 0,
                    "examples": [],
                }

            summary[domain]["count"] += 1
            if entity_data.get("disabled_by") is None:
                summary[domain]["enabled"] += 1
            else:
                summary[domain]["disabled"] += 1

            # Add some examples
            if len(summary[domain]["examples"]) < 3:
                summary[domain]["examples"].append(entity_id)

        return summary

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

        # Print entity summary
        summary = self.get_entity_summary()
        if summary:
            print("AVAILABLE ENTITIES BY DOMAIN:")
            for domain, info in sorted(summary.items()):
                enabled_count = info["enabled"]
                disabled_count = info["disabled"]
                print(
                    f"  {domain}: {enabled_count} enabled, "
                    f"{disabled_count} disabled"
                )
                if info["examples"]:
                    print(f"    Examples: {', '.join(info['examples'])}")
            print()

        if not self.errors and not self.warnings:
            print("✅ All entity/device references are valid!")
        elif not self.errors:
            print("✅ Entity/device references are valid (with warnings)")
        else:
            print("❌ Invalid entity/device references found")


def main():
    """Run entity and device reference validation from command line."""
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"

    validator = ReferenceValidator(config_dir)
    is_valid = validator.validate_all()
    validator.print_results()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
