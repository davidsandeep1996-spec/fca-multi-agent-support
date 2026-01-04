
"""
Transaction Model
Represents financial transactions on accounts.
"""
from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models import BaseModel

class Transaction(BaseModel):
    __tablename__ = "transactions"

    account_id = Column(ForeignKey("accounts.id"), nullable=False, index=True)
    reference = Column(String(50), unique=True, nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), default="GBP", nullable=False)
    description = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    merchant_name = Column(String(100), nullable=True)

    # Relationships
    account = relationship("Account", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction({self.reference}, amount={self.amount})>"
