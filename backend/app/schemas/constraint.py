from pydantic import BaseModel
from typing import Optional

class ConstraintBase(BaseModel):
    name: str
    description: Optional[str] = None

class ConstraintRead(ConstraintBase):
    Constraint_ID: int
    enabled: bool

    class Config:
        from_attributes = True

class ConstraintUpdate(BaseModel):
    enabled: bool
