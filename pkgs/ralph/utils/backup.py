"""BD issue snapshot and restore for rollback support."""

import json
import logging
from dataclasses import asdict
from pathlib import Path

import bd

logger = logging.getLogger(__name__)


def snapshot_issues(iteration: int, backup_dir: Path, bd_cwd: Path | None = None) -> Path:
    """Dump all bd issues to a JSON file.

    Args:
        iteration: Current iteration index (used in filename).
        backup_dir: Directory to write the snapshot.
        bd_cwd: Working directory for bd CLI.

    Returns:
        Path to the created snapshot file.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    issues = bd.list_issues(cwd=bd_cwd)
    path = backup_dir / f"issues_iter_{iteration}.json"
    path.write_text(json.dumps([asdict(i) for i in issues], default=str, indent=2))
    logger.info("Snapshot %d issue(s) to %s", len(issues), path)
    return path


def restore_issues_from_snapshot(snapshot_path: Path, bd_cwd: Path | None = None) -> None:
    """Best-effort restore of issue status and assignee from a snapshot.

    Only sends fields that are actually present in the snapshot.

    Args:
        snapshot_path: Path to a JSON snapshot file.
        bd_cwd: Working directory for bd CLI.
    """
    data = json.loads(snapshot_path.read_text())
    restored = 0
    for item in data:
        try:
            kwargs: dict = {}
            if "status" in item and item["status"] is not None:
                kwargs["status"] = item["status"]
            if "assignee" in item and item["assignee"] is not None:
                kwargs["assignee"] = item["assignee"]
            if not kwargs:
                continue
            bd.update_issue(item["id"], cwd=bd_cwd, **kwargs)
            restored += 1
        except Exception:
            logger.warning("Failed to restore issue %s", item.get("id", "?"))
    logger.info("Restored %d/%d issues from %s", restored, len(data), snapshot_path)


MAX_SNAPSHOTS = 10


def prune_old_snapshots(backup_dir: Path, keep: int = MAX_SNAPSHOTS) -> None:
    """Delete oldest snapshots beyond the keep limit.

    Args:
        backup_dir: Directory containing snapshot files.
        keep: Number of most recent snapshots to retain.
    """
    snapshots = sorted(backup_dir.glob("issues_iter_*.json"))
    for old in snapshots[:-keep] if len(snapshots) > keep else []:
        old.unlink()
        logger.info("Pruned old snapshot %s", old.name)
