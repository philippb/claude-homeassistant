#!/usr/bin/env python3
"""Home Assistant Entity Rename Tool.

Renames entities via the Home Assistant WebSocket API.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    print("❌ Error: websockets package not installed")
    print("   Run: pip install websockets")
    sys.exit(1)


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


async def rename_entity(old_entity_id: str, new_entity_id: str) -> bool:
    """Rename an entity via WebSocket API."""
    load_env_file()

    ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
    token = os.getenv("HA_TOKEN", "")

    if not token:
        print("❌ Error: HA_TOKEN not found in environment or .env file")
        print("   Add to .env: HA_TOKEN=your_long_lived_access_token")
        return False

    # Convert http(s) URL to ws(s) URL
    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/websocket"

    try:
        async with websockets.connect(ws_url) as ws:
            # Receive auth_required message
            msg = json.loads(await ws.recv())
            if msg["type"] != "auth_required":
                print(f"❌ Unexpected message: {msg}")
                return False

            # Send auth
            await ws.send(json.dumps({"type": "auth", "access_token": token}))

            # Receive auth result
            msg = json.loads(await ws.recv())
            if msg["type"] != "auth_ok":
                print(f"❌ Authentication failed: {msg}")
                return False

            print(f"✅ Connected to Home Assistant")

            # Send entity registry update
            await ws.send(
                json.dumps(
                    {
                        "id": 1,
                        "type": "config/entity_registry/update",
                        "entity_id": old_entity_id,
                        "new_entity_id": new_entity_id,
                    }
                )
            )

            # Receive response
            msg = json.loads(await ws.recv())

            if msg.get("success"):
                print(f"✅ Renamed: {old_entity_id} → {new_entity_id}")
                return True
            else:
                error = msg.get("error", {}).get("message", "Unknown error")
                print(f"❌ Failed to rename {old_entity_id}: {error}")
                return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def rename_entities(renames: list[tuple[str, str]]) -> int:
    """Rename multiple entities. Returns count of successful renames."""
    load_env_file()

    ha_url = os.getenv("HA_URL", "http://homeassistant.local:8123")
    token = os.getenv("HA_TOKEN", "")

    if not token:
        print("❌ Error: HA_TOKEN not found in environment or .env file")
        print("   Add to .env: HA_TOKEN=your_long_lived_access_token")
        return 0

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/websocket"

    success_count = 0

    try:
        async with websockets.connect(ws_url) as ws:
            # Auth sequence
            msg = json.loads(await ws.recv())
            if msg["type"] != "auth_required":
                print(f"❌ Unexpected message: {msg}")
                return 0

            await ws.send(json.dumps({"type": "auth", "access_token": token}))
            msg = json.loads(await ws.recv())
            if msg["type"] != "auth_ok":
                print(f"❌ Authentication failed: {msg}")
                return 0

            print(f"✅ Connected to Home Assistant")

            # Rename each entity
            for i, (old_id, new_id) in enumerate(renames, start=1):
                await ws.send(
                    json.dumps(
                        {
                            "id": i,
                            "type": "config/entity_registry/update",
                            "entity_id": old_id,
                            "new_entity_id": new_id,
                        }
                    )
                )

                msg = json.loads(await ws.recv())

                if msg.get("success"):
                    print(f"✅ Renamed: {old_id} → {new_id}")
                    success_count += 1
                else:
                    error = msg.get("error", {}).get("message", "Unknown error")
                    print(f"❌ Failed to rename {old_id}: {error}")

    except Exception as e:
        print(f"❌ Error: {e}")

    return success_count


def main():
    if len(sys.argv) < 3:
        print("Usage: python rename_entity.py <old_entity_id> <new_entity_id>")
        print("       python rename_entity.py --batch <old1>,<new1> <old2>,<new2> ...")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        # Batch mode: multiple old,new pairs
        renames = []
        for arg in sys.argv[2:]:
            if "," in arg:
                old_id, new_id = arg.split(",", 1)
                renames.append((old_id.strip(), new_id.strip()))

        if not renames:
            print("❌ No valid entity pairs provided")
            sys.exit(1)

        count = asyncio.run(rename_entities(renames))
        print(f"\n✅ Successfully renamed {count}/{len(renames)} entities")
        sys.exit(0 if count == len(renames) else 1)
    else:
        # Single rename
        old_entity_id = sys.argv[1]
        new_entity_id = sys.argv[2]
        success = asyncio.run(rename_entity(old_entity_id, new_entity_id))
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
