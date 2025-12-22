#!/usr/bin/env python3
"""Integration tests for rsync filter rules.

Tests that the .rsync-filter file correctly:
1. Excludes sensitive directories from transfer (both push and pull)
2. Protects server-side directories from deletion during push
3. Allows normal config files to sync

Run with: python tools/test_rsync_filter.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class RsyncFilterTest:
    """Test the rsync filter rules work correctly."""

    def __init__(self):
        """Initialize test with paths."""
        self.project_root = Path(__file__).parent.parent
        self.filter_file = self.project_root / ".rsync-filter"
        self.temp_dir = None
        self.local_dir = None
        self.remote_dir = None
        self.errors = []

    def setup(self):
        """Create temporary test directories."""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rsync_test_"))
        self.local_dir = self.temp_dir / "local"
        self.remote_dir = self.temp_dir / "remote"

        # Create directory structures
        self.local_dir.mkdir()
        self.remote_dir.mkdir()

        # === REMOTE (simulated HA server) ===
        # Protected directories that should NOT be deleted on push
        (self.remote_dir / ".storage" / "auth").mkdir(parents=True)
        (self.remote_dir / ".storage" / "core").mkdir(parents=True)
        (self.remote_dir / "backups").mkdir()
        (self.remote_dir / "www").mkdir()
        (self.remote_dir / "custom_components").mkdir()
        (self.remote_dir / "image").mkdir()
        (self.remote_dir / "tmp_backups").mkdir()
        (self.remote_dir / "deps").mkdir()
        (self.remote_dir / "tts").mkdir()

        # Files in protected directories
        (self.remote_dir / ".storage" / "auth" / "tokens.json").write_text(
            "SECRET_AUTH_TOKEN"
        )
        (self.remote_dir / ".storage" / "core" / "entity_registry").write_text(
            "entity_registry_v1"
        )
        (self.remote_dir / "backups" / "backup.tar").write_text("backup_data")
        (self.remote_dir / "www" / "index.html").write_text("<html>dashboard</html>")
        (self.remote_dir / "custom_components" / "my_comp.py").write_text("custom_code")

        # Config files that SHOULD be synced
        (self.remote_dir / "configuration.yaml").write_text("homeassistant: old")
        (self.remote_dir / "automations.yaml").write_text("automation: old")

        # === LOCAL (what we'd push) ===
        (self.local_dir / ".storage" / "core").mkdir(parents=True)
        (self.local_dir / ".storage" / "core" / "entity_registry").write_text(
            "entity_registry_v2_updated"
        )
        (self.local_dir / "configuration.yaml").write_text("homeassistant: NEW")
        (self.local_dir / "automations.yaml").write_text("automation: NEW")

    def teardown(self):
        """Clean up temporary directories."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def run_rsync(self, source: Path, dest: Path) -> subprocess.CompletedProcess:
        """Run rsync with the filter file."""
        cmd = [
            "rsync",
            "-avz",
            "--delete",
            "--checksum",  # Use checksum comparison (more reliable for tests)
            f"--filter=. {self.filter_file}",
            f"{source}/",
            f"{dest}/",
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def assert_file_exists(self, path: Path, msg: str):
        """Assert a file exists."""
        if not path.exists():
            self.errors.append(f"FAIL: {msg} - File missing: {path}")
            return False
        return True

    def assert_file_not_exists(self, path: Path, msg: str):
        """Assert a file does not exist."""
        if path.exists():
            self.errors.append(f"FAIL: {msg} - File should not exist: {path}")
            return False
        return True

    def assert_file_content(self, path: Path, expected: str, msg: str):
        """Assert a file has expected content."""
        if not path.exists():
            self.errors.append(f"FAIL: {msg} - File missing: {path}")
            return False
        actual = path.read_text()
        if actual != expected:
            self.errors.append(f"FAIL: {msg} - Expected '{expected}', got '{actual}'")
            return False
        return True

    def test_push_updates_config_files(self):
        """Test that push updates config files on remote."""
        print("  Testing: Push updates config files...")
        self.run_rsync(self.local_dir, self.remote_dir)

        self.assert_file_content(
            self.remote_dir / "configuration.yaml",
            "homeassistant: NEW",
            "configuration.yaml should be updated",
        )
        self.assert_file_content(
            self.remote_dir / "automations.yaml",
            "automation: NEW",
            "automations.yaml should be updated",
        )

    def test_push_preserves_auth_tokens(self):
        """Test that push does NOT delete auth tokens."""
        print("  Testing: Push preserves auth tokens...")
        self.run_rsync(self.local_dir, self.remote_dir)

        self.assert_file_exists(
            self.remote_dir / ".storage" / "auth" / "tokens.json",
            "Auth tokens should be preserved",
        )
        self.assert_file_content(
            self.remote_dir / ".storage" / "auth" / "tokens.json",
            "SECRET_AUTH_TOKEN",
            "Auth token content should be unchanged",
        )

    def test_push_preserves_backups(self):
        """Test that push does NOT delete backups."""
        print("  Testing: Push preserves backups...")
        self.run_rsync(self.local_dir, self.remote_dir)

        self.assert_file_exists(
            self.remote_dir / "backups" / "backup.tar",
            "Backups should be preserved",
        )

    def test_push_preserves_www(self):
        """Test that push does NOT delete www directory."""
        print("  Testing: Push preserves www...")
        self.run_rsync(self.local_dir, self.remote_dir)

        self.assert_file_exists(
            self.remote_dir / "www" / "index.html",
            "www directory should be preserved",
        )

    def test_push_preserves_custom_components(self):
        """Test that push does NOT delete custom_components."""
        print("  Testing: Push preserves custom_components...")
        self.run_rsync(self.local_dir, self.remote_dir)

        self.assert_file_exists(
            self.remote_dir / "custom_components" / "my_comp.py",
            "custom_components should be preserved",
        )

    def test_pull_excludes_auth_tokens(self):
        """Test that pull does NOT sync auth tokens to local."""
        print("  Testing: Pull excludes auth tokens...")

        # Reset local directory
        if self.local_dir.exists():
            shutil.rmtree(self.local_dir)
        self.local_dir.mkdir()

        self.run_rsync(self.remote_dir, self.local_dir)

        self.assert_file_not_exists(
            self.local_dir / ".storage" / "auth" / "tokens.json",
            "Auth tokens should NOT be pulled",
        )

    def test_pull_excludes_backups(self):
        """Test that pull does NOT sync backups to local."""
        print("  Testing: Pull excludes backups...")

        # Reset local directory
        if self.local_dir.exists():
            shutil.rmtree(self.local_dir)
        self.local_dir.mkdir()

        self.run_rsync(self.remote_dir, self.local_dir)

        self.assert_file_not_exists(
            self.local_dir / "backups" / "backup.tar",
            "Backups should NOT be pulled",
        )

    def test_pull_gets_config_files(self):
        """Test that pull DOES sync config files."""
        print("  Testing: Pull gets config files...")

        # Reset local directory
        if self.local_dir.exists():
            shutil.rmtree(self.local_dir)
        self.local_dir.mkdir()

        self.run_rsync(self.remote_dir, self.local_dir)

        self.assert_file_exists(
            self.local_dir / "configuration.yaml",
            "configuration.yaml should be pulled",
        )
        self.assert_file_exists(
            self.local_dir / "automations.yaml",
            "automations.yaml should be pulled",
        )

    def test_pull_deletes_stale_local_files(self):
        """Test that pull --delete removes stale local files."""
        print("  Testing: Pull deletes stale local files...")

        # Reset local directory with a stale file
        if self.local_dir.exists():
            shutil.rmtree(self.local_dir)
        self.local_dir.mkdir()
        (self.local_dir / "stale_file.yaml").write_text("should be deleted")

        self.run_rsync(self.remote_dir, self.local_dir)

        self.assert_file_not_exists(
            self.local_dir / "stale_file.yaml",
            "Stale files should be deleted by --delete",
        )

    def run_all_tests(self) -> bool:
        """Run all tests and return success status."""
        if not self.filter_file.exists():
            print(f"❌ Filter file not found: {self.filter_file}")
            return False

        # Check rsync is available
        try:
            subprocess.run(["rsync", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ rsync not found. Please install rsync.")
            return False

        print("🔍 Running rsync filter integration tests")
        print("=" * 50)
        print()

        try:
            self.setup()

            # Run all test methods
            test_methods = [
                self.test_push_updates_config_files,
                self.test_push_preserves_auth_tokens,
                self.test_push_preserves_backups,
                self.test_push_preserves_www,
                self.test_push_preserves_custom_components,
                self.test_pull_excludes_auth_tokens,
                self.test_pull_excludes_backups,
                self.test_pull_gets_config_files,
                self.test_pull_deletes_stale_local_files,
            ]

            for test_method in test_methods:
                # Re-setup for each test to ensure isolation
                self.teardown()
                self.setup()
                test_method()

        finally:
            self.teardown()

        print()
        print("=" * 50)

        if self.errors:
            print(f"❌ {len(self.errors)} test(s) failed:")
            for error in self.errors:
                print(f"  {error}")
            return False
        else:
            print(f"✅ All {len(test_methods)} tests passed!")
            return True


def main():
    """Run the rsync filter tests."""
    test = RsyncFilterTest()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
