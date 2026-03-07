from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.core.config import settings
from app.routes import timetable_v2


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

    app.include_router(timetable_v2.router)

    return app


app = create_app()
