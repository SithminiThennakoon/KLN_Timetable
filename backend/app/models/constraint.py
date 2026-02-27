from sqlalchemy import Column, Integer, String, Boolean
from app.core.database import Base

class Constraint(Base):
    __tablename__ = "constraint"

    Constraint_ID = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=False)

    model_config = {"from_attributes": True}
