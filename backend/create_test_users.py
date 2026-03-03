"""
Script to create test users
"""

import sys
sys.path.insert(0, '/path/to/backend')

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash

db = SessionLocal()

test_users = [
    {
        "email": "admin@kln.edu.lk",
        "name": "Admin User",
        "password": "admin123",
        "role": UserRole.ADMIN
    },
    {
        "email": "head@kln.edu.lk",
        "name": "Department Head",
        "password": "head123",
        "role": UserRole.DEPARTMENT_HEAD
    },
    {
        "email": "lecturer@kln.edu.lk",
        "name": "Dr. Lecturer",
        "password": "lecturer123",
        "role": UserRole.LECTURER
    },
    {
        "email": "student@kln.edu.lk",
        "name": "Student User",
        "password": "student123",
        "role": UserRole.STUDENT
    }
]

for user_data in test_users:
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data["email"]).first()
    
    if not existing_user:
        hashed_password = get_password_hash(user_data["password"])
        new_user = User(
            email=user_data["email"],
            name=user_data["name"],
            hashed_password=hashed_password,
            role=user_data["role"]
        )
        db.add(new_user)
        print(f"Created user: {user_data['email']}")
    else:
        print(f"User already exists: {user_data['email']}")

db.commit()
db.close()
print("Test users created successfully!")
