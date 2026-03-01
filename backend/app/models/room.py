from sqlalchemy import Column, Integer, String
from app.core.database import Base


class Room(Base):
    __tablename__ = "room"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String(30), nullable=False)
    lab_type = Column(String(50), nullable=True)
    location = Column(String(100), nullable=False)
    year_restriction = Column(Integer, nullable=True)
