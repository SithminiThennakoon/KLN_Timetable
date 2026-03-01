from pydantic import BaseModel, Field


class TimetableGenerateResponse(BaseModel):
    status: str
    total_scheduled_sessions: int
    unscheduled_sessions: int
    version: str
    diagnostics: list[str] = []
