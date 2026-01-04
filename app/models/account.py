"""
Account Model
Represents a customer's bank account.
"""
from sqlalchemy import Column, String, Numeric, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
import enum
from app.models import BaseModel

class AccountType(str, enum.Enum):
    CURRENT = "current"
    SAVINGS = "savings"
    LOAN = "loan"
    CREDIT = "credit"

class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

class Account(BaseModel):
    __tablename__ = "accounts"

    account_number = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(String(50), nullable=False, index=True, comment="External Link")
    product_id = Column(ForeignKey("products.id"), nullable=True)

    type = Column(SAEnum(AccountType), nullable=False, default=AccountType.CURRENT)
    status = Column(SAEnum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE)
    currency = Column(String(3), default="GBP", nullable=False)
    balance = Column(Numeric(15, 2), default=0.00, nullable=False)
    available_balance = Column(Numeric(15, 2), default=0.00, nullable=False)

    # Relationships
    product = relationship("Product")
    # Using string reference to avoid circular imports
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account({self.account_number}, type={self.type}, balance={self.balance})>"
