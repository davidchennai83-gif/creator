from pydantic import BaseModel, ConfigDict, Field
from app.models.content import ContentCategory


class ContentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20000)
    category: ContentCategory = ContentCategory.OTHER
    language: str = Field(default="en", min_length=2, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=30)
