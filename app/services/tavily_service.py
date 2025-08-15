"""Tavily API integration for LinkedIn profile discovery."""

import logging
from typing import Optional
from tavily import TavilyClient
from config import settings

logger = logging.getLogger(__name__)


class TavilyService:
    """Service for discovering LinkedIn profiles using Tavily search API."""
    
    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)
    
    async def find_linkedin_profile(self, name: str, email: str = None, additional_info: str = None) -> Optional[str]:
        """
        Find LinkedIn profile URL for a person using Tavily search.
        
        Args:
            name: Full name of the person
            email: Email address (optional, helps with disambiguation)
            additional_info: Any additional context (company, role, etc.)
            
        Returns:
            LinkedIn profile URL if found, None otherwise
        """
        try:
            # Construct search query for LinkedIn
            query_parts = [f'"{name}"', "site:linkedin.com/in/"]
            
            if email and "@" in email:
                # Add company domain if available
                domain = email.split("@")[1]
                query_parts.append(f'"{domain}"')
            
            if additional_info:
                query_parts.append(f'"{additional_info}"')
            
            query = " ".join(query_parts)
            
            logger.info(f"Searching LinkedIn for: {query}")
            
            # Search using Tavily
            response = self.client.search(
                query=query,
                search_depth="basic",
                max_results=settings.max_linkedin_search_results,
                include_raw_content=False
            )
            
            # Extract LinkedIn URLs from results
            linkedin_urls = []
            for result in response.get("results", []):
                url = result.get("url", "")
                if "linkedin.com/in/" in url and url not in linkedin_urls:
                    linkedin_urls.append(url)
            
            if linkedin_urls:
                # Return the first (most relevant) LinkedIn URL
                best_url = linkedin_urls[0]
                logger.info(f"Found LinkedIn profile: {best_url}")
                return best_url
            
            logger.warning(f"No LinkedIn profile found for: {name}")
            return None
            
        except Exception as e:
            logger.error(f"LinkedIn discovery failed for {name}: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test Tavily API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple test search
            response = self.client.search(
                query="test site:linkedin.com",
                search_depth="basic",
                max_results=1,
                include_raw_content=False
            )
            return "results" in response
        except Exception as e:
            logger.error(f"Tavily connection test failed: {str(e)}")
            return False