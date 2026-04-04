import json
import logging
import os

logger = logging.getLogger(__name__)

# Directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
CRM_DIR = BASE_DIR

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Backup settings
BACKUP_KEEP_COUNT = 10

# Job cleanup (seconds)
JOB_CLEANUP_INTERVAL = 3600
JOB_RETENTION_SECONDS = 3600

# Log rotation
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# JSON validation
MAX_JSON_SIZE = 10 * 1024 * 1024


def load_config():
    config_path = os.path.join(BASE_DIR, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"config.json not found at {config_path}. "
            "Create it from config.example.json"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    if env_password:
        config["sender_password"] = env_password
        logger.info("Using GMAIL_APP_PASSWORD from environment")

    required = ["sender_email", "sender_password", "smtp_server", "smtp_port"]
    missing = [k for k in required if not config.get(k)]
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")

    return config


def load_template(config: dict) -> str:
    template_path = os.path.join(
        BASE_DIR, config.get("template_file", "email_template.html")
    )
    if not os.path.exists(template_path):
        logger.warning(
            f"Template file not found: {template_path}, using empty template"
        )
        return ""

    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


config = load_config()
template_html = load_template(config)
