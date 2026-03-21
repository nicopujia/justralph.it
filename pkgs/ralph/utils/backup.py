"""Task snapshot and restore for rollback support."""

import logging
import shutil
from pathlib import Path

import tasks

logger = logging.getLogger(__name__)


def snapshot_tasks(iteration: int, backup_dir: Path, tasks_cwd: Path | None = None) -> Path:
    """Copy tasks.yaml to a timestamped backup file.

    Args:
        iteration: Current iteration index (used in filename).
        backup_dir: Directory to write the snapshot.
        tasks_cwd: Working directory containing tasks.yaml.

    Returns:
        Path to the created snapshot file.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    src = (tasks_cwd or Path.cwd()) / tasks.main.TASKS_FILE
    dest = backup_dir / f"tasks_iter_{iteration}.yaml"
    if src.exists():
        shutil.copy2(src, dest)
        logger.info("Snapshot tasks to %s", dest)
    else:
        dest.write_text("tasks: []\n")
        logger.info("No tasks.yaml found; wrote empty snapshot to %s", dest)
    return dest


def restore_tasks_from_snapshot(snapshot_path: Path, tasks_cwd: Path | None = None) -> None:
    """Restore tasks.yaml from a snapshot file.

    Args:
        snapshot_path: Path to a YAML snapshot file.
        tasks_cwd: Working directory to restore into.
    """
    dest = (tasks_cwd or Path.cwd()) / tasks.main.TASKS_FILE
    shutil.copy2(snapshot_path, dest)
    logger.info("Restored tasks from %s", snapshot_path)


MAX_SNAPSHOTS = 10


def prune_old_snapshots(backup_dir: Path, keep: int = MAX_SNAPSHOTS) -> None:
    """Delete oldest snapshots beyond the keep limit.

    Args:
        backup_dir: Directory containing snapshot files.
        keep: Number of most recent snapshots to retain.
    """
    snapshots = sorted(backup_dir.glob("tasks_iter_*.yaml"))
    for old in snapshots[:-keep] if len(snapshots) > keep else []:
        old.unlink()
        logger.info("Pruned old snapshot %s", old.name)
