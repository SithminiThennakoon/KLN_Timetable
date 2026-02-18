from sqlalchemy import Column, Integer, String

from app.core.database import Base


class AdminLogin(Base):
    __tablename__ = "admin_login"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    adminemail = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
