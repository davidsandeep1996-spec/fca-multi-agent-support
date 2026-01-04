"""
FastAPI Application Entry Point

This module initializes the FastAPI application, configures middleware,
registers routers, and sets up CORS policies.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

# Import configuration and utilities
from app.config import settings
from app.logger import setup_logging
from app.database import init_db, close_db
from app.api.routes.messages import router as messages_router

# Import routers
from app.routers import health

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan (startup and shutdown).

    Startup:
    - Initialize logging
    - Initialize database tables (development only)
    - Log startup information

    Shutdown:
    - Close database connections
    - Cleanup resources
    - Log shutdown
    """
    # ========== STARTUP ==========
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database (development only)
    if settings.is_development:
        logger.info("Initializing database tables (development mode)")
        try:
            await init_db()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)

    logger.info("Application startup complete")

    yield  # Application runs here

    # ========== SHUTDOWN ==========
    logger.info("Shutting down application")

    # Close database connections
    try:
        await close_db()
    except Exception as e:
        logger.error(f"Error closing database: {e}", exc_info=True)

    logger.info("Application shutdown complete")


# ============================================================================
# APPLICATION FACTORY
# ============================================================================


def create_application() -> FastAPI:
    """
    Create and configure FastAPI application instance.

    Returns:
        FastAPI: Configured application instance
    """

    # Create FastAPI instance
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FCA-compliant multi-agent AI support system for UK financial services",
        docs_url="/docs" if settings.debug else None,  # Disable docs in production
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
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
                "message": str(exc) if settings.debug else "An unexpected error occurred",
            },
        )

    # ========================================================================
    # ROUTERS
    # ========================================================================

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """
        Root endpoint - API information.

        Returns:
            dict: API metadata
        """
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "operational",
            "environment": settings.environment,
            "docs": "/docs" if settings.debug else "disabled",
        }

    # Register routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["Health"],
    )

    app.include_router(messages_router)


    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

# Create application instance
app = create_application()


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
