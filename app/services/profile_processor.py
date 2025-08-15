"""Main Profile Processing Orchestrator for LinkedIn-based O-1 Assessment."""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.profile import Profile, ProcessingLog
from app.services.linkedin_discovery_service import LinkedInDiscoveryService
from app.services.brightdata_service import BrightDataService
from app.services.gpt_scoring_service import GPTScoringService
from config import settings

logger = logging.getLogger(__name__)


class ProfileProcessor:
    """Main orchestrator for the LinkedIn-based O-1 assessment pipeline."""
    
    def __init__(self):
        self.linkedin_discovery = LinkedInDiscoveryService()
        self.brightdata = BrightDataService()
        self.gpt_scoring = GPTScoringService()
    
    async def process_profile(self, profile_id: str) -> Dict[str, Any]:
        """
        Process a single profile through the complete pipeline.
        
        Args:
            profile_id: Profile ID to process
            
        Returns:
            Dictionary containing processing results
        """
        db = SessionLocal()
        try:
            # Get profile from database
            profile = db.query(Profile).filter(Profile.id == profile_id).first()
            if not profile:
                return {"error": "Profile not found", "profile_id": profile_id}
            
            logger.info(f"Starting processing for profile: {profile.name}")
            
            # Update status
            profile.processing_status = "processing"
            db.commit()
            
            # Step 1: LinkedIn Discovery (if needed)
            linkedin_url = await self._ensure_linkedin_url(profile, db)
            if not linkedin_url:
                return await self._handle_processing_error(
                    profile, db, "linkedin_discovery", "Could not find LinkedIn profile"
                )
            
            # Step 2: BrightData Scraping
            linkedin_data = await self._scrape_linkedin_profile(profile, linkedin_url, db)
            if not linkedin_data:
                return await self._handle_processing_error(
                    profile, db, "brightdata_scraping", "LinkedIn scraping failed"
                )
            
            # Step 3: Discover additional social links
            social_links = await self._discover_social_links(profile, linkedin_url, db)
            
            # Step 4: GPT Assessment
            assessment = await self._assess_with_gpt(profile, linkedin_data, db)
            if not assessment or assessment.get("error"):
                return await self._handle_processing_error(
                    profile, db, "gpt_assessment", "GPT assessment failed"
                )
            
            # Step 5: Update profile with results
            await self._save_results(profile, linkedin_data, social_links, assessment, db)
            
            # Step 6: Update rankings
            await self._update_rankings(db)
            
            logger.info(f"Successfully processed profile: {profile.name}")
            return {
                "success": True,
                "profile_id": profile_id,
                "final_score": profile.final_score,
                "ranking": profile.ranking
            }
            
        except Exception as e:
            logger.error(f"Profile processing failed for {profile_id}: {str(e)}")
            return await self._handle_processing_error(
                db.query(Profile).filter(Profile.id == profile_id).first() if 'profile' not in locals() else profile,
                db, "general", str(e)
            )
        finally:
            db.close()
    
    async def _ensure_linkedin_url(self, profile: Profile, db: Session) -> Optional[str]:
        """Ensure profile has a LinkedIn URL, discover if missing."""
        try:
            # Log step start
            self._log_step(db, profile.id, "linkedin_discovery", "started", "Checking LinkedIn URL")
            
            # Check if profile already has a LinkedIn URL
            if profile.linkedin_profile:
                # Normalize existing URL
                normalized_url = self.linkedin_discovery.normalize_linkedin_url(profile.linkedin_profile)
                if normalized_url and await self.linkedin_discovery.validate_linkedin_url(normalized_url):
                    # Update profile with normalized URL if it changed
                    if normalized_url != profile.linkedin_profile:
                        profile.linkedin_profile = normalized_url
                        db.commit()
                        logger.info(f"Normalized existing LinkedIn URL: {profile.linkedin_profile} -> {normalized_url}")
                    
                    self._log_step(db, profile.id, "linkedin_discovery", "completed", 
                                 "LinkedIn URL already available", {"url": normalized_url})
                    return normalized_url
            
            # Discover LinkedIn URL
            logger.info(f"Discovering LinkedIn URL for: {profile.name}")
            linkedin_url = await self.linkedin_discovery.find_linkedin_profile(
                name=profile.name,
                email=profile.email,
                additional_info=profile.additional_info
            )
            
            if linkedin_url:
                profile.linkedin_profile = linkedin_url
                db.commit()
                self._log_step(db, profile.id, "linkedin_discovery", "completed", 
                             "LinkedIn URL discovered", {"url": linkedin_url})
                return linkedin_url
            
            self._log_step(db, profile.id, "linkedin_discovery", "failed", "No LinkedIn URL found")
            return None
            
        except Exception as e:
            self._log_step(db, profile.id, "linkedin_discovery", "failed", str(e))
            return None
    
    async def _scrape_linkedin_profile(self, profile: Profile, linkedin_url: str, db: Session) -> Optional[Dict[str, Any]]:
        """Scrape LinkedIn profile using BrightData."""
        try:
            self._log_step(db, profile.id, "brightdata_scraping", "started", 
                         "Starting LinkedIn scraping", {"url": linkedin_url})
            
            linkedin_data = await self.brightdata.scrape_linkedin_profile(linkedin_url)
            
            if linkedin_data:
                self._log_step(db, profile.id, "brightdata_scraping", "completed", 
                             "LinkedIn scraping successful", {"data_size": len(str(linkedin_data))})
                return linkedin_data
            
            self._log_step(db, profile.id, "brightdata_scraping", "failed", "Scraping returned no data")
            return None
            
        except Exception as e:
            self._log_step(db, profile.id, "brightdata_scraping", "failed", str(e))
            return None
    
    async def _discover_social_links(self, profile: Profile, linkedin_url: str, db: Session) -> Dict[str, str]:
        """Discover additional social media links."""
        try:
            self._log_step(db, profile.id, "social_discovery", "started", "Discovering social links")
            
            social_links = await self.linkedin_discovery.discover_additional_social_links(
                name=profile.name,
                linkedin_url=linkedin_url
            )
            
            self._log_step(db, profile.id, "social_discovery", "completed", 
                         "Social links discovered", {"links": list(social_links.keys())})
            return social_links
            
        except Exception as e:
            self._log_step(db, profile.id, "social_discovery", "failed", str(e))
            return {"linkedin": linkedin_url}  # At least return LinkedIn
    
    async def _assess_with_gpt(self, profile: Profile, linkedin_data: Dict[str, Any], db: Session) -> Optional[Dict[str, Any]]:
        """Assess profile using GPT-4o-mini."""
        try:
            self._log_step(db, profile.id, "gpt_assessment", "started", "Starting GPT assessment")
            
            assessment = await self.gpt_scoring.assess_o1_compatibility(linkedin_data)
            
            if assessment and not assessment.get("error"):
                self._log_step(db, profile.id, "gpt_assessment", "completed", 
                             "GPT assessment successful", {"score": assessment.get("overall_score")})
                return assessment
            
            self._log_step(db, profile.id, "gpt_assessment", "failed", 
                         assessment.get("error", "Unknown GPT error"))
            return None
            
        except Exception as e:
            self._log_step(db, profile.id, "gpt_assessment", "failed", str(e))
            return None
    
    async def _save_results(self, profile: Profile, linkedin_data: Dict[str, Any], 
                          social_links: Dict[str, str], assessment: Dict[str, Any], db: Session):
        """Save all processing results to the profile."""
        try:
            # Update profile with all results
            profile.linkedin_data = linkedin_data
            profile.social_links = social_links
            profile.gpt_assessment = assessment
            profile.o1_evidence = assessment.get("evidence", {})
            profile.final_score = assessment.get("overall_score", 0.0)
            profile.processing_status = "completed"
            profile.updated_at = datetime.utcnow()
            
            db.commit()
            
            self._log_step(db, profile.id, "save_results", "completed", "Results saved successfully")
            
        except Exception as e:
            self._log_step(db, profile.id, "save_results", "failed", str(e))
            raise
    
    async def _update_rankings(self, db: Session):
        """Update rankings for all completed profiles."""
        try:
            # Get all completed profiles ordered by score
            profiles = db.query(Profile).filter(
                Profile.processing_status == "completed",
                Profile.final_score.isnot(None)
            ).order_by(Profile.final_score.desc()).all()
            
            # Update rankings
            for rank, profile in enumerate(profiles, 1):
                profile.ranking = rank
            
            db.commit()
            logger.info(f"Updated rankings for {len(profiles)} profiles")
            
        except Exception as e:
            logger.error(f"Ranking update failed: {str(e)}")
    
    async def _handle_processing_error(self, profile: Profile, db: Session, 
                                     step: str, error_message: str) -> Dict[str, Any]:
        """Handle processing errors and update profile status."""
        try:
            if profile:
                profile.processing_status = "failed"
                db.commit()
                self._log_step(db, profile.id, step, "failed", error_message)
            
            return {
                "error": error_message,
                "profile_id": profile.id if profile else "unknown",
                "failed_step": step
            }
        except Exception as e:
            logger.error(f"Error handling failed: {str(e)}")
            return {"error": f"Processing failed: {error_message}"}
    
    def _log_step(self, db: Session, profile_id: str, step: str, status: str, 
                  message: str, data: Dict[str, Any] = None):
        """Log processing step to database."""
        try:
            log_entry = ProcessingLog(
                profile_id=profile_id,
                step=step,
                status=status,
                message=message,
                data=data or {}
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Logging failed: {str(e)}")
    
    async def process_batch(self, profile_ids: list[str], max_concurrent: int = None) -> Dict[str, Any]:
        """
        Process multiple profiles concurrently.
        
        Args:
            profile_ids: List of profile IDs to process
            max_concurrent: Maximum concurrent processes (default from settings)
            
        Returns:
            Dictionary containing batch processing results
        """
        max_concurrent = max_concurrent or settings.max_concurrent_profiles
        
        logger.info(f"Starting batch processing of {len(profile_ids)} profiles with {max_concurrent} concurrent")
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(profile_id: str):
            async with semaphore:
                return await self.process_profile(profile_id)
        
        # Process all profiles concurrently
        results = await asyncio.gather(
            *[process_with_semaphore(pid) for pid in profile_ids],
            return_exceptions=True
        )
        
        # Analyze results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed")
        
        return {
            "total_processed": len(profile_ids),
            "successful": successful,
            "failed": failed,
            "results": results
        }
