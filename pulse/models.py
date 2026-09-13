"""Validated structured outputs for optional language-model calls."""

from pydantic import BaseModel, Field


class SignalOutput(BaseModel):
    category: str
    estimated_severity: int = Field(ge=1, le=5)
    keywords: list[str]
    infrastructure: str
    immediate_attention: bool
    related_categories: list[str]
    confidence: float = Field(ge=0, le=1)


class ResponseOutput(BaseModel):
    hypothesis: str
    potential_impact: str
    inspection: list[str]
    immediate_response: str
    next_steps: list[str]
