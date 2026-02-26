from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import admin, dashboard, timetable

def create_app() -> FastAPI:
    app = FastAPI()

    # add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # include route modules
    app.include_router(admin.router)
    app.include_router(dashboard.router)
    app.include_router(timetable.router)
    from app.routes import constraints
    app.include_router(constraints.router)
    from app.routes import courses
    app.include_router(courses.router)
    from app.routes import lecturers
    app.include_router(lecturers.router)

    return app

app = create_app()
