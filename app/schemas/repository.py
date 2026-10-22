from pydantic import BaseModel, Field, HttpUrl


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    git_url: HttpUrl
    default_branch: str = Field(default="main", max_length=255)