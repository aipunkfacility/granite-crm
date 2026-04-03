import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server import config, models
from server.routers import send, template, db, backup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_format)

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
file_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, "crm_server.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
file_handler.setFormatter(file_format)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.info("Server starting up...")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from server.services.batch import start_cleanup_task

    start_cleanup_task()
    yield


app = FastAPI(title="Email Sender Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(send.router)
app.include_router(template.router)
app.include_router(db.router)
app.include_router(backup.router)


@app.get("/health")
async def health():
    db_files = len([f for f in os.listdir(config.DB_DIR) if f.endswith(".json")])
    return {
        "status": "ok",
        "server": "email-sender",
        "timestamp": datetime.now().isoformat(),
        "db_files": db_files,
    }


BASE_DIR = config.BASE_DIR
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="root")
