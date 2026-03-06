from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine, SessionLocal
from app.core.config import settings
from app.seed_timeslots import seed_timeslots
from app.routes import (
    departments,
    subjects,
    pathways,
    modules,
    sessions,
    sessions_unscheduled,
    sessions_expanded,
    lecturers_new,
    rooms,
    timeslots,
    timetable_entries,
    data_status,
    timetable_generate,
    timetable_validate,
    timetable_resolve,
    timetable_v2,
)


def create_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.RESET_DB:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_timeslots(db)

    app.include_router(departments.router)
    app.include_router(subjects.router)
    app.include_router(pathways.router)
    app.include_router(modules.router)
    app.include_router(sessions.router)
    app.include_router(sessions_unscheduled.router)
    app.include_router(sessions_expanded.router)
    app.include_router(lecturers_new.router)
    app.include_router(rooms.router)
    app.include_router(timeslots.router)
    app.include_router(timetable_entries.router)
    app.include_router(data_status.router)
    app.include_router(timetable_generate.router)
    app.include_router(timetable_validate.router)
    app.include_router(timetable_resolve.router)
    app.include_router(timetable_v2.router)

    return app


app = create_app()
