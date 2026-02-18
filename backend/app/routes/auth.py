from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import re
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.core.config import settings
from app.models.admin_login import AdminLogin
from app.models.user import User
from app.models.student_login import StudentLogin
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

def validate_username(username: str) -> bool:
    """Validate username format: **/****/*** where first two are capital letters"""
    pattern = r'^[A-Z]{2}/[A-Z]{4}/[A-Z]{3}$'
    return re.match(pattern, username) is not None

def validate_student_email(email: str) -> bool:
    """Validate student email format: must end with @stuln.ac.lk"""
    return email.endswith('@stuln.ac.lk')

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Validate username format
    if not validate_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username format. Must be in format **/****/*** (e.g., AB/CDEF/GHI)"
        )
    
    # Validate email for students
    if user_data.role == "student" and not validate_student_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student email must end with @stuln.ac.lk"
        )
    
    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        name=user_data.name,
        hashed_password=hashed_password,
        role=user_data.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Login user and return JWT token"""
    identifier = credentials.username.strip()

    # Try login against users table by username or email
    user = db.query(User).filter(User.username == identifier).first()
    if not user:
        user = db.query(User).filter(User.email == identifier).first()

    if user:
        if not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user.role
        }

    # Fallback login against student_login table
    student = db.query(StudentLogin).filter(StudentLogin.studentemail == identifier).first()
    if student and student.password == credentials.password:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": student.studentemail, "user_id": student.stu_id, "role": "student"},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "student"
        }

    # Fallback login against admin_login table
    admin = db.query(AdminLogin).filter(AdminLogin.adminemail == identifier).first()
    if admin and admin.password == credentials.password:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin.adminemail, "user_id": admin.id, "role": "admin"},
            expires_delta=access_token_expires
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": "admin"
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("/me", response_model=UserResponse)
def get_current_user(token: str = None, db: Session = Depends(get_db)):
    """Get current user info (requires token)"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    # Implementation would verify token and get user
    pass
