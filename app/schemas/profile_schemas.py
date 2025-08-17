"""Pydantic schemas for LinkedIn-based O-1 Assessment API operations."""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    """Schema for creating a new profile from CSV data."""
    
    api_id: str = Field(..., description="Unique API ID from the event system")
    name: str = Field(..., description="Full name of the person")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    email: str = Field(..., description="Email address")
    linkedin_profile: Optional[str] = Field(None, description="LinkedIn profile URL")
    works_in_ai: Optional[str] = Field(None, description="Whether they work/operate in AI")
    visa_journey_stage: Optional[str] = Field(None, description="Current stage in O-1/EB-1 application journey")
    questions_topics: Optional[str] = Field(None, description="Questions/topics they want addressed")
    additional_info: Optional[str] = Field(None, description="Any additional information provided")


class ProfileResponse(BaseModel):
    """Schema for profile response."""
    
    id: str
    api_id: str
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: str
    linkedin_profile: Optional[str]
    works_in_ai: Optional[str]
    visa_journey_stage: Optional[str]
    questions_topics: Optional[str]
    additional_info: Optional[str]
    
    # New fields for LinkedIn-based pipeline
    social_links: Optional[Dict[str, str]] = Field(None, description="All social media links")
    final_score: Optional[float] = Field(None, description="GPT-generated O-1 score")
    ranking: Optional[int] = Field(None, description="Position in ranking")
    processing_status: str = Field(default="pending", description="Processing status")
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LinkedInDataResponse(BaseModel):
    """Schema for LinkedIn profile data."""
    
    basic_info: Dict[str, Any] = Field(default_factory=dict)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    accomplishments: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)


class GPTAssessmentResponse(BaseModel):
    """Schema for GPT assessment results."""
    
    overall_score: float = Field(..., description="Overall O-1 score (1-10)")
    criteria_scores: Dict[str, float] = Field(..., description="Individual criteria scores")
    evidence: Dict[str, List[str]] = Field(..., description="Evidence for each criterion")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    likelihood: str = Field(..., description="High/Medium/Low")
    recommendation: str = Field(..., description="Detailed recommendation")
    reasoning: str = Field(..., description="Assessment reasoning")


class RankingEntry(BaseModel):
    """Single entry in the rankings table."""
    
    rank: int
    full_name: str
    seniority_level: Optional[str] = Field(None, description="Professional seniority: Junior/Senior/Executive/VP")
    current_title: Optional[str] = Field(None, description="Current job title")
    social_influence: Optional[str] = Field(None, description="Social influence level and reach")
    follower_counts: Optional[Dict[str, int]] = Field(default_factory=dict, description="Follower counts by platform")
    social_links: Dict[str, str] = Field(default_factory=dict)
    email: str
    evidence: Dict[str, List[str]] = Field(default_factory=dict)
    score: float
    likelihood: str
    recommendation: str
    processing_status: str


class RankingResponse(BaseModel):
    """Schema for the complete ranking response."""
    
    rankings: List[RankingEntry]
    total: int
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)


class ProcessingLogEntry(BaseModel):
    """Schema for processing log entries."""
    
    step: str
    status: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class ProcessingLogsResponse(BaseModel):
    """Schema for processing logs response."""
    
    profile_id: str
    logs: List[ProcessingLogEntry]


class BatchProfileRequest(BaseModel):
    """Schema for batch profile creation."""
    
    profiles: List[ProfileCreate] = Field(..., description="List of profiles to create")


class ProcessingStatsResponse(BaseModel):
    """Schema for system processing statistics."""
    
    total_profiles: int
    pending: int
    processing: int
    completed: int
    failed: int
    completion_rate: float


class BatchProcessingRequest(BaseModel):
    """Schema for batch processing request."""
    
    profile_ids: Optional[List[str]] = Field(None, description="Specific profile IDs to process")
    max_concurrent: Optional[int] = Field(None, description="Maximum concurrent processes")


class BatchProcessingResponse(BaseModel):
    """Schema for batch processing response."""
    
    total_processed: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]