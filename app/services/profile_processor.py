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
from app.services.scoring_v1 import GPTScoringService

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
            
            # Step 1: Use existing LinkedIn URL (no discovery needed)
            linkedin_url = profile.linkedin_profile
            if not linkedin_url:
                return await self._handle_processing_error(
                    profile, db, "linkedin_url", "No LinkedIn profile URL available"
                )
            
            # Step 2: BrightData Scraping
            linkedin_data = await self._scrape_linkedin_profile(profile, linkedin_url, db)
            if not linkedin_data:
                return await self._handle_processing_error(
                    profile, db, "brightdata_scraping", "LinkedIn scraping failed"
                )
            
            # Step 3: Social links simplified (LinkedIn only)
            social_links = {"linkedin": linkedin_url}
            
            # Step 4: GitHub Analytics removed - focusing on LinkedIn + Twitter only
            github_data = None
            
            # Step 4.5: GitHub enhancement removed
            
            # Step 5: GPT Assessment (now includes GitHub data)
            assessment = await self._assess_with_gpt(profile, linkedin_data, github_data, db)
            if not assessment or assessment.get("error"):
                return await self._handle_processing_error(
                    profile, db, "gpt_assessment", "GPT assessment failed"
                )
            
            # Step 6: Update profile with results
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
                email=profile.email,
                linkedin_url=linkedin_url
            )
            
            self._log_step(db, profile.id, "social_discovery", "completed", 
                         "Social links discovered", {"links": list(social_links.keys())})
            return social_links
            
        except Exception as e:
            self._log_step(db, profile.id, "social_discovery", "failed", str(e))
            return {"linkedin": linkedin_url}  # At least return LinkedIn
    

    

    
    async def _assess_with_gpt(self, profile: Profile, linkedin_data: Dict[str, Any], 
                              github_data: Optional[Dict[str, Any]], db: Session) -> Optional[Dict[str, Any]]:
        """Assess profile using GPT-4o-mini (GitHub removed)."""
        try:
            self._log_step(db, profile.id, "gpt_assessment", "started", "Starting GPT assessment")
            
            # Use only LinkedIn data for assessment (GitHub removed)
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

            # Compute judge auto-suggestion
            auto_score, auto_reason = self._compute_judge_auto_suggestion(linkedin_data, assessment)
            profile.judge_auto_score = auto_score
            profile.judge_auto_reason = auto_reason
            # Only set default status if still unknown
            if not profile.judge_status or profile.judge_status == "unknown":
                # mark as candidate if high auto score
                profile.judge_status = "candidate" if (auto_score is not None and auto_score >= 0.6) else "unknown"
            
            # GitHub data removed from storage
            
            db.commit()
            
            self._log_step(db, profile.id, "save_results", "completed", "Results saved successfully")
            
        except Exception as e:
            self._log_step(db, profile.id, "save_results", "failed", str(e))
            raise

    def _compute_judge_auto_suggestion(self, linkedin_data: Dict[str, Any], assessment: Dict[str, Any]) -> tuple[float, str]:
        """Heuristic judge auto-score (0..1) and reason from LinkedIn data."""
        try:
            score_points = 0
            max_points = 6
            reasons = []
            basic = (linkedin_data or {}).get("basic_info", {})
            headline = (basic.get("headline") or "").lower()
            current_company = (basic.get("current_company") or "")

            # Seniority/title
            senior_terms = ["founder", "co-founder", "principal", "staff", "lead", "head", "director", "professor", "research scientist"]
            if any(t in headline for t in senior_terms):
                score_points += 1
                reasons.append("senior title")

            # LinkedIn network
            connections = (basic.get("linkedin_connections") or 0)
            followers = (basic.get("linkedin_followers") or 0)
            total = (connections or 0) + (followers or 0)
            if total >= 7000:
                score_points += 2
                reasons.append("large network ≥7k")
            elif total >= 3000:
                score_points += 1
                reasons.append("network ≥3k")

            # Company prestige
            tier_companies = ["Google", "Meta", "Apple", "Microsoft", "Amazon", "NVIDIA"]
            if current_company and any(c in current_company for c in tier_companies):
                score_points += 1
                reasons.append("tier-1 company")

            # Community involvement
            acc = (linkedin_data or {}).get("accomplishments", {})
            memberships = acc.get("memberships", []) or []
            prof_memberships = acc.get("professional_memberships", []) or []
            orgs = acc.get("organizations", []) or []
            volunteer = acc.get("volunteer_experience", []) or []
            if any([memberships, prof_memberships, orgs, volunteer]) and (
                len(memberships) + len(prof_memberships) + len(orgs) + len(volunteer) >= 1
            ):
                score_points += 1
                reasons.append("community roles/memberships")

            # Visibility/impact
            awards = acc.get("awards", []) or []
            publications = acc.get("publications", []) or []
            projects = acc.get("projects", []) or []
            if any([awards, publications, projects]):
                score_points += 1
                reasons.append("awards/publications/projects")

            # Recommendations
            recs = basic.get("recommendations_count") or 0
            if recs >= 5:
                score_points += 1
                reasons.append("≥5 recommendations")

            score = min(1.0, max(0.0, score_points / max_points)) if max_points > 0 else 0.0
            return score, ", ".join(reasons)
        except Exception:
            return None, ""
    
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
    
    async def process_profiles_sequentially(self, profile_ids: list = None, max_profiles: int = None) -> Dict[str, Any]:
        """
        Process profiles one by one to avoid timeouts and resource issues.
        
        Args:
            profile_ids: List of specific profile IDs to process. If None, processes pending profiles.
            max_profiles: Maximum number of profiles to process in this batch
            
        Returns:
            Dictionary with processing results and statistics
        """
        db = SessionLocal()
        try:
            # Get profiles to process
            if profile_ids:
                profiles_query = db.query(Profile).filter(Profile.id.in_(profile_ids))
            else:
                profiles_query = db.query(Profile).filter(
                    Profile.processing_status.in_(['pending', 'failed'])
                ).order_by(Profile.created_at)
            
            if max_profiles:
                profiles_query = profiles_query.limit(max_profiles)
            
            profiles_to_process = profiles_query.all()
            
            logger.info(f"Starting sequential processing of {len(profiles_to_process)} profiles")
            
            results = {
                "total_profiles": len(profiles_to_process),
                "successful": 0,
                "failed": 0,
                "results": [],
                "start_time": datetime.utcnow().isoformat()
            }
            
            for i, profile in enumerate(profiles_to_process, 1):
                logger.info(f"Processing profile {i}/{len(profiles_to_process)}: {profile.name}")
                
                try:
                    # Process individual profile
                    result = await self.process_profile(profile.id)
                    
                    if "error" in result:
                        results["failed"] += 1
                        logger.error(f"Failed to process {profile.name}: {result['error']}")
                    else:
                        results["successful"] += 1
                        logger.info(f"Successfully processed {profile.name} (Score: {result.get('final_score', 'N/A')})")
                    
                    results["results"].append({
                        "profile_id": profile.id,
                        "name": profile.name,
                        "email": profile.email,
                        "result": result
                    })
                    
                    # Small delay between profiles to be gentle on APIs
                    if i < len(profiles_to_process):  # Don't wait after last profile
                        logger.info("Waiting 10s before next profile...")
                        await asyncio.sleep(10)
                        
                except Exception as e:
                    results["failed"] += 1
                    logger.error(f"Exception processing {profile.name}: {str(e)}")
                    results["results"].append({
                        "profile_id": profile.id,
                        "name": profile.name,
                        "email": profile.email,
                        "result": {"error": str(e)}
                    })
            
            results["end_time"] = datetime.utcnow().isoformat()
            results["success_rate"] = (results["successful"] / results["total_profiles"]) * 100 if results["total_profiles"] > 0 else 0
            
            logger.info(f"Sequential processing completed: {results['successful']}/{results['total_profiles']} successful ({results['success_rate']:.1f}%)")
            
            return results
            
        except Exception as e:
            logger.error(f"Sequential processing failed: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()
