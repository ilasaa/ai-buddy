from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccessArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    task_id: int | None = Field(default=None, gt=0)
    resource: Literal["jira", "confluence", "gitlab"]
    project_key: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{1,39}$")
    permission: Literal["read", "write"]
    justification: str = Field(min_length=5, max_length=1000)


class AccessDraftArguments(BaseModel):
    """A tool can ask for missing fields without inventing them."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    task_id: int | None = Field(default=None, gt=0)
    resource: Literal["jira", "confluence", "gitlab"] | None = None
    project_key: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_-]{1,39}$")
    permission: Literal["read", "write"] | None = None
    justification: str | None = Field(default=None, min_length=5, max_length=1000)


class RequestId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: int = Field(gt=0, strict=True)


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    comment: str = Field(default="", max_length=1000)
