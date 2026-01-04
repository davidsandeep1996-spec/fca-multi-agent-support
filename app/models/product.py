"""
Product Model
Represents financial products (Savings, Credit Cards, Loans).
"""
from sqlalchemy import Column, String, Numeric, Text, Boolean, JSON
from app.models import BaseModel

class Product(BaseModel):
    __tablename__ = "products"

    name = Column(String(100), nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True, comment="savings, credit, loan")
    description = Column(Text, nullable=True)
    interest_rate = Column(Numeric(5, 4), nullable=True, comment="Annual interest rate (decimal)")
    features = Column(JSON, default=list, comment="List of product features")
    requirements = Column(JSON, default=dict, comment="Eligibility requirements")
    is_active = Column(Boolean, default=True, index=True)

    def __repr__(self):
        return f"<Product(name='{self.name}', type='{self.type}')>"
