from fastapi import APIRouter

from app.schemas.timetable import TimetableSolveRequest, TimetableSolveResponse
from app.services.timetable_solver import solve_timetable

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


@router.post("/solve", response_model=TimetableSolveResponse)
def solve(request: TimetableSolveRequest):
    return solve_timetable(request)
