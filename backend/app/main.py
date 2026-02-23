from fastapi import FastAPI

from app.routes import admin, dashboard, timetable


def create_app() -> FastAPI:
    app = FastAPI()

    # include route modules
    app.include_router(admin.router)
    app.include_router(dashboard.router)
    app.include_router(timetable.router)

    return app


app = create_app()
