from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.module import Module
from app.models.subject import Subject
from app.schemas.module import ModuleCreate, ModuleRead, ModuleUpdate

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("/", response_model=list[ModuleRead])
def list_modules(db: Session = Depends(get_db)):
    return db.query(Module).order_by(Module.id).all()


@router.post("/", response_model=ModuleRead, status_code=status.HTTP_201_CREATED)
def create_module(payload: ModuleCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
    if not subject:
        raise HTTPException(status_code=400, detail="Subject not found")
    existing = db.query(Module).filter(Module.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Module code already exists")
    module = Module(
        code=payload.code,
        name=payload.name,
        subject_id=payload.subject_id,
        year=payload.year,
        semester=payload.semester,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


@router.put("/{module_id}", response_model=ModuleRead)
def update_module(module_id: int, payload: ModuleUpdate, db: Session = Depends(get_db)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    if payload.subject_id is not None:
        subject = db.query(Subject).filter(Subject.id == payload.subject_id).first()
        if not subject:
            raise HTTPException(status_code=400, detail="Subject not found")
        module.subject_id = payload.subject_id
    if payload.code is not None:
        existing = db.query(Module).filter(Module.code == payload.code, Module.id != module_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Module code already exists")
        module.code = payload.code
    if payload.name is not None:
        module.name = payload.name
    if payload.year is not None:
        module.year = payload.year
    if payload.semester is not None:
        module.semester = payload.semester
    db.commit()
    db.refresh(module)
    return module


@router.delete("/{module_id}")
def delete_module(module_id: int, db: Session = Depends(get_db)):
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    db.delete(module)
    db.commit()
    return {"message": "Module deleted"}
