import json
import logging
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request

from server.config import DB_DIR
from server.services.backup import create_backup, find_backup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/db", tags=["db"])


def validate_json_data(data) -> tuple[bool, str]:
    if not isinstance(data, (dict, list)):
        return False, "Root must be an object or array"

    data_str = json.dumps(data)
    max_size = 10 * 1024 * 1024
    if len(data_str) > max_size:
        return False, f"Data too large: {len(data_str)} bytes (max: {max_size})"

    return True, ""


@router.get("/list")
async def list_db_files():
    try:
        files = []
        for f in os.listdir(DB_DIR):
            if f.endswith(".json"):
                path = os.path.join(DB_DIR, f)
                stat = os.stat(path)
                files.append(
                    {
                        "name": f,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                )

        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"files": files}

    except Exception as e:
        logger.error(f"Failed to list DB files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filename}")
async def read_db_file(filename: str):
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    except json.JSONDecodeError:
        backup_path = find_backup(safe_name)
        if backup_path:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON. Backup available: {os.path.basename(backup_path)}",
            )
        raise HTTPException(status_code=500, detail="Invalid JSON")

    except Exception as e:
        logger.error(f"Failed to read {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{filename}")
async def write_db_file(filename: str, request: Request):
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    try:
        body = await request.json()

        is_valid, error_msg = validate_json_data(body)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Validation failed: {error_msg}"
            )

        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing == body:
                    return {"success": True, "file": safe_name, "unchanged": True}
            except:
                pass

        backup_path = create_backup(filepath)
        if backup_path:
            logger.info(f"Backup created: {os.path.basename(backup_path)}")

        temp_path = filepath + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

        os.replace(temp_path, filepath)

        logger.info(f"Saved {safe_name} ({os.path.getsize(filepath)} bytes)")
        return {
            "success": True,
            "file": safe_name,
            "size": os.path.getsize(filepath),
            "backup": os.path.basename(backup_path) if backup_path else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_db_file(filename: str):
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    filepath = os.path.join(DB_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        backup_path = create_backup(filepath)
        os.remove(filepath)

        logger.info(f"Deleted {safe_name}, backup at {backup_path}")
        return {
            "success": True,
            "file": safe_name,
            "backup": os.path.basename(backup_path) if backup_path else None,
        }

    except Exception as e:
        logger.error(f"Failed to delete {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filename}/backups")
async def list_backups(filename: str):
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    from server.config import BACKUP_DIR

    pattern = f"{safe_name}."
    backups = []

    for f in os.listdir(BACKUP_DIR):
        if f.startswith(pattern) and f.endswith(".bak"):
            full_path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(full_path)
            backups.append(
                {
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

    backups.sort(key=lambda x: x["modified"], reverse=True)
    return {"file": safe_name, "backups": backups}


@router.post("/{filename}/restore")
async def restore_backup(filename: str):
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files allowed")

    safe_name = os.path.basename(filename)
    from server.services.backup import find_backup
    from server.config import BACKUP_DIR

    backup_path = find_backup(safe_name)

    if not backup_path:
        raise HTTPException(status_code=404, detail="No backup found")

    filepath = os.path.join(DB_DIR, safe_name)

    try:
        if os.path.exists(filepath):
            create_backup(filepath)

        import shutil

        shutil.copy2(backup_path, filepath)
        logger.info(f"Restored {safe_name} from {backup_path}")

        return {
            "success": True,
            "file": safe_name,
            "restored_from": os.path.basename(backup_path),
        }

    except Exception as e:
        logger.error(f"Failed to restore {safe_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
