import logging
import os
import shutil
from datetime import datetime
from typing import Optional

from server.config import BACKUP_DIR, BACKUP_KEEP_COUNT

logger = logging.getLogger(__name__)


def create_backup(filepath: str) -> Optional[str]:
    if not os.path.exists(filepath):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(filepath)
    backup_name = f"{filename}.{timestamp}.bak"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    shutil.copy2(filepath, backup_path)
    logger.info("Created backup: %s", backup_path)

    cleanup_old_backups(filename)

    return backup_path


def cleanup_old_backups(filename: str, keep: int = BACKUP_KEEP_COUNT):
    pattern = f"{filename}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            backups.append((full_path, os.path.getmtime(full_path)))

    backups.sort(key=lambda x: x[1], reverse=True)

    for path, _ in backups[keep:]:
        try:
            os.remove(path)
            logger.debug("Removed old backup: %s", path)
        except Exception as e:
            logger.warning("Failed to remove old backup %s: %s", path, e)


def find_backup(filename: str) -> Optional[str]:
    pattern = f"{filename}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            backups.append((full_path, os.path.getmtime(full_path)))

    if not backups:
        return None

    backups.sort(key=lambda x: x[1], reverse=True)
    return backups[0][0]
