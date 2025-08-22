"""Main FastAPI application for LinkedIn-based O-1 Visa Assessment System."""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import List, Dict, Any
import asyncio
import logging
import json

from config import settings
from app.database import get_db, init_db, SessionLocal
from app.schemas import (
    ProfileResponse,
    BatchProfileRequest,
    GPTAssessmentResponse,
    RankingResponse,
    RankingEntry,
    # for judge endpoints
    ProcessingLogsResponse,
    ProcessingStatsResponse,
    BatchProcessingRequest,
    BatchProcessingResponse,
)
from app.models import Profile, ProcessingLog
from app.services.profile_processor import ProfileProcessor

from pathlib import Path

# Initialize FastAPI app
app = FastAPI(
    title="LinkedIn-based O-1 Visa Assessment System",
    description=(
        "AI-powered system for analyzing LinkedIn profiles and ranking them "
        "for O-1 visa compatibility using GPT-4o-mini intelligent assessment"
    ),
    version="2.0.0",
)

# Initialize services
profile_processor = ProfileProcessor()

# Static files (dashboard)
@app.get("/dashboard")
def serve_dashboard():
    """Serve the main dashboard HTML file."""
    dashboard_path = Path("app/static/dashboard.html")
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.post("/profiles/upload-csv", response_model=List[ProfileResponse])
async def upload_csv_profiles(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process profiles from CSV file."""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Parse CSV and create profiles
        from app.utils.csv_processor import CSVProcessor
        csv_processor = CSVProcessor()
        profiles_data = csv_processor.parse_csv_content(csv_content)
        
        created_profiles = []
        for profile_data in profiles_data:
            # Create profile in database
            db_profile = Profile(**profile_data)
            db.add(db_profile)
            db.commit()
            db.refresh(db_profile)
            created_profiles.append(db_profile)
        
        return [ProfileResponse.model_validate(profile) for profile in created_profiles]
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")


@app.post("/profiles/{profile_id}/process")
async def process_profile(profile_id: str, db: Session = Depends(get_db)):
    """Process a single profile through the complete LinkedIn-based pipeline."""
    try:
        # Check if profile exists
        profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Process profile
        result = await profile_processor.process_profile(profile_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles/process-batch", response_model=BatchProcessingResponse)
async def process_batch_profiles(
    request: BatchProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Process multiple profiles in batch."""
    try:
        profile_ids = request.profile_ids
        
        # Validate all profiles exist
        profiles = db.query(Profile).filter(Profile.id.in_(profile_ids)).all()
        if len(profiles) != len(profile_ids):
            raise HTTPException(status_code=404, detail="Some profiles not found")
        
        # Process in background
        async def batch_process():
            results = []
            for profile_id in profile_ids:
                try:
                    result = await profile_processor.process_profile(profile_id)
                    results.append({"profile_id": profile_id, "status": "completed", "result": result})
                except Exception as e:
                    results.append({"profile_id": profile_id, "status": "failed", "error": str(e)})
            return results
        
        background_tasks.add_task(batch_process)
        
        return BatchProcessingResponse(
            message=f"Started processing {len(profile_ids)} profiles",
            profile_ids=profile_ids,
            status="started"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profiles/{profile_id}/assessment")
def get_profile_assessment(profile_id: str, db: Session = Depends(get_db)):
    """Get GPT assessment results for a profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if not profile.gpt_assessment:
        raise HTTPException(status_code=404, detail="Assessment not available")
    
    return {
        "profile_id": profile.id,
        "name": profile.name,
        "processing_status": profile.processing_status,
        "linkedin_profile": profile.linkedin_profile,
        "social_links": profile.social_links,
        "gpt_assessment": profile.gpt_assessment,
        "o1_evidence": profile.o1_evidence,
        "final_score": profile.final_score,
        "ranking": profile.ranking,
        "updated_at": profile.updated_at
    }


@app.get("/profiles/{profile_id}/processing-logs", response_model=ProcessingLogsResponse)
def get_processing_logs(profile_id: str, db: Session = Depends(get_db)):
    """Get processing logs for a profile."""
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    logs = db.query(ProcessingLog).filter(
        ProcessingLog.profile_id == profile_id
    ).order_by(ProcessingLog.timestamp.desc()).all()
    
    return ProcessingLogsResponse(
        profile_id=profile_id,
        logs=[{
            "step": log.step,
            "status": log.status,
            "message": log.message,
            "data": log.data,
            "timestamp": log.timestamp
        } for log in logs]
    )


@app.get("/rankings", response_model=RankingResponse)
def get_rankings(limit: int = 500, db: Session = Depends(get_db)):
    """Get ranked profiles based on O-1 assessment scores."""
    profiles = db.query(Profile).filter(
        Profile.final_score.isnot(None),
        Profile.processing_status == "completed"
    ).order_by(Profile.final_score.desc()).limit(limit).all()
    
    rankings = []
    for rank, profile in enumerate(profiles, 1):
        # Get likelihood from GPT assessment
        likelihood = "Unknown"
        if profile.gpt_assessment and "likelihood" in profile.gpt_assessment:
            likelihood = profile.gpt_assessment["likelihood"]
        
        # Get recommendation from GPT assessment
        recommendation = ""
        if profile.gpt_assessment and "recommendation" in profile.gpt_assessment:
            recommendation = profile.gpt_assessment["recommendation"]
        
        # Extract seniority, social influence, and GitHub info from data
        seniority_level = None
        current_title = None
        social_influence = None
        github_impact = None
        follower_counts = {}
        github_metrics = {}
        
        if profile.linkedin_data:
            basic_info = profile.linkedin_data.get("basic_info", {})
            current_title = basic_info.get("headline", "")
            
            # Use GPT service to classify seniority and social influence
            from app.services.scoring_v1 import GPTScoringService
            gpt_service = GPTScoringService()
            seniority_level, _, _ = gpt_service.classify_seniority_level(current_title, basic_info.get("current_company", ""))
            
            # Analyze social influence
            influence_score, influence_analysis, follower_breakdown = gpt_service.analyze_social_influence(profile.linkedin_data)
            social_influence = influence_analysis
            follower_counts = follower_breakdown
            
            # Extract GitHub data if available
            github_data = profile.linkedin_data.get("github_data")
            if github_data:
                github_impact = github_data.get("analysis_summary", "GitHub data available")
                github_metrics = github_data.get("metrics", {})
        
        rankings.append(RankingEntry(
            id=profile.id,
            rank=rank,
            full_name=profile.name,
            seniority_level=seniority_level,
            current_title=current_title,
            social_influence=social_influence,
            github_impact=github_impact,
            follower_counts=follower_counts,
            github_metrics=github_metrics,
            social_links=profile.social_links or {},
            email=profile.email,
            evidence=profile.o1_evidence or {},
            score=profile.final_score,
            likelihood=likelihood,
            recommendation=recommendation,
            processing_status=profile.processing_status,
            judge_status=profile.judge_status,
            judge_auto_score=profile.judge_auto_score
        ))
    
    return RankingResponse(
        rankings=rankings,
        total=len(rankings),
        analysis_metadata={
            "total_profiles": len(rankings),
            "last_updated": profiles[0].updated_at.isoformat() if profiles else None
        }
    )


# Judge endpoints
@app.get("/profiles/{profile_id}/judge")
def get_judge_status(profile_id: str, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "profile_id": profile.id,
        "judge_status": profile.judge_status,
        "judge_notes": profile.judge_notes,
        "judge_auto_score": profile.judge_auto_score,
        "judge_auto_reason": profile.judge_auto_reason,
    }


@app.patch("/profiles/{profile_id}/judge")
def set_judge_status(profile_id: str, payload: dict, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    status = payload.get("judge_status")
    notes = payload.get("judge_notes")
    if status not in [None, "unknown", "candidate", "not_candidate"]:
        raise HTTPException(status_code=400, detail="Invalid judge_status")
    if status is not None:
        profile.judge_status = status
    if notes is not None:
        profile.judge_notes = notes
    db.commit()
    return {"ok": True}


@app.get("/stats", response_model=ProcessingStatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    """Get system processing statistics."""
    total_profiles = db.query(func.count(Profile.id)).scalar()
    
    # Count by processing status
    pending = db.query(func.count(Profile.id)).filter(
        Profile.processing_status == "pending"
    ).scalar()
    
    processing = db.query(func.count(Profile.id)).filter(
        Profile.processing_status == "processing"
    ).scalar()
    
    completed = db.query(func.count(Profile.id)).filter(
        Profile.processing_status == "completed"
    ).scalar()
    
    failed = db.query(func.count(Profile.id)).filter(
        Profile.processing_status == "failed"
    ).scalar()
    
    completion_rate = (completed / total_profiles * 100) if total_profiles > 0 else 0
    
    return ProcessingStatsResponse(
        total_profiles=total_profiles,
        pending=pending,
        processing=processing,
        completed=completed,
        failed=failed,
        completion_rate=completion_rate
    )


@app.post("/judge/recompute")
def recompute_judge_for_completed(db: Session = Depends(get_db)):
    """Recompute judge auto-score for all completed profiles."""
    try:
        gpt_service = GPTScoringService()
        updated = 0
        profiles = db.query(Profile).filter(Profile.processing_status == "completed").all()
        for p in profiles:
            linkedin_data = p.linkedin_data or {}
            assessment = p.gpt_assessment or {}
            # reuse processor heuristic without instantiating the full processor
            from app.services.profile_processor import ProfileProcessor
            proc = ProfileProcessor()
            auto_score, auto_reason = proc._compute_judge_auto_suggestion(linkedin_data, assessment)
            p.judge_auto_score = auto_score
            p.judge_auto_reason = auto_reason
            if not p.judge_status or p.judge_status == "unknown":
                p.judge_status = "candidate" if (auto_score is not None and auto_score >= 0.6) else p.judge_status
            updated += 1
        db.commit()
        return {"updated": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/healthz")
def healthz():
    """Health check endpoint."""
    db_ok = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    finally:
        try:
            db.close()
        except Exception:
            pass
    
    return {
        "status": "ok",
        "database": "ok" if db_ok else "error",
        "has_openai_key": bool(settings.openai_api_key),
        "has_tavily_key": bool(settings.tavily_api_key),
        "has_brightdata_key": bool(settings.brightdata_api_key),
        "brightdata_timeout": settings.brightdata_timeout,
    }


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)