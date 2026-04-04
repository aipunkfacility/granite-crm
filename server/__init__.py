import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
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


def get_api_token() -> str:
    return os.environ.get("CRM_API_TOKEN", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from server.services.batch import start_cleanup_task

    start_cleanup_task()
    yield


app = FastAPI(title="Email Sender Server", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = ["/health", "/template", "/"]
    if request.url.path in public_paths:
        return await call_next(request)

    if request.method == "GET":
        return await call_next(request)

    token = get_api_token()
    if token:
        auth_header = request.headers.get("Authorization", "")
        provided_token = auth_header.replace("Bearer ", "")
        if provided_token != token:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(send.router)
app.include_router(template.router)
app.include_router(db.router)
app.include_router(backup.router)


@app.get("/")
async def root():
    index_path = Path(config.BASE_DIR) / "index.html"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        token = get_api_token()
        logger.info(f"API token from env: {'SET' if token else 'EMPTY'}")
        if token:
            old = 'const API_TOKEN = "";'
            new = f'const API_TOKEN = "{token}";'
            if old in content:
                content = content.replace(old, new)
                logger.info("API token injected into index.html")
            else:
                logger.warning("Could not find API_TOKEN placeholder in index.html")
        response = HTMLResponse(content=content, media_type="text/html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
    return {"message": "index.html not found"}


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

app.mount("/static", StaticFiles(directory=BASE_DIR, html=True), name="static")


@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    file_path = Path(BASE_DIR) / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"detail": "Not found"})
