from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlanInput(Input):
    title: str = Field(min_length=3, max_length=250)
    expectations: str = Field(min_length=3, max_length=10000)
    start_date: date
    target_date: date
    version: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def dates(self):
        if self.target_date < self.start_date:
            raise ValueError("Срок плана раньше начала")
        return self


class GoalInput(Input):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(default="", max_length=5000)
    success_criteria: str = Field(min_length=3, max_length=5000)
    target_date: date
    version: int = Field(gt=0)


class TaskInput(Input):
    title: str = Field(min_length=3, max_length=250)
    description: str = Field(default="", max_length=5000)
    goal_id: int = Field(gt=0)
    due_date: date
    request_resource: Literal["jira", "confluence", "gitlab"] | None = None
    quiz_id: int | None = Field(default=None, gt=0)
    verification_type: Literal["self", "review", "quiz", "request"] = "self"
    version: int = Field(gt=0)


class AgreementInput(Input):
    action: Literal["send", "agree", "comment", "revise"]
    version: int = Field(gt=0)
    comment: str = Field(default="", max_length=5000)


class VerificationInput(Input):
    action: Literal["submit", "approve", "reject"]
    evidence: str = Field(default="", max_length=10000)
    comment: str = Field(default="", max_length=5000)


class ObjectiveInput(Input):
    title: str = Field(min_length=3, max_length=250)
    key_results: list[str] = Field(min_length=1, max_length=10)
    period_start: date
    period_end: date
