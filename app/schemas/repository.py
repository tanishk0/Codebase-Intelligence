from pydantic import BaseModel, Field, HttpUrl

from datetime import datetime

class RepositoryResponse(BaseModel):
    id: int
    name: str
    git_url: str
    default_branch: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}