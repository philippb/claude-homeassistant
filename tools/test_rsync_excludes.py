#!/usr/bin/env python3
"""Test suite for rsync exclude files configuration.

Validates that:
1. Both exclude files exist
2. Push excludes protect .storage/ directory
3. Pull excludes allow .storage/ directory
4. Makefile references correct exclude files
"""

import sys
from pathlib import Path


class RsyncExcludesTest:
    """Test rsync exclude files configuration."""

    def __init__(self, project_root: str = "."):
        """Initialize the test."""
        self.project_root = Path(project_root).resolve()
        self.errors = []
        self.warnings = []

    def test_exclude_files_exist(self) -> bool:
        """Test that both exclude files exist."""
        pull_excludes = self.project_root / ".rsync-excludes-pull"
        push_excludes = self.project_root / ".rsync-excludes-push"

        passed = True

        if not pull_excludes.exists():
            self.errors.append(".rsync-excludes-pull file not found")
            passed = False
        else:
            print("  ✓ .rsync-excludes-pull exists")

        if not push_excludes.exists():
            self.errors.append(".rsync-excludes-push file not found")
            passed = False
        else:
            print("  ✓ .rsync-excludes-push exists")

        return passed

    def test_push_excludes_protect_storage(self) -> bool:
        """Test that push excludes protect .storage/ directory."""
        push_excludes = self.project_root / ".rsync-excludes-push"

        if not push_excludes.exists():
            self.errors.append("Cannot test: .rsync-excludes-push not found")
            return False

        content = push_excludes.read_text()

        # Check for .storage/ protection
        if ".storage/" in content or ".storage" in content:
            print("  ✓ .rsync-excludes-push protects .storage/")
            return True
        else:
            self.errors.append(
                ".rsync-excludes-push does NOT protect .storage/ - "
                "this will cause HA runtime state to be overwritten!"
            )
            return False

    def test_pull_excludes_allow_storage(self) -> bool:
        """Test that pull excludes allow .storage/ directory (not excluded)."""
        pull_excludes = self.project_root / ".rsync-excludes-pull"

        if not pull_excludes.exists():
            self.errors.append("Cannot test: .rsync-excludes-pull not found")
            return False

        content = pull_excludes.read_text()
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Check that .storage/ is NOT excluded (or only specific files within)
        storage_excluded = False
        for line in lines:
            # Check for blanket .storage/ exclusion
            if line == ".storage/" or line == ".storage":
                storage_excluded = True
                break

        if storage_excluded:
            self.warnings.append(
                ".rsync-excludes-pull excludes entire .storage/ - "
                "consider allowing it for local backup/reference"
            )
            print("  ⚠ .rsync-excludes-pull excludes .storage/ (warning)")
            return True  # Not a failure, just a warning
        else:
            print("  ✓ .rsync-excludes-pull allows .storage/ for backup")
            return True

    def test_makefile_uses_correct_excludes(self) -> bool:
        """Test that Makefile references the correct exclude files."""
        makefile = self.project_root / "Makefile"

        if not makefile.exists():
            self.errors.append("Makefile not found")
            return False

        content = makefile.read_text()
        passed = True

        # Check pull uses -pull excludes
        if "exclude-from=.rsync-excludes-pull" in content:
            print("  ✓ Makefile pull uses .rsync-excludes-pull")
        else:
            self.errors.append("Makefile pull does not use .rsync-excludes-pull")
            passed = False

        # Check push uses -push excludes
        if "exclude-from=.rsync-excludes-push" in content:
            print("  ✓ Makefile push uses .rsync-excludes-push")
        else:
            self.errors.append("Makefile push does not use .rsync-excludes-push")
            passed = False

        return passed

    def test_push_excludes_critical_files(self) -> bool:
        """Test that push excludes protect critical HA files."""
        push_excludes = self.project_root / ".rsync-excludes-push"

        if not push_excludes.exists():
            return False

        content = push_excludes.read_text()

        # Critical files that should be protected
        critical_patterns = [
            ".storage/",  # Entire storage directory
        ]

        # Optional but recommended protections
        recommended_patterns = [
            "home-assistant_v2.db",
            "*.log",
        ]

        passed = True

        # Check critical patterns
        for pattern in critical_patterns:
            if pattern in content:
                print(f"  ✓ Push excludes protect: {pattern}")
            else:
                self.errors.append(f"Push excludes missing critical pattern: {pattern}")
                passed = False

        # Check recommended patterns (warnings only)
        for pattern in recommended_patterns:
            if pattern in content or pattern.replace("*", "") in content:
                print(f"  ✓ Push excludes protect: {pattern}")
            else:
                self.warnings.append(f"Consider adding to push excludes: {pattern}")

        return passed

    def run(self) -> bool:
        """Run all tests."""
        print("🔍 Testing Rsync Exclude Files Configuration")
        print("=" * 50)
        print()

        all_passed = True

        tests = [
            ("Exclude files exist", self.test_exclude_files_exist),
            ("Push excludes protect .storage/", self.test_push_excludes_protect_storage),
            ("Pull excludes allow .storage/", self.test_pull_excludes_allow_storage),
            ("Makefile uses correct excludes", self.test_makefile_uses_correct_excludes),
            ("Push excludes critical files", self.test_push_excludes_critical_files),
        ]

        for test_name, test_func in tests:
            print(f"\n📋 {test_name}")
            print("-" * 40)
            try:
                if not test_func():
                    all_passed = False
            except Exception as e:
                self.errors.append(f"Test '{test_name}' threw exception: {e}")
                all_passed = False

        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY")
        print("=" * 50)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   • {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   • {warning}")

        if all_passed and not self.errors:
            print("\n✅ All rsync exclude tests passed!")
        else:
            print("\n❌ Some tests failed. Please fix the errors above.")

        return all_passed and not self.errors


def main():
    """Run main function for command line usage."""
    project_root = sys.argv[1] if len(sys.argv) > 1 else "."

    tester = RsyncExcludesTest(project_root)
    success = tester.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
