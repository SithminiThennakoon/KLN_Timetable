from pydantic import BaseModel, Field
from typing import Optional


class TimetableGenerateResponse(BaseModel):
    status: str
    total_scheduled_sessions: int
    unscheduled_sessions: int
    version: str
    diagnostics: list[str] = []


class TimetablePreviewResponse(BaseModel):
    status: str
    total_scheduled_sessions: int
    unscheduled_sessions: int
    results: list[list[int]]
    diagnostics: list[str] = []


class TimetableSaveRequest(BaseModel):
    results: list[list[int]]


class TimetableSaveResponse(BaseModel):
    status: str
    version: str
    total_scheduled_sessions: int
    message: str
