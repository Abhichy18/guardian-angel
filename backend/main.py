"""
Guardian Angel — FastAPI Main Application

Bootstraps the web server, sets up middleware (CORS, error handling),
registers the API routers (auth, consent, events, alerts, audit),
initializes the SQLite database schema on startup, and mounts the static web frontend.
"""

import logging
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from database.db import db
from backend.routers import auth, consent, events, alerts, audit

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("backend.main")

app = FastAPI(
    title="Guardian Angel",
    description="Real-Time Scam & Fraud Shield for Elderly Family Members",
    version="1.0.0"
)

# CORS middleware configuration
allowed_origins = [
    origin.strip() 
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router)
app.include_router(consent.router)
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(audit.router)

@app.on_event("startup")
async def startup_db_client():
    """Startup hook: connect to and initialize the SQLite database."""
    logger.info("Starting up database...")
    await db.connect()
    # Close it since individual endpoints handle their own connections, 
    # but the first connect builds the schema/indices.
    await db.close()
    logger.info("Database schema verification completed.")

@app.get("/api/health", tags=["system"])
async def health_check():
    """Simple API health check endpoint used by Docker/deployment checkers."""
    return {"status": "healthy", "service": "guardian-angel-backend"}

# Mount Static Frontend Files
# Ensure the frontend directory exists before mounting to prevent startup failures.
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
os.makedirs(frontend_dir, exist_ok=True)
os.makedirs(os.path.join(frontend_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(frontend_dir, "js"), exist_ok=True)

# Mount /css and /js explicitly, serve index.html at root
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

@app.get("/")
async def serve_landing():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/onboarding")
async def serve_onboarding():
    return FileResponse(os.path.join(frontend_dir, "onboarding.html"))

@app.get("/elder-dashboard")
async def serve_elder_dashboard():
    return FileResponse(os.path.join(frontend_dir, "elder-dashboard.html"))

@app.get("/family-dashboard")
async def serve_family_dashboard():
    return FileResponse(os.path.join(frontend_dir, "family-dashboard.html"))
