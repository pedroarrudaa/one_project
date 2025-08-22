"""Profile-related database models for new LinkedIn-based O-1 assessment system."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base
import uuid

Base = declarative_base()


class Profile(Base):
    """Main profile table storing basic profile information from CSV data."""

    __tablename__ = "profiles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_id = Column(String, unique=True, nullable=False)  # From CSV
    name = Column(String, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, nullable=False)
    linkedin_profile = Column(String)  # Discovered or provided
    works_in_ai = Column(String)
    visa_journey_stage = Column(String)
    questions_topics = Column(Text)
    additional_info = Column(Text)
    
    # New fields for LinkedIn-based pipeline
    linkedin_data = Column(JSON)  # Raw LinkedIn data from BrightData
    social_links = Column(JSON)   # All social media links found
    gpt_assessment = Column(JSON) # GPT-4o-mini assessment
    o1_evidence = Column(JSON)    # Structured O-1 evidence
    final_score = Column(Float)   # GPT-generated score
    ranking = Column(Integer)     # Position in ranking
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed

    # Judge suitability (manual + auto-suggestion)
    judge_status = Column(String, default="unknown")  # unknown | candidate | not_candidate
    judge_notes = Column(Text)
    judge_auto_score = Column(Float)  # 0..1 auto-suggest score
    judge_auto_reason = Column(Text)

    # Manual review workflow for outreach
    review_status = Column(String, default="under_review")  # under_review | approved | disapproved
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    __table_args__ = (
        Index("ix_profiles_api_id", "api_id"),
        Index("ix_profiles_final_score", "final_score"),
        Index("ix_profiles_ranking", "ranking"),
    )


class ProcessingLog(Base):
    """Log of processing steps for debugging and monitoring."""
    
    __tablename__ = "processing_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    step = Column(String, nullable=False)  # linkedin_discovery, brightdata_scraping, gpt_assessment
    status = Column(String, nullable=False)  # started, completed, failed
    message = Column(Text)
    data = Column(JSON)  # Step-specific data
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_processing_logs_profile_id", "profile_id"),
        Index("ix_processing_logs_step", "step"),
    )