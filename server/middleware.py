from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import os


def get_api_token() -> str:
    return os.environ.get("CRM_API_TOKEN", "")


def setup_middleware(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

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
