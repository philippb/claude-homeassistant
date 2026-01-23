"""Integration tests for rsync exclude rules.

Tests that the .rsync-excludes-* files correctly:
1. Exclude sensitive directories from transfer (pull)
2. Protect server-side runtime state from deletion during push
3. Allow normal config files to sync
"""

# pylint: disable=import-error,redefined-outer-name

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

PULL_EXCLUDES = Path(__file__).parent.parent / ".rsync-excludes-pull"
PUSH_EXCLUDES = Path(__file__).parent.parent / ".rsync-excludes-push"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for the test session."""
    temp = Path(tempfile.mkdtemp(prefix="rsync_test_"))
    yield temp
    if temp.exists():
        shutil.rmtree(temp)


@pytest.fixture
def local_dir(temp_dir):
    """Create a local config tree used as the rsync source."""
    local = temp_dir / "local"
    local.mkdir()
    (local / ".storage" / "core").mkdir(parents=True)
    (local / ".storage" / "core" / "entity_registry").write_text(
        "entity_registry_v2_updated"
    )
    (local / "configuration.yaml").write_text("homeassistant: NEW")
    (local / "automations.yaml").write_text("automation: NEW")
    return local


@pytest.fixture
def remote_dir(temp_dir):
    """Create a remote config tree used as the rsync destination."""
    remote = temp_dir / "remote"
    remote.mkdir()
    (remote / ".storage" / "auth").mkdir(parents=True)
    (remote / ".storage" / "core").mkdir(parents=True)
    (remote / "backups").mkdir()
    (remote / "www").mkdir()
    (remote / "custom_components").mkdir()
    (remote / "image").mkdir()
    (remote / "tmp_backups").mkdir()
    (remote / "deps").mkdir()
    (remote / "tts").mkdir()

    (remote / ".storage" / "auth" / "tokens.json").write_text("SECRET_AUTH_TOKEN")
    (remote / ".storage" / "core" / "entity_registry").write_text("entity_registry_v1")
    (remote / "backups" / "backup.tar").write_text("backup_data")
    (remote / "www" / "index.html").write_text("<html>dashboard</html>")
    (remote / "custom_components" / "my_comp.py").write_text("custom_code")

    (remote / "configuration.yaml").write_text("homeassistant: old")
    (remote / "automations.yaml").write_text("automation: old")

    return remote


def run_rsync(source, dest, excludes):
    """Run rsync with the provided exclude file."""
    cmd = [
        "rsync",
        "-avz",
        "--delete",
        "--checksum",
        f"--exclude-from={excludes}",
        f"{source}/",
        f"{dest}/",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(
            "rsync failed:\n" f"stdout: {result.stdout}\n" f"stderr: {result.stderr}"
        )
    return result


def test_push_updates_config_files(local_dir, remote_dir):
    """Push updates to configuration files."""
    run_rsync(local_dir, remote_dir, PUSH_EXCLUDES)

    assert (
        remote_dir / "configuration.yaml"
    ).exists(), "configuration.yaml should be updated"
    assert (
        remote_dir / "configuration.yaml"
    ).read_text() == "homeassistant: NEW", "configuration.yaml should have NEW content"
    assert (
        remote_dir / "automations.yaml"
    ).exists(), "automations.yaml should be updated"
    assert (
        remote_dir / "automations.yaml"
    ).read_text() == "automation: NEW", "automations.yaml should have NEW content"


def test_push_preserves_storage(local_dir, remote_dir):
    """Push does not overwrite .storage contents on remote."""
    run_rsync(local_dir, remote_dir, PUSH_EXCLUDES)

    assert (
        remote_dir / ".storage" / "core" / "entity_registry"
    ).read_text() == "entity_registry_v1", "Remote .storage should remain unchanged"


def test_push_preserves_backups(local_dir, remote_dir):
    """Push preserves backups on the remote."""
    run_rsync(local_dir, remote_dir, PUSH_EXCLUDES)

    assert (
        remote_dir / "backups" / "backup.tar"
    ).exists(), "Backups should be preserved"


def test_push_preserves_www(local_dir, remote_dir):
    """Push preserves the www directory on the remote."""
    run_rsync(local_dir, remote_dir, PUSH_EXCLUDES)

    assert (
        remote_dir / "www" / "index.html"
    ).exists(), "www directory should be preserved"


def test_push_preserves_custom_components(local_dir, remote_dir):
    """Push preserves custom_components on the remote."""
    run_rsync(local_dir, remote_dir, PUSH_EXCLUDES)

    assert (
        remote_dir / "custom_components" / "my_comp.py"
    ).exists(), "custom_components should be preserved"


def test_pull_excludes_auth_tokens(temp_dir, remote_dir):
    """Pull excludes auth tokens locally."""
    local = temp_dir / "local_pull"
    local.mkdir()

    run_rsync(remote_dir, local, PULL_EXCLUDES)

    assert not (
        local / ".storage" / "auth" / "tokens.json"
    ).exists(), "Auth tokens should NOT be pulled"


def test_pull_allows_storage_core(temp_dir, remote_dir):
    """Pull includes non-sensitive .storage files."""
    local = temp_dir / "local_pull"
    local.mkdir()

    run_rsync(remote_dir, local, PULL_EXCLUDES)

    assert (
        local / ".storage" / "core" / "entity_registry"
    ).read_text() == "entity_registry_v1", "Storage core should be pulled"


def test_pull_excludes_backups(temp_dir, remote_dir):
    """Pull excludes backups locally."""
    local = temp_dir / "local_pull"
    local.mkdir()

    run_rsync(remote_dir, local, PULL_EXCLUDES)

    assert not (
        local / "backups" / "backup.tar"
    ).exists(), "Backups should NOT be pulled"


def test_pull_gets_config_files(temp_dir, remote_dir):
    """Pull brings down config files."""
    local = temp_dir / "local_pull"
    local.mkdir()

    run_rsync(remote_dir, local, PULL_EXCLUDES)

    assert (
        local / "configuration.yaml"
    ).exists(), "configuration.yaml should be pulled"
    assert (local / "automations.yaml").exists(), "automations.yaml should be pulled"


def test_pull_deletes_stale_local_files(temp_dir, remote_dir):
    """Pull deletes stale local files with --delete."""
    local = temp_dir / "local_pull"
    local.mkdir()
    (local / "stale_file.yaml").write_text("should be deleted")

    run_rsync(remote_dir, local, PULL_EXCLUDES)

    assert not (
        local / "stale_file.yaml"
    ).exists(), "Stale files should be deleted by --delete"
