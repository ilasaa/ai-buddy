from pydantic import BaseModel, ConfigDict


class TeamResponse(BaseModel):
    id: int
    name: str
    description: str | None
    leader_id: int | None

    model_config = ConfigDict(from_attributes=True)