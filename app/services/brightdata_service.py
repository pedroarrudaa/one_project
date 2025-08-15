"""BrightData Service for LinkedIn profile scraping."""

import asyncio
import logging
from typing import Dict, Any, Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)


class BrightDataService:
    """Service to scrape LinkedIn profiles using BrightData API."""
    
    def __init__(self):
        self.api_key = settings.brightdata_api_key
        self.timeout = settings.brightdata_timeout
        self.retries = settings.brightdata_retries
        self.base_url = "https://api.brightdata.com/datasets/v3/trigger"
        self.dataset_id = "gd_l1viktl72bvl7bjuj0"
    
    async def scrape_linkedin_profile(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape LinkedIn profile data using BrightData API.
        
        Args:
            linkedin_url: LinkedIn profile URL to scrape
            
        Returns:
            Dictionary containing scraped profile data or None if failed
        """
        try:
            logger.info(f"Starting LinkedIn scrape for: {linkedin_url}")
            
            # Prepare request payload for BrightData (array format)
            payload = [{"url": linkedin_url}]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            params = {
                "dataset_id": self.dataset_id,
                "include_errors": "true"
            }
            
            # Make API request with retries
            for attempt in range(self.retries):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            self.base_url,
                            params=params,
                            json=payload,
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            logger.info(f"BrightData collection triggered: {data}")
                            
                            # BrightData returns snapshot_id, we need to poll for results
                            snapshot_id = data.get("snapshot_id")
                            if snapshot_id:
                                return await self._wait_for_results(snapshot_id)
                            else:
                                logger.error("No snapshot_id returned from BrightData")
                                return None
                        
                        elif response.status_code == 429:  # Rate limited
                            wait_time = 2 ** attempt
                            logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                            await asyncio.sleep(wait_time)
                            continue
                        
                        else:
                            logger.error(f"BrightData API error {response.status_code}: {response.text}")
                            break
                
                except httpx.TimeoutException:
                    logger.warning(f"Timeout on attempt {attempt + 1} for {linkedin_url}")
                    if attempt < self.retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        break
                
                except Exception as e:
                    logger.error(f"Request failed on attempt {attempt + 1}: {str(e)}")
                    if attempt < self.retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        break
            
            logger.error(f"Failed to scrape LinkedIn profile after {self.retries} attempts: {linkedin_url}")
            return None
            
        except Exception as e:
            logger.error(f"LinkedIn scraping failed for {linkedin_url}: {str(e)}")
            return None
    
    async def _wait_for_results(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Wait for BrightData collection results using snapshot_id.
        
        Args:
            snapshot_id: The snapshot ID returned by BrightData trigger
            
        Returns:
            Scraped profile data or None if failed
        """
        try:
            # BrightData results endpoint
            results_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # Poll for results (max 3 minutes)
            max_attempts = 18  # 18 attempts * 10 seconds = 180 seconds (3 minutes)
            
            for attempt in range(max_attempts):
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(results_url, headers=headers)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check if data is ready (can be array or single object)
                        if isinstance(data, list) and len(data) > 0:
                            # Return first profile data
                            profile_data = data[0]
                            logger.info(f"Successfully retrieved LinkedIn data for snapshot: {snapshot_id}")
                            return self._normalize_linkedin_data(profile_data)
                        elif isinstance(data, dict) and "id" in data:
                            # Single profile object
                            logger.info(f"Successfully retrieved LinkedIn data for snapshot: {snapshot_id}")
                            return self._normalize_linkedin_data(data)
                        
                        # Check if status is still running
                        elif isinstance(data, dict) and data.get("status") == "running":
                            logger.info(f"BrightData still processing... attempt {attempt + 1}/{max_attempts}")
                            await asyncio.sleep(10)
                            continue
                    
                    elif response.status_code == 202:
                        # Status 202 means still processing
                        logger.info(f"BrightData processing (202)... attempt {attempt + 1}/{max_attempts}")
                        await asyncio.sleep(10)
                        continue
                    
                    elif response.status_code == 404:
                        # Data not ready yet, wait and retry
                        logger.info(f"Waiting for BrightData results... attempt {attempt + 1}/{max_attempts}")
                        await asyncio.sleep(10)
                        continue
                    
                    else:
                        logger.error(f"Error fetching results: {response.status_code} - {response.text}")
                        break
            
            logger.error(f"Timeout waiting for BrightData results: {snapshot_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error waiting for results: {str(e)}")
            return None
    
    def _normalize_linkedin_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize raw BrightData response into standardized format.
        
        Args:
            raw_data: Raw response from BrightData API
            
        Returns:
            Normalized profile data
        """
        try:
            # Extract key information from BrightData response
            # Note: Actual field names depend on BrightData's response format
            normalized = {
                "basic_info": {
                    "name": raw_data.get("name", ""),
                    "headline": raw_data.get("current_company", {}).get("name", "") if raw_data.get("current_company") else "",
                    "location": raw_data.get("city", "") or raw_data.get("location", ""),
                    "summary": raw_data.get("summary", ""),
                    "profile_url": raw_data.get("url", "") or raw_data.get("input_url", ""),
                    "profile_image": raw_data.get("avatar", ""),
                    "connections_count": raw_data.get("connections", 0),  # Usar 'connections' do BrightData
                    "followers_count": raw_data.get("followers", 0),
                    "current_company": raw_data.get("current_company_name", "")
                },
                "experience": [],
                "education": [],
                "skills": [],
                "accomplishments": {
                    "publications": [],
                    "patents": [],
                    "awards": [],
                    "certifications": [],
                    "languages": [],
                    "projects": []
                },
                "recommendations": [],
                "raw_data": raw_data  # Keep original for debugging
            }
            
            # Normalize experience
            experience_data = raw_data.get("experience") or []
            if experience_data:
                for exp in experience_data:
                    normalized["experience"].append({
                        "title": exp.get("title", ""),
                        "company": exp.get("company", ""),
                        "location": exp.get("location", ""),
                        "start_date": exp.get("start_date", ""),
                        "end_date": exp.get("end_date", ""),
                        "description": exp.get("description", ""),
                        "duration": exp.get("duration", "")
                    })
            
            # Normalize education
            education_data = raw_data.get("education") or []
            if education_data:
                for edu in education_data:
                    normalized["education"].append({
                        "school": edu.get("title", "") or edu.get("school", ""),
                        "degree": edu.get("degree", ""),
                        "field": edu.get("field", ""),
                        "start_year": edu.get("start_year", ""),
                        "end_year": edu.get("end_year", ""),
                        "description": edu.get("description", "")
                    })
            
            # Normalize skills
            normalized["skills"] = raw_data.get("skills", [])
            
            # Normalize accomplishments
            accomplishments = raw_data.get("accomplishments", {})
            if accomplishments:
                normalized["accomplishments"]["publications"] = accomplishments.get("publications", [])
                normalized["accomplishments"]["patents"] = accomplishments.get("patents", [])
                normalized["accomplishments"]["awards"] = accomplishments.get("awards", [])
                normalized["accomplishments"]["certifications"] = accomplishments.get("certifications", [])
                normalized["accomplishments"]["languages"] = accomplishments.get("languages", [])
                normalized["accomplishments"]["projects"] = accomplishments.get("projects", [])
            
            # Normalize recommendations
            recommendations_data = raw_data.get("recommendations") or []
            if recommendations_data:
                for rec in recommendations_data:
                    if isinstance(rec, str):
                        # Handle string format recommendations
                        normalized["recommendations"].append({
                            "recommender": "",
                            "relationship": "",
                            "text": rec
                        })
                    else:
                        normalized["recommendations"].append({
                            "recommender": rec.get("recommender", ""),
                            "relationship": rec.get("relationship", ""),
                            "text": rec.get("text", "")
                        })
            
            return normalized
            
        except Exception as e:
            logger.error(f"Data normalization failed: {str(e)}")
            return {"raw_data": raw_data, "normalization_error": str(e)}
    

    async def get_snapshot_results(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get results from a specific BrightData snapshot.
        
        Args:
            snapshot_id: The snapshot ID to retrieve results from
            
        Returns:
            Scraped profile data or None if failed
        """
        try:
            results_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(results_url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if data is ready (can be array or single object)
                    if isinstance(data, list) and len(data) > 0:
                        # Return first profile data
                        profile_data = data[0]
                        logger.info(f"Successfully retrieved LinkedIn data for snapshot: {snapshot_id}")
                        return self._normalize_linkedin_data(profile_data)
                    elif isinstance(data, dict) and "id" in data:
                        # Single profile object
                        logger.info(f"Successfully retrieved LinkedIn data for snapshot: {snapshot_id}")
                        return self._normalize_linkedin_data(data)
                    
                    # Check if status is still running
                    elif isinstance(data, dict) and data.get("status") == "running":
                        logger.info(f"BrightData snapshot {snapshot_id} still processing")
                        return None
                
                else:
                    logger.error(f"Error fetching snapshot {snapshot_id}: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting snapshot results: {str(e)}")
            return None
    
    async def test_connection(self) -> bool:
        """
        Test BrightData API connection and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/status",  # Update with actual health check endpoint
                    headers=headers
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"BrightData connection test failed: {str(e)}")
            return False
