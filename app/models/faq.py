"""
FAQ Model
"""
from sqlalchemy import Column, Integer, String, Boolean, Text
from app.database import Base

class FAQ(Base):
    __tablename__ = "faqs"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, index=True, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String, index=True)  # e.g., 'security', 'account'
    keywords = Column(String)  # Comma-separated for simple search
    is_active = Column(Boolean, default=True)
