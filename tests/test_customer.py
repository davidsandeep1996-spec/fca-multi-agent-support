"""
Customer Tests

Tests for Customer model and CustomerService.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.customer import CustomerService
from app.models.customer import Customer


# ============================================================================
# CREATE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_create_customer(db_session: AsyncSession):
    """Test creating a customer."""
    service = CustomerService(db=db_session)

    customer = await service.create_customer(
        customer_id="CUST-003",
        first_name="John",
        last_name="Smith",
        email="john4@example.com",
        phone="+44123456789"
    )

    assert customer.id is not None
    assert customer.customer_id == "CUST-003"
    assert customer.first_name == "John"
    assert customer.last_name == "Smith"
    assert customer.email == "john4@example.com"
    assert customer.phone == "+44123456789"
    assert customer.is_active is True
    assert customer.is_verified is False
    assert customer.is_vip is False


@pytest.mark.asyncio
async def test_create_customer_duplicate_email(db_session: AsyncSession):
    """Test creating customer with duplicate email raises error."""
    service = CustomerService(db=db_session)

    # Create first customer
    await service.create_customer(
        customer_id="CUST-003",
        first_name="John",
        last_name="Smith",
        email="john4@example.com"
    )

    # Try to create second customer with same email
    with pytest.raises(ValueError, match="already exists"):
        await service.create_customer(
            customer_id="CUST-003",
            first_name="Jane",
            last_name="Doe",
            email="john4@example.com"
        )


# ============================================================================
# READ TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_customer(db_session: AsyncSession):
    """Test getting customer by ID."""
    service = CustomerService(db=db_session)

    # Create customer
    created = await service.create_customer(
        customer_id="CUST-006",
        first_name="John",
        last_name="Smith",
        email="john6@example.com"
    )

    # Get customer
    customer = await service.get_customer(created.id)

    assert customer is not None
    assert customer.id == created.id
    assert customer.email == "john6@example.com"


@pytest.mark.asyncio
async def test_get_customer_by_email(db_session: AsyncSession):
    """Test getting customer by email."""
    service = CustomerService(db=db_session)

    # Create customer
    await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    # Get by email
    customer = await service.get_customer_by_email("john@example.com")

    assert customer is not None
    assert customer.email == "john@example.com"


@pytest.mark.asyncio
async def test_search_customers(db_session: AsyncSession):
    """Test searching customers by name."""
    service = CustomerService(db=db_session)

    # Create customers
    await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    await service.create_customer(
        customer_id="CUST-002",
        first_name="Jane",
        last_name="Johnson",
        email="jane@example.com"
    )

    # Search for "john"
    results = await service.search_customers("john")

    assert len(results) == 2  # Matches "John" and "Johnson"
    assert any(c.first_name == "John" for c in results)
    assert any(c.last_name == "Johnson" for c in results)


# ============================================================================
# UPDATE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_update_customer(db_session: AsyncSession):
    """Test updating customer."""
    service = CustomerService(db=db_session)

    # Create customer
    customer = await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    # Update customer
    updated = await service.update_customer(
        customer.id,
        {"first_name": "Jane", "phone": "+44123456789"}
    )

    assert updated is not None
    assert updated.first_name == "Jane"
    assert updated.phone == "+44123456789"
    assert updated.last_name == "Smith"  # Unchanged


@pytest.mark.asyncio
async def test_verify_customer(db_session: AsyncSession):
    """Test verifying customer."""
    service = CustomerService(db=db_session)

    # Create customer
    customer = await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    assert customer.is_verified is False

    # Verify customer
    verified = await service.verify_customer(customer.id)

    assert verified is not None
    assert verified.is_verified is True


@pytest.mark.asyncio
async def test_make_vip(db_session: AsyncSession):
    """Test making customer VIP."""
    service = CustomerService(db=db_session)

    # Create customer
    customer = await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    assert customer.is_vip is False

    # Make VIP
    vip = await service.make_vip(customer.id)

    assert vip is not None
    assert vip.is_vip is True


# ============================================================================
# DELETE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_delete_customer(db_session: AsyncSession):
    """Test deleting customer."""
    service = CustomerService(db=db_session)

    # Create customer
    customer = await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    customer_id = customer.id

    # Delete customer
    success = await service.delete_customer(customer_id)

    assert success is True

    # Verify deleted
    deleted = await service.get_customer(customer_id)
    assert deleted is None


# ============================================================================
# PROPERTY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_customer_full_name(db_session: AsyncSession):
    """Test customer full_name property."""
    service = CustomerService(db=db_session)

    customer = await service.create_customer(
        customer_id="CUST-001",
        first_name="John",
        last_name="Smith",
        email="john@example.com"
    )

    assert customer.full_name == "John Smith"
