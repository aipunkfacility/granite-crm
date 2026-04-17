import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = sys.argv[1]
BACKUP_FILE = sys.argv[2]

if not os.path.exists(DB_PATH):
    print(f"[ERROR] DB not found: {DB_PATH}")
    sys.exit(1)

os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)

src = sqlite3.connect(DB_PATH)
dst = sqlite3.connect(BACKUP_FILE)
src.backup(dst)
dst.close()
src.close()

size_mb = os.path.getsize(BACKUP_FILE) // 1048576
print(f"[OK] granite_backup.db  ({size_mb} MB)")
