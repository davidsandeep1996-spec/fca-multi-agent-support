"""
FastAPI Application Entry Point

This module initializes the FastAPI application, configures middleware,
registers routers, and sets up CORS policies.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

# Import will be created in later commits
# from app.routers import health
# from app.config import settings
# from app.logger import setup_logging

# Temporary imports for Phase 2
import os
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION FACTORY
# ============================================================================


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application instance.

    Returns:
        FastAPI: Configured application instance
    """

    # Get app configuration
    app_name = os.getenv("APP_NAME", "FCA Multi-Agent Support System")
    app_version = os.getenv("APP_VERSION", "0.1.0")
    environment = os.getenv("ENVIRONMENT", "development")
    debug = os.getenv("DEBUG", False)

    # Create FastAPI instance
    app = FastAPI(
        title=app_name,
        version=app_version,
        description="FCA-compliant multi-agent AI support system for UK financial services",
        docs_url="/docs" if debug else None,  # Disable docs in production
        redoc_url="/redoc" if debug else None,
        openapi_url="/openapi.json" if debug else None,
        # Metadata for OpenAPI schema
        contact={
            "name": "David Sandeep",
            "email": "davidsandeep1996@gmail.com",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )

    # ========================================================================
    # MIDDLEWARE CONFIGURATION
    # ========================================================================

    # CORS Middleware - Allow cross-origin requests
    cors_origins = os.getenv("CORS_ORIGINS", '["http://localhost:3000"]')
    # Parse JSON string (simple version for Phase 2)
    allowed_origins = ["http://localhost:3000", "http://localhost:8000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],  # Allow all HTTP methods
        allow_headers=["*"],  # Allow all headers
    )

    # GZip Middleware - Compress responses
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,  # Only compress responses > 1KB
    )

    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================

    @app.on_event("startup")
    async def startup_event():
        """
        Run on application startup.

        - Initialize logging
        - Connect to database
        - Load configuration
        """
        logger.info(f"Starting {app_name} v{app_version}")
        logger.info(f"Environment: {environment}")
        logger.info("Application startup complete")

    @app.on_event("shutdown")
    async def shutdown_event():
        """
        Run on application shutdown.

        - Close database connections
        - Cleanup resources
        - Log shutdown
        """
        logger.info("Shutting down application")
        logger.info("Application shutdown complete")

    # ========================================================================
    # EXCEPTION HANDLERS
    # ========================================================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """
        Global exception handler for unhandled errors.

        Args:
            request: FastAPI request object
            exc: Exception that was raised

        Returns:
            JSONResponse with error details
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if debug else "An unexpected error occurred",
            },
        )

    # ========================================================================
    # ROUTERS
    # ========================================================================

    # Root endpoint (temporary)
    @app.get("/", tags=["Root"])
    async def root():
        """
        Root endpoint - API information.

        Returns:
            dict: API metadata
        """
        return {
            "name": app_name,
            "version": app_version,
            "status": "operational",
            "docs": "/docs" if debug else "disabled"
        }

    # Health check router will be added in Commit 21
    # app.include_router(health.router, prefix="/api/v1", tags=["Health"])

    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

# Create application instance
app = create_application()

from app.routers import health

app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["Health"],
)


# ============================================================================
# MAIN ENTRY POINT (for direct execution)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Run with uvicorn (development only)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
