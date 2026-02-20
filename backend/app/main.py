from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.models.admin_login import AdminLogin
from app.models.student_login import StudentLogin
from app.routes.auth import router as auth_router
from app.routes.timetable import router as timetable_router
from app.routes.dashboard import router as dashboard_router
from app.core.config import settings

# Create tables (temporarily commented out due to database connection issues)
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(timetable_router)
app.include_router(dashboard_router)

@app.get("/")
def read_root():
    return {"message": "KLN Timetable API"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
