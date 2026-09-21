"""FastAPI application instance and router mounting."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.logging import setup_logging
from config.settings import get_local_storage_path, get_settings
from controllers import (
    admin_controller,
    analytics_controller,
    auth_controller,
    cases_controller,
    sessions_controller,
    turns_controller,
    usage_controller,
    ws_controller,
)
from controllers.research_controller import router as research_router
from core.errors import (
    AppError,
    app_error_handler,
    general_exception_handler,
    http_exception_handler,
)
from core.events import create_start_app_handler, create_stop_app_handler

# Get settings
settings = get_settings()

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="APEX API",
    description="AI Patient Experience Simulator backend service",
    version="1.0.0",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
    openapi_url="/v1/openapi.json",
)

# --- CORS middleware ---
# If you need credentials (cookies/auth), DO NOT use ["*"].
# Make sure settings.cors_origins is a LIST, e.g.:
# ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173"]
allow_origins = settings.cors_origins
allow_credentials = True

# If wildcard is configured, disable credentials to satisfy CORS rules.
if allow_origins == ["http://localhost:5173"]:
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register event handlers
app.add_event_handler("startup", create_start_app_handler(app))
app.add_event_handler("shutdown", create_stop_app_handler(app))

# Register error handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)  # <— wire it
app.add_exception_handler(Exception, general_exception_handler)

# Register routers with /v1 prefix
app.include_router(auth_controller.router, prefix="/v1")
app.include_router(cases_controller.router, prefix="/v1")
app.include_router(analytics_controller.router, prefix="/v1")
app.include_router(sessions_controller.router, prefix="/v1")
app.include_router(turns_controller.router, prefix="/v1")
app.include_router(admin_controller.router, prefix="/v1")
app.include_router(research_router, prefix="/v1")
app.include_router(usage_controller.router, prefix="/v1")
app.include_router(ws_controller.router, prefix="/v1")

local_storage_path = get_local_storage_path()
Path(local_storage_path).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(local_storage_path)), name="media")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Medical Case Simulation API",
        "version": "1.0.0",
        "docs": "/v1/docs",
        "redoc": "/v1/redoc",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    # Use the in-memory app object to avoid import path issues with the reloader
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
