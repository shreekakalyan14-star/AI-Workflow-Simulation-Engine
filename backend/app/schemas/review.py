"""
Structured AI Review Response Schemas.

Strict Pydantic models for validating AI review responses.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class AcceptanceCriterionReview(BaseModel):
    """Review result for a single acceptance criterion."""
    criterion: str = Field(..., min_length=1)
    met: bool
    evidence: str = Field(default="", description="Evidence from submission supporting the decision")


class CodeQualityReview(BaseModel):
    """Code quality assessment."""
    score: int = Field(default=75, ge=0, le=100)
    feedback: str = Field(default="Code quality assessed")


class TestingReview(BaseModel):
    """Testing assessment."""
    score: int = Field(default=75, ge=0, le=100)
    feedback: str = Field(default="Testing assessed")


class SecurityReview(BaseModel):
    """Security assessment."""
    score: int = Field(default=75, ge=0, le=100)
    feedback: str = Field(default="Security assessed")


class PerformanceReview(BaseModel):
    """Performance assessment."""
    score: int = Field(default=75, ge=0, le=100)
    feedback: str = Field(default="Performance assessed")


class AIReviewResponse(BaseModel):
    """
    Complete AI technical review response.
    
    The AI technical review evaluates the submission against requirements.
    It does NOT decide task completion - that's the Manager's role.
    """
    result: str = Field(..., pattern="^(approved|changes_required|rejected)$")
    score: int = Field(..., ge=0, le=100)
    severity: str = Field(default="info", pattern="^(info|warning|error|critical)$")
    summary: str = Field(..., min_length=10, max_length=500)
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    required_changes: List[str] = Field(default_factory=list)
    acceptance_criteria: List[AcceptanceCriterionReview] = Field(default_factory=list)
    code_quality: CodeQualityReview = Field(default_factory=CodeQualityReview)
    testing: TestingReview = Field(default_factory=TestingReview)
    security: SecurityReview = Field(default_factory=SecurityReview)
    performance: PerformanceReview = Field(default_factory=PerformanceReview)

    @field_validator('result')
    @classmethod
    def validate_result(cls, v: str) -> str:
        return v.lower()

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        return v.lower()

    @field_validator('acceptance_criteria')
    @classmethod
    def validate_criteria(cls, v: List[AcceptanceCriterionReview]) -> List[AcceptanceCriterionReview]:
        # Ensure each criterion has meaningful evidence
        for criterion in v:
            if criterion.met and not criterion.evidence.strip():
                raise ValueError("Met criteria must have evidence")
            if not criterion.met and not criterion.evidence.strip():
                raise ValueError("Unmet criteria must have explanation")
        return v


class AIManagerDecision(BaseModel):
    """
    AI Engineering Manager final decision.
    
    The manager reviews the AI technical review and makes the FINAL decision
    on whether to approve or request changes.
    """
    decision: str = Field(..., pattern="^(approved|changes_required)$")
    summary: str = Field(..., min_length=10, max_length=300)
    feedback: str = Field(..., min_length=10, max_length=1000)
    severity: str = Field(default="info", pattern="^(info|warning|error|critical)$")

    @field_validator('decision')
    @classmethod
    def validate_decision(cls, v: str) -> str:
        return v.lower()