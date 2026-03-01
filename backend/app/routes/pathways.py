from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.pathway import Pathway
from app.models.subject import Subject
from app.schemas.pathway import PathwayCreate, PathwayRead, PathwayUpdate

router = APIRouter(prefix="/api/pathways", tags=["pathways"])


def _pathway_to_read(pathway: Pathway) -> PathwayRead:
    subject_ids = [subject.id for subject in pathway.subjects]
    return PathwayRead(
        id=pathway.id,
        name=pathway.name,
        department_id=pathway.department_id,
        year=pathway.year,
        subject_ids=subject_ids,
    )


@router.get("/", response_model=list[PathwayRead])
def list_pathways(db: Session = Depends(get_db)):
    pathways = db.query(Pathway).order_by(Pathway.id).all()
    return [_pathway_to_read(pathway) for pathway in pathways]


@router.post("/", response_model=PathwayRead, status_code=status.HTTP_201_CREATED)
def create_pathway(payload: PathwayCreate, db: Session = Depends(get_db)):
    pathway = Pathway(
        name=payload.name,
        department_id=payload.department_id,
        year=payload.year,
    )
    if payload.subject_ids:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
        if len(subjects) != len(set(payload.subject_ids)):
            raise HTTPException(status_code=400, detail="One or more subjects not found")
        pathway.subjects = subjects
    db.add(pathway)
    db.commit()
    db.refresh(pathway)
    return _pathway_to_read(pathway)


@router.put("/{pathway_id}", response_model=PathwayRead)
def update_pathway(pathway_id: int, payload: PathwayUpdate, db: Session = Depends(get_db)):
    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")
    if payload.name is not None:
        pathway.name = payload.name
    if payload.department_id is not None:
        pathway.department_id = payload.department_id
    if payload.year is not None:
        pathway.year = payload.year
    if payload.subject_ids is not None:
        subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all()
        if len(subjects) != len(set(payload.subject_ids)):
            raise HTTPException(status_code=400, detail="One or more subjects not found")
        pathway.subjects = subjects
    db.commit()
    db.refresh(pathway)
    return _pathway_to_read(pathway)


@router.delete("/{pathway_id}")
def delete_pathway(pathway_id: int, db: Session = Depends(get_db)):
    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")
    db.delete(pathway)
    db.commit()
    return {"message": "Pathway deleted"}
