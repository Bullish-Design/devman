from pydantic import BaseModel, Field


class ChangelogSummary(BaseModel):
    summary: str = Field(description="A concise, factual changelog summary.")
