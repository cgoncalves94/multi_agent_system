"""FastAPI backend for the LangGraph chat agent.

This module implements the main FastAPI application, handling middleware setup,
exception handling, and static file serving.
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from src.backend.exceptions import AppError
from src.backend.routes import router


# Initialize FastAPI app
app = FastAPI(
    title="LangGraph Chat API",
    description="REST API for LangGraph chat interface",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "http://0.0.0.0:*",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:63342",
        "http://127.0.0.1:63342",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:2024",
        "http://127.0.0.1:2024",
        "https://smith.langchain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Exception handlers
@app.exception_handler(AppError)
async def app_error_handler(_: Any, exc: AppError) -> JSONResponse:
    """Handle application-specific errors.

    Args:
        _: The request that caused the error
        exc: The exception that was raised

    Returns:
        JSONResponse: A formatted error response
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "detail": exc.detail,
                "code": exc.code,
                "status_code": exc.status_code,
            }
        },
    )


# Mount static files
static_files_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_files_path)), name="static")

# Include API routes
app.include_router(router, prefix="/api")


# Serve index.html for the root path
@app.get("/")
async def serve_index():
    return FileResponse(str(static_files_path / "index.html"))
