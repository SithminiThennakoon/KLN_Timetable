from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("/", response_model=list[RoomRead])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).order_by(Room.id).all()


@router.post("/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)):
    existing = db.query(Room).filter(Room.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Room name already exists")
    room = Room(
        name=payload.name,
        capacity=payload.capacity,
        room_type=payload.room_type,
        lab_type=payload.lab_type,
        location=payload.location,
        year_restriction=payload.year_restriction,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.put("/{room_id}", response_model=RoomRead)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if payload.name is not None:
        existing = db.query(Room).filter(Room.name == payload.name, Room.id != room_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Room name already exists")
        room.name = payload.name
    if payload.capacity is not None:
        room.capacity = payload.capacity
    if payload.room_type is not None:
        room.room_type = payload.room_type
    if payload.lab_type is not None or payload.lab_type is None:
        room.lab_type = payload.lab_type
    if payload.location is not None:
        room.location = payload.location
    if payload.year_restriction is not None or payload.year_restriction is None:
        room.year_restriction = payload.year_restriction
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return {"message": "Room deleted"}
