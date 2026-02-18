import re

from sqlalchemy import Column, String
from sqlalchemy.orm import validates

from app.core.database import Base


class StudentLogin(Base):
    __tablename__ = "student_login"

    stu_id = Column(String(12), primary_key=True, index=True, nullable=False)
    studentemail = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)

    @validates("stu_id")
    def validate_stu_id(self, key, value):
        pattern = r"^[A-Za-z]{2,3}/\d{4}/\d{3}$"
        if not re.fullmatch(pattern, value):
            raise ValueError("Stu_ID must match format like BS/2023/789")
        return value
