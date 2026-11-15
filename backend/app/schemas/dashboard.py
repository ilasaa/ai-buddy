from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["intern", "mentor"]
Status = Literal["todo", "in_progress", "done", "submitted", "changes_requested", "blocked"]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class TeamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None


class MentorSummary(BaseModel):
    id: int
    full_name: str
    role: Role
    team: TeamSummary


class Profile(BaseModel):
    id: int
    full_name: str
    email: str
    role: Role
    team: TeamSummary
    mentor: MentorSummary | None
    internship_started_at: date | None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_resource: str | None = None
    quiz_id: int | None = None
    goal_id: int | None = None
    verification_type: str = "self"
    evidence: str | None = None
    review_comment: str | None = None
    title: str
    description: str | None
    status: Status
    due_date: date | None
    completed_at: datetime | None
    created_at: datetime


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


class OnboardingResponse(BaseModel):
    tasks: list[TaskResponse]
    completed: int
    total: int
    percent: int
