"""
FastAPI application entrypoint for the College Admissions RAG system.
Run with: uvicorn app.server:app --reload --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path
import os

# Ensure the backend directory is on the path so 'app' is a known package
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="College Admissions RAG API",
    description="Real-time web RAG system for college admission queries",
    version="1.0.0",
)

# Allow the Vite dev server (port 5173) and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
 