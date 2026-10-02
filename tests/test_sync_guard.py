"""Tests for tools/sync_guard.py: make pull/push must not silently overwrite work.

`make push` runs `rsync --delete` local -> HA and `make pull` runs it HA -> local.
Without a guard, push overwrites changes made in the HA UI since the last pull
(the UI rewrites automations.yaml / scripts.yaml on every save), and pull
overwrites local edits that were never pushed. The guard compares against the
state of the last successful sync (a baseline snapshot) and refuses instead.

The "remote" here is a local directory; rsync treats both the same way.
"""

# pylint: disable=import-error,redefined-outer-name

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
GUARD = ROOT / "tools" / "sync_guard.py"
PULL_EXCLUDES = ROOT / ".rsync-excludes-pull"
PUSH_EXCLUDES = ROOT / ".rsync-excludes-push"


@pytest.fixture
def dirs():
    """A synced pair: remote (HA) and local, plus where the baseline lives."""
    temp = Path(tempfile.mkdtemp(prefix="sync_guard_test_"))
    remote, local = temp / "remote", temp / "local"
    for d in (remote, local):
        d.mkdir()
        (d / "configuration.yaml").write_text("homeassistant:\n")
        (d / "automations.yaml").write_text("- id: one\n")
        (d / "scripts.yaml").write_text("hello: {}\n")
    (remote / ".storage").mkdir()
    (remote / ".storage" / "core.config").write_text("{}")
    yield {
        "temp": temp,
        "remote": remote,
        "local": local,
        "baseline": temp / "baseline",
    }
    shutil.rmtree(temp)


def guard(dirs, command, excludes):
    """Run the guard the way the Makefile does."""
    return subprocess.run(
        [
            sys.executable,
            str(GUARD),
            command,
            "--remote",
            f"{dirs['remote']}/",
            "--local",
            f"{dirs['local']}/",
            "--baseline",
            str(dirs["baseline"]),
            "--excludes",
            str(excludes),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def record(dirs):
    """What `make pull` / `make push` do after a successful transfer."""
    result = guard(dirs, "record", PULL_EXCLUDES)
    assert result.returncode == 0, result.stderr


def test_push_refuses_without_baseline(dirs):
    """Fail closed: without a baseline, push cannot know what it would overwrite."""
    result = guard(dirs, "check-push", PUSH_EXCLUDES)
    assert result.returncode != 0
    assert "make pull" in result.stderr


def test_push_allows_local_changes(dirs):
    record(dirs)
    (dirs["local"] / "automations.yaml").write_text("- id: one\n- id: two\n")
    result = guard(dirs, "check-push", PUSH_EXCLUDES)
    assert result.returncode == 0, result.stderr


def test_push_refuses_when_ui_changed_a_file(dirs):
    record(dirs)
    (dirs["remote"] / "automations.yaml").write_text("- id: one\n- id: made-in-ui\n")
    (dirs["local"] / "scripts.yaml").write_text("hello: {changed: true}\n")
    result = guard(dirs, "check-push", PUSH_EXCLUDES)
    assert result.returncode != 0
    assert "automations.yaml" in result.stderr


def test_push_refuses_when_ui_created_a_file(dirs):
    """rsync --delete would remove a file created on HA since the last sync."""
    record(dirs)
    (dirs["remote"] / "scenes.yaml").write_text("- id: new-scene\n")
    result = guard(dirs, "check-push", PUSH_EXCLUDES)
    assert result.returncode != 0
    assert "scenes.yaml" in result.stderr


def test_push_ignores_excluded_runtime_state(dirs):
    """.storage is never pushed, so HA changing it is not a conflict."""
    record(dirs)
    (dirs["remote"] / ".storage" / "core.config").write_text('{"changed": true}')
    result = guard(dirs, "check-push", PUSH_EXCLUDES)
    assert result.returncode == 0, result.stderr


def test_first_pull_is_allowed(dirs):
    """No baseline yet: the first pull replaces the template config, as documented."""
    (dirs["local"] / "automations.yaml").write_text("# template\n")
    result = guard(dirs, "check-pull", PULL_EXCLUDES)
    assert result.returncode == 0, result.stderr


def test_pull_refuses_to_overwrite_unpushed_edit(dirs):
    record(dirs)
    (dirs["local"] / "automations.yaml").write_text("- id: one\n- id: not-pushed\n")
    (dirs["remote"] / "automations.yaml").write_text("- id: one\n- id: made-in-ui\n")
    result = guard(dirs, "check-pull", PULL_EXCLUDES)
    assert result.returncode != 0
    assert "automations.yaml" in result.stderr


def test_pull_refuses_to_delete_unpushed_new_file(dirs):
    record(dirs)
    (dirs["local"] / "new_package.yaml").write_text("sensor: []\n")
    result = guard(dirs, "check-pull", PULL_EXCLUDES)
    assert result.returncode != 0
    assert "new_package.yaml" in result.stderr


def test_pull_allows_ui_changes_without_local_edits(dirs):
    record(dirs)
    (dirs["remote"] / "automations.yaml").write_text("- id: one\n- id: made-in-ui\n")
    result = guard(dirs, "check-pull", PULL_EXCLUDES)
    assert result.returncode == 0, result.stderr


def test_record_after_push_clears_the_conflict(dirs):
    """After a successful push, the pushed state is the new baseline."""
    record(dirs)
    (dirs["local"] / "automations.yaml").write_text("- id: pushed\n")
    shutil.copy(dirs["local"] / "automations.yaml", dirs["remote"] / "automations.yaml")
    record(dirs)
    assert guard(dirs, "check-pull", PULL_EXCLUDES).returncode == 0
    assert guard(dirs, "check-push", PUSH_EXCLUDES).returncode == 0


@pytest.mark.parametrize("target", ["pull", "push"])
def test_makefile_runs_the_guard_before_rsync(target):
    """The guard must run before the transfer and record after it; FORCE=1 skips the check."""
    env = {"HA_HOST": "ha", "PATH": "/usr/bin:/bin"}
    plan = subprocess.run(
        ["make", "-n", target],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    lines = plan.splitlines()
    check = next(i for i, l in enumerate(lines) if f"sync_guard.py check-{target}" in l)
    transfer = next(
        i for i, l in enumerate(lines) if l.lstrip("@ ").startswith("rsync")
    )
    rec = next(i for i, l in enumerate(lines) if "sync_guard.py record" in l)
    assert check < transfer < rec

    forced = subprocess.run(
        ["make", "-n", target, "FORCE=1"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert f"check-{target}" not in forced
