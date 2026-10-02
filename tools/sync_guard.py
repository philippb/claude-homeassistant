#!/usr/bin/env python3
"""Stop `make pull` / `make push` from silently overwriting work.

Both targets run `rsync --delete`, which makes the destination an exact copy:

* push overwrites anything changed on Home Assistant since the last pull. The
  HA UI rewrites automations.yaml / scripts.yaml / scenes.yaml on every save,
  so an automation edited in the UI is lost, and a file created there deleted.
* pull overwrites local edits that were never pushed.

The guard keeps a baseline: a copy of the config as it was after the last
successful pull or push. Before a transfer it asks rsync (dry run, checksums)
what would change and compares that with the baseline:

    check-push  refuse if HA differs from the baseline in any file push manages
    check-pull  refuse if a file pull would overwrite or delete was edited locally
    record      store the current local config as the new baseline

Exit status 1 lists the conflicting files. `make pull FORCE=1` / `make push
FORCE=1` skip the check when overwriting is intended.
"""

import argparse
import filecmp
import subprocess
import sys
from pathlib import Path


def rsync_changes(source, dest, excludes):
    """Files rsync would transfer or delete going source -> dest (dry run, by checksum)."""
    cmd = [
        "rsync",
        "--recursive",
        "--links",
        "--checksum",
        "--dry-run",
        "--itemize-changes",
        "--delete",
        f"--exclude-from={excludes}",
        source,
        dest,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"sync_guard: rsync dry run failed:\n{result.stderr.strip()}")
    changes = []
    for line in result.stdout.splitlines():
        if line.startswith("*deleting"):
            path = line.split(None, 1)[1]
        elif line[:1] in "<>c" and len(line) > 12:
            path = line[12:]
        else:
            continue
        if not path.endswith("/"):
            changes.append(path)
    return changes


def refuse(message, conflicts, hint):
    """Print the conflicting files and exit non-zero."""
    print(f"sync_guard: {message}", file=sys.stderr)
    for path in conflicts:
        print(f"  {path}", file=sys.stderr)
    print(hint, file=sys.stderr)
    sys.exit(1)


def check_push(args):
    """Refuse a push that would overwrite or delete changes made on HA."""
    baseline = Path(args.baseline)
    if not baseline.is_dir():
        refuse(
            "no baseline from a previous `make pull`, so changes made on Home Assistant"
            " cannot be detected.",
            [],
            "Run `make pull` first, or `make push FORCE=1` to overwrite Home Assistant anyway.",
        )
    conflicts = rsync_changes(f"{baseline}/", args.remote, args.excludes)
    if conflicts:
        refuse(
            "these files changed on Home Assistant since the last pull/push"
            " (e.g. edited in the UI); push would overwrite or delete them:",
            conflicts,
            "Run `make pull` to get them (your local edits are kept only if you"
            " pushed them), or `make push FORCE=1` to overwrite.",
        )


def check_pull(args):
    """Refuse a pull that would overwrite or delete local edits that were never pushed."""
    baseline = Path(args.baseline)
    if not baseline.is_dir():
        return  # first pull: replacing the template config is the point
    local = Path(args.local)
    conflicts = []
    for path in rsync_changes(args.remote, args.local, args.excludes):
        mine, base = local / path, baseline / path
        if mine.exists() != base.exists():
            conflicts.append(path)
        elif mine.exists() and not filecmp.cmp(mine, base, shallow=False):
            conflicts.append(path)
    if conflicts:
        refuse(
            "these local files were changed since the last pull/push and not pushed;"
            " pull would overwrite or delete them:",
            conflicts,
            "Run `make push` first, or `make pull FORCE=1` to discard them.",
        )


def record(args):
    """Store the local config as the baseline after a successful transfer."""
    Path(args.baseline).mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync",
        "--recursive",
        "--links",
        "--checksum",
        "--delete",
        f"--exclude-from={args.excludes}",
        f"{str(args.local).rstrip('/')}/",
        f"{args.baseline}/",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"sync_guard: could not record the baseline:\n{result.stderr.strip()}")


def main():
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("command", choices=["check-push", "check-pull", "record"])
    parser.add_argument(
        "--remote", required=True, help="rsync path of HA's config, e.g. ha:/config/"
    )
    parser.add_argument("--local", required=True, help="local config directory")
    parser.add_argument(
        "--baseline", required=True, help="where the baseline copy is kept"
    )
    parser.add_argument(
        "--excludes", required=True, help="rsync exclude file of the transfer"
    )
    args = parser.parse_args()
    {"check-push": check_push, "check-pull": check_pull, "record": record}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
