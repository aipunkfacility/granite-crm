import json
import logging
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException

from server.config import BACKUP_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backups", tags=["backups"])


def _validate_backup_filename(filename: str) -> str:
    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return os.path.basename(filename)


@router.get("")
async def list_all_backups():
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(full_path)
            backups.append(
                {
                    "name": f,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    backups.sort(key=lambda x: x["created"], reverse=True)
    return {"backups": backups}


@router.post("/restore/{backup_name}")
async def restore_from_backup(backup_name: str):
    safe_name = _validate_backup_filename(backup_name)
    backup_path = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail=f"Backup not found: {safe_name}")

    if not safe_name.endswith(".bak"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")

    try:
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info("Restored from backup: %s", safe_name)
        return {
            "success": True,
            "backup": safe_name,
            "contacts": data if isinstance(data, list) else [data],
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON in backup: {e}")
    except Exception as e:
        logger.error("Failed to restore from %s: %s", safe_name, e)
        raise HTTPException(status_code=500, detail=str(e))
