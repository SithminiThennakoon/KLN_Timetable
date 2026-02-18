"""
Database initialization script
Run this to create the initial database and tables
"""

import sys
sys.path.insert(0, '/path/to/backend')

from app.core.database import Base, engine
from app.models.user import User
from app.models.student_login import StudentLogin

# Create all tables
Base.metadata.create_all(bind=engine)

print("Database tables created successfully!")
print("Tables created:")
print("  - users")
print("  - student_login")
