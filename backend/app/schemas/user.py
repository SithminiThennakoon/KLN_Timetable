from pydantic import BaseModel, EmailStr
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    DEPARTMENT_HEAD = "department_head"
    LECTURER = "lecturer"
    STUDENT = "student"

class UserBase(BaseModel):
    username: str
    email: EmailStr
    name: str
    role: UserRole = UserRole.STUDENT

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[UserRole] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: str
    updated_at: str

model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str

class LoginRequest(BaseModel):
    username: str
    password: str
