"""LinkedIn Discovery Service for O-1 Assessment - LinkedIn Only."""

import asyncio
import logging
from typing import Dict, Optional
from tavily import TavilyClient

from config import settings

logger = logging.getLogger(__name__)


class LinkedInDiscoveryService:
    """Service to discover LinkedIn profiles using Tavily search."""
    
    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)
    
    def normalize_linkedin_url(self, url: str) -> str:
        """Normalize LinkedIn URL to standard format."""
        if not url:
            return ""
        
        # Remove common prefixes and clean up
        url = url.strip()
        if url.startswith("@"):
            url = url[1:]
        
        if not url.startswith("http"):
            if url.startswith("linkedin.com") or url.startswith("www.linkedin.com"):
                url = f"https://{url}"
            elif url.startswith("/in/"):
                url = f"https://linkedin.com{url}"
            else:
                url = f"https://linkedin.com/in/{url}"
        
        # Standardize domain
        url = url.replace("www.linkedin.com", "linkedin.com")
        url = url.replace("http://", "https://")
        
        # Remove trailing slashes and parameters
        url = url.rstrip("/").split("?")[0].split("#")[0]
        
        return url
    
    async def discover_linkedin_profile(self, name: str, email: str = None) -> Optional[str]:
        """Discover LinkedIn profile for a person."""
        try:
            from .tavily_service import TavilyService
            tavily_service = TavilyService()
            
            linkedin_url = await tavily_service.find_linkedin_profile(name, email)
            
            if linkedin_url:
                normalized_url = self.normalize_linkedin_url(linkedin_url)
                logger.info(f"Normalized LinkedIn URL: {linkedin_url} -> {normalized_url}")
                return normalized_url
            
            return None
            
        except Exception as e:
            logger.error(f"LinkedIn discovery failed for {name}: {str(e)}")
            return None
    
    async def validate_linkedin_url(self, url: str) -> bool:
        """Validate if a LinkedIn URL is accessible and valid."""
        try:
            import httpx
            
            # Basic URL validation
            if not url or "linkedin.com/in/" not in url:
                return False
            
            # Try to access the URL (basic check)
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    response = await client.head(url, follow_redirects=True)
                    return response.status_code == 200
                except httpx.TimeoutException:
                    logger.warning(f"LinkedIn URL validation timeout: {url}")
                    return True  # Assume valid if just timeout
                except Exception as e:
                    logger.warning(f"LinkedIn URL validation failed: {url} - {str(e)}")
                    return False
            
        except Exception as e:
            logger.error(f"LinkedIn validation error for {url}: {str(e)}")
            return False
    
    async def discover_additional_social_links(self, name: str, email: str = None, linkedin_url: str = None) -> Dict[str, str]:
        """Discover social media links - LinkedIn only (Twitter and GitHub removed)."""
        social_links = {}
        
        try:
            # Only LinkedIn - Twitter and GitHub discovery removed
            if linkedin_url:
                social_links["linkedin"] = linkedin_url
            
            logger.info(f"Social links for {name}: LinkedIn only")
            return social_links
            
        except Exception as e:
            logger.error(f"Social links discovery failed for {name}: {str(e)}")
            return social_links