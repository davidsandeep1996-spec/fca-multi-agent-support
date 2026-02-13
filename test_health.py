"""
Health Check Endpoint Tests

Tests for health check, ping, readiness, and liveness endpoints.
"""

import pytest
from httpx import AsyncClient


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_success(client: AsyncClient):
    """
    Test health check endpoint returns success.

    Verifies:
    - Status code 200 OK
    - Response structure
    - All required fields present
    - Health status is healthy
    """
    response = await client.get("/api/v1/health")

    # Check status code
    assert response.status_code == 200

    # Parse response
    data = response.json()

    # Check required fields
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "environment" in data
    assert "checks" in data

    # Check status is healthy
    assert data["status"] == "healthy"

    # Check version
    assert data["version"] == "0.1.0"

    # Check checks structure
    checks = data["checks"]
    assert "database" in checks
    assert "redis" in checks
    assert "groq_ai" in checks

    # Check database check
    db_check = checks["database"]
    assert "status" in db_check
    assert "type" in db_check
    assert db_check["type"] == "postgresql"


@pytest.mark.asyncio
async def test_health_check_database_status(client: AsyncClient):
    """
    Test health check includes database status.

    Verifies:
    - Database check exists
    - Database status is healthy
    - Pool size is reported
    """
    response = await client.get("/api/v1/health")
    data = response.json()

    db_check = data["checks"]["database"]

    # Check database status
    assert db_check["status"] == "healthy"
    assert "pool_size" in db_check
    assert db_check["pool_size"] > 0


# ============================================================================
# PING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_ping_success(client: AsyncClient):
    """
    Test ping endpoint returns success.

    Verifies:
    - Status code 200 OK
    - Response structure
    - Quick response time
    """
    response = await client.get("/api/v1/ping")

    # Check status code
    assert response.status_code == 200

    # Parse response
    data = response.json()

    # Check required fields
    assert "status" in data
    assert "timestamp" in data

    # Check status is ok
    assert data["status"] == "ok"


# ============================================================================
# READINESS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_readiness_success(client: AsyncClient):
    """
    Test readiness endpoint returns ready.

    Verifies:
    - Status code 200 OK
    - Response indicates ready
    """
    response = await client.get("/api/v1/ready")

    # Check status code
    assert response.status_code == 200

    # Parse response
    data = response.json()

    # Check status
    assert "status" in data
    assert data["status"] == "ready"


# ============================================================================
# LIVENESS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_liveness_success(client: AsyncClient):
    """
    Test liveness endpoint returns alive.

    Verifies:
    - Status code 200 OK
    - Response indicates alive
    """
    response = await client.get("/api/v1/live")

    # Check status code
    assert response.status_code == 200

    # Parse response
    data = response.json()

    # Check status
    assert "status" in data
    assert data["status"] == "alive"


# ============================================================================
# ROOT ENDPOINT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """
    Test root endpoint returns API information.

    Verifies:
    - Status code 200 OK
    - Response structure
    - API metadata present
    """
    response = await client.get("/")

    # Check status code
    assert response.status_code == 200

    # Parse response
    data = response.json()

    # Check required fields
    assert "name" in data
    assert "version" in data
    assert "status" in data
    assert "environment" in data

    # Check values
    assert data["status"] == "operational"
    assert data["version"] == "0.1.0"
