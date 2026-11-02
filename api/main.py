"""PlaceGuard FastAPI application.

Main API entry point with all routes configured.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import drives, eligibility, ingestion, students
from api.routes.auth import router as auth_router
from api.routes.timeline import router as timeline_router
from config import settings
from database.connection import init_db

# Create FastAPI app
app = FastAPI(
    title="PlaceGuard API",
    description="Placement eligibility management system with LLM-powered extraction and deterministic rule engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS - allow WhatsApp console and frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8001", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly include OPTIONS
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and start background services on startup."""
    init_db()
    
    # Start Gmail polling service if enabled
    try:
        from ingestion.gmail.polling_service import start_polling_service
        await start_polling_service()
    except Exception as e:
        # Log error but don't prevent app startup
        import logging
        logging.error(f"Failed to start Gmail polling service: {e}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background services on shutdown."""
    try:
        from ingestion.gmail.polling_service import stop_polling_service
        await stop_polling_service()
    except Exception as e:
        import logging
        logging.error(f"Failed to stop Gmail polling service: {e}")


# Health check
@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "PlaceGuard API",
        "version": "1.0.0",
    }


# Include routers
app.include_router(auth_router)
app.include_router(students.router)
app.include_router(drives.router)
app.include_router(eligibility.router)
app.include_router(ingestion.router)
app.include_router(timeline_router)


# Root endpoint
@app.get("/", tags=["system"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "PlaceGuard API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/auth/login",
            "me": "/auth/me",
            "students": "/students",
            "drives": "/drives",
            "eligibility": "/eligibility/check",
            "ingestion": "/ingest/notice",
            "timeline": "/timeline/{drive_id}",
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
