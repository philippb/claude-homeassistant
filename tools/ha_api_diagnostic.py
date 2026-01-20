#!/usr/bin/env python3
"""Home Assistant API Diagnostic Tool.

Comprehensive testing of various API endpoints and entity operations.
Combines functionality from multiple diagnostic scripts.
"""

import json
import os

import requests

from tools.reload_config import load_env_file

load_env_file()
HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
TOKEN = os.getenv("HA_TOKEN", "")


def test_api_connection():
    """Test basic API connection."""
    print("🔗 Testing API Connection...")
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = requests.get(f"{HA_URL}/api/", headers=headers, timeout=10)

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Message: {data.get('message', 'No message')}")
            return True
        print(f"   Error: {response.text}")
        return False
    except Exception as e:
        print(f"   Exception: {e}")
        return False


def test_api_endpoints():
    """Test various API endpoints to find entity registry access."""
    print("\n🔍 Testing Various API Endpoints...")

    headers = {"Authorization": f"Bearer {TOKEN}"}

    endpoints_to_test = [
        ("/api/config/entity_registry", "Entity Registry"),
        ("/api/config/entity_registry/list", "Entity Registry List"),
        ("/api/states", "Entity States"),
        ("/api/config", "Configuration"),
        ("/api/config/core", "Core Configuration"),
        ("/api/hassio/supervisor/api/config", "Supervisor Config"),
        ("/api/template", "Template API"),
    ]

    successful_endpoints = []

    for endpoint, description in endpoints_to_test:
        try:
            print(f"\n   Testing: {endpoint} ({description})")
            response = requests.get(f"{HA_URL}{endpoint}", headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                successful_endpoints.append(endpoint)
                try:
                    data = response.json()
                    if isinstance(data, list):
                        print(f"   ✅ List with {len(data)} items")
                        if len(data) > 0:
                            print(f"      Sample type: {type(data[0])}")
                    elif isinstance(data, dict):
                        keys = list(data.keys())[:5]
                        print(f"   ✅ Dict with keys: {keys}")
                    else:
                        print(f"   ✅ {type(data)}")
                except Exception:
                    print(f"   ✅ Non-JSON response ({len(response.text)} chars)")
            else:
                print(f"   ❌ {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ Exception: {e}")

    return successful_endpoints


def test_entity_registry_read():
    """Test reading entity registry."""
    print("\n📋 Testing Entity Registry Read Access...")
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = requests.get(
            f"{HA_URL}/api/config/entity_registry", headers=headers, timeout=10
        )

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Found {len(data)} entities")

            # Look for target entities
            target_entities = [
                "binary_sensor.basement",
                "media_player.kitchen",
                "camera.driveway_live_view",
            ]
            found_entities = []

            for entity in data:
                entity_id = entity.get("entity_id")
                if entity_id in target_entities:
                    found_entities.append(entity)
                    print(f"   ✅ Found: {entity_id}")
                    print(f"      Platform: {entity.get('platform')}")
                    print(f"      Device ID: {entity.get('device_id')}")
                    print(f"      Unique ID: {entity.get('unique_id')}")

            return found_entities
        print(f"   ❌ Error: {response.text}")
        return []
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return []


def test_states_endpoint():
    """Test the /api/states endpoint to see entity data."""
    print("\n📊 Testing States Endpoint for Entity Info...")
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        response = requests.get(f"{HA_URL}/api/states", headers=headers, timeout=10)

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            states = response.json()
            print(f"   ✅ Found {len(states)} states")

            # Look for our target entities
            target_entities = [
                "binary_sensor.basement",
                "media_player.kitchen",
                "camera.driveway_live_view",
            ]
            found_entities = []

            for state in states:
                entity_id = state.get("entity_id")
                if entity_id in target_entities:
                    found_entities.append(entity_id)
                    print(f"   ✅ Found: {entity_id}")
                    attrs = list(state.get("attributes", {}).keys())[:5]
                    print(f"      Attributes: {attrs}")

            return len(found_entities) == len(target_entities)
        print(f"   ❌ Error: {response.text}")
        return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def test_entity_rename(entity_data_list):
    """Test renaming a single entity using multiple methods."""
    print("\n🔄 Testing Entity Rename Methods...")

    if not entity_data_list:
        print("   ❌ No entity data to test with")
        return False

    entity_data = entity_data_list[0]  # Use first found entity
    old_id = entity_data.get("entity_id", "binary_sensor.basement")
    new_id = "binary_sensor.sf_basement_motion_test"

    print(f"   Testing rename: {old_id} → {new_id}")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    # Method 1: Direct entity registry update
    try:
        print("\n   Method 1: Direct registry update...")
        data = {"new_entity_id": new_id}
        response = requests.post(
            f"{HA_URL}/api/config/entity_registry/{old_id}",
            headers=headers,
            json=data,
            timeout=10,
        )

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Method 1 successful!")
            return True
        print(f"   ❌ Method 1 failed: {response.text}")

    except Exception as e:
        print(f"   ❌ Method 1 exception: {e}")

    # Method 2: Update endpoint
    try:
        print("\n   Method 2: Update endpoint...")
        response = requests.post(
            f"{HA_URL}/api/config/entity_registry/update",
            headers=headers,
            json={"entity_id": old_id, "new_entity_id": new_id},
            timeout=10,
        )

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Method 2 successful!")
            return True
        print(f"   ❌ Method 2 failed: {response.text}")

    except Exception as e:
        print(f"   ❌ Method 2 exception: {e}")

    return False


def test_service_call_method():
    """Test if we can rename via service calls."""
    print("\n🔧 Testing Service Call Method...")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    # Test calling homeassistant.update_entity service
    try:
        service_data = {
            "entity_id": "binary_sensor.basement",
            # This changes friendly name, not entity_id
            "name": "SF Basement Motion Test",
        }

        response = requests.post(
            f"{HA_URL}/api/services/homeassistant/update_entity",
            headers=headers,
            json=service_data,
            timeout=10,
        )

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Service call successful (friendly name only)")
            print("   Note: This only changes display name, not entity_id")
        else:
            print(f"   ❌ Service call failed: {response.text}")

    except Exception as e:
        print(f"   ❌ Exception: {e}")


def show_websocket_info():
    """Show information about WebSocket method."""
    print("\n🌐 WebSocket API Information...")
    print("   Entity registry operations likely require WebSocket API:")
    print("   • WebSocket URL: ws://homeassistant.local:8123/api/websocket")
    print("   • Auth: Send auth message with Bearer token")
    print("   • List entities: {'type': 'config/entity_registry/list'}")
    print(
        "   • Update entity: {'type': 'config/entity_registry/update', "
        "'entity_id': '...', 'new_entity_id': '...'}"
    )

    websocket_example = {
        "id": 1,
        "type": "config/entity_registry/update",
        "entity_id": "binary_sensor.basement",
        "new_entity_id": "binary_sensor.sf_basement_motion",
    }

    print("\n   Example WebSocket command:")
    print(f"   {json.dumps(websocket_example, indent=2)}")


def main():
    """Run main diagnostic function."""
    print("🏠 Home Assistant API Diagnostic Tool")
    print("=" * 60)

    if not TOKEN:
        print("❌ No HA_TOKEN found in .env file!")
        print("   Create a .env file with: HA_TOKEN=your_long_lived_access_token")
        return

    print(f"🔗 Testing connection to: {HA_URL}")

    # Test 1: Basic connection
    if not test_api_connection():
        print("❌ Basic connection failed - stopping tests")
        return

    # Test 2: Explore available endpoints
    successful_endpoints = test_api_endpoints()

    # Test 3: Entity registry read
    entity_data = test_entity_registry_read()

    # Test 4: States endpoint
    states_work = test_states_endpoint()

    # Test 5: Entity rename attempts
    test_entity_rename(entity_data)

    # Test 6: Service call method
    test_service_call_method()

    # Test 7: WebSocket method info
    show_websocket_info()

    # Summary
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"✅ Working endpoints: {len(successful_endpoints)}")
    registry_access = "Yes" if entity_data else "No (likely WebSocket only)"
    print(f"✅ Entity registry access: {registry_access}")
    states_status = "Yes" if states_work else "No"
    print(f"✅ States endpoint: {states_status}")
    print("✅ Entity renaming: Requires WebSocket API or UI")
    print("\n📝 RECOMMENDATIONS:")
    print("   1. Use WebSocket API for entity registry operations")
    print("   2. REST API works for states but not entity management")
    print("   3. Service calls only change friendly names, not entity IDs")
    print("   4. Manual UI renaming may be most reliable option")


if __name__ == "__main__":
    main()
