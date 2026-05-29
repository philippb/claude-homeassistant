#!/usr/bin/env python3
"""Home Assistant Configuration Reload Tool.

Calls the Home Assistant API to reload configuration after config files
have been pushed to the instance. Reloads core configuration as well as the
YAML-managed domains (automations, scenes, scripts) so that changes to those
files take effect without a full restart.
"""

import os
import sys
from pathlib import Path

import requests

# Service endpoints to reload, in order. Core config first, then the
# YAML-managed domains this repo edits. Reloads are idempotent, so calling
# them all on every push is safe.
RELOAD_SERVICES = [
    ("Core configuration", "homeassistant/reload_core_config"),
    ("Automations", "automation/reload"),
    ("Scenes", "scene/reload"),
    ("Scripts", "script/reload"),
]


def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")


def reload_service(ha_url: str, headers: dict, label: str, service_path: str) -> bool:
    """Reload a single Home Assistant service. Returns True on success."""
    url = f"{ha_url}/api/services/{service_path}"

    try:
        print(f"🔄 Reloading {label}...")
        response = requests.post(url, headers=headers, timeout=30)

        if response.status_code == 200:
            print(f"✅ {label} reloaded successfully!")
            return True
        else:
            print(f"❌ Failed to reload {label}: {response.status_code}")
            if response.text:
                print(f"   Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"❌ Timeout: Home Assistant took too long to reload {label}")
        print("   This may indicate a configuration error preventing reload")
        return False

    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error: Cannot reach Home Assistant at {ha_url}")
        print("   Check that Home Assistant is running and accessible")
        return False

    except Exception as e:
        print(f"❌ Unexpected error reloading {label}: {e}")
        return False


def reload_config():
    """Reload Home Assistant core config and YAML-managed domains via API."""
    # Load environment variables
    load_env_file()

    # Get configuration
    ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
    token = os.getenv("HA_TOKEN", "")

    if not token:
        print("❌ Error: HA_TOKEN not found in environment or .env file")
        print("   Create a .env file with: HA_TOKEN=your_long_lived_access_token")
        print("   Get your token from Home Assistant Profile page")
        return False

    # Prepare API request
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    all_ok = True
    for label, service_path in RELOAD_SERVICES:
        if not reload_service(ha_url, headers, label, service_path):
            all_ok = False

    if all_ok:
        print("✅ All configuration reloaded successfully!")
    return all_ok


if __name__ == "__main__":
    SUCCESS = reload_config()
    sys.exit(0 if SUCCESS else 1)
