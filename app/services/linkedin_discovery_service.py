"""LinkedIn Discovery Service using Tavily API to find LinkedIn profiles."""

import logging
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
from tavily import TavilyClient
from config import settings

logger = logging.getLogger(__name__)


class LinkedInDiscoveryService:
    """Service to discover LinkedIn profiles using Tavily search."""
    
    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)
    
    def normalize_linkedin_url(self, url: str) -> Optional[str]:
        """
        Normalize LinkedIn URL by removing regional suffixes and parameters.
        
        Args:
            url: Raw LinkedIn URL from search results
            
        Returns:
            Normalized LinkedIn URL or None if invalid
        """
        try:
            if not url or "linkedin.com/in/" not in url:
                return None
            
            # Parse the URL
            parsed = urlparse(url)
            
            # Extract the path and remove regional suffixes
            path = parsed.path
            
            # Remove common regional suffixes like /nl, /br, /de, etc.
            regional_suffixes = ['/nl', '/br', '/de', '/fr', '/es', '/it', '/jp', '/cn', '/in', '/uk']
            for suffix in regional_suffixes:
                if path.endswith(suffix):
                    path = path[:-len(suffix)]
                    break
            
            # Remove trailing slashes
            path = path.rstrip('/')
            
            # Validate path format: should be /in/username
            if not re.match(r'^/in/[a-zA-Z0-9\-_]+$', path):
                logger.warning(f"Invalid LinkedIn path format: {path}")
                return None
            
            # Reconstruct clean URL
            clean_url = f"https://linkedin.com{path}"
            
            logger.info(f"Normalized LinkedIn URL: {url} -> {clean_url}")
            return clean_url
            
        except Exception as e:
            logger.error(f"Failed to normalize LinkedIn URL {url}: {str(e)}")
            return None
    
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
            # Construct search query
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
            
            # Extract and normalize LinkedIn URLs from results
            linkedin_urls = []
            for result in response.get("results", []):
                url = result.get("url", "")
                if "linkedin.com/in/" in url:
                    # Normalize the URL
                    normalized_url = self.normalize_linkedin_url(url)
                    if normalized_url and normalized_url not in linkedin_urls:
                        linkedin_urls.append(normalized_url)
            
            if linkedin_urls:
                # Return the first (most relevant) normalized LinkedIn URL
                best_url = linkedin_urls[0]
                logger.info(f"Found and normalized LinkedIn profile: {best_url}")
                return best_url
            
            logger.warning(f"No LinkedIn profile found for: {name}")
            return None
            
        except Exception as e:
            logger.error(f"LinkedIn discovery failed for {name}: {str(e)}")
            return None
    
    async def validate_linkedin_url(self, url: str) -> bool:
        """
        Validate if a LinkedIn URL is properly formatted and normalized.
        
        Args:
            url: LinkedIn profile URL
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if not url or "linkedin.com/in/" not in url:
                return False
            
            # Parse URL
            parsed = urlparse(url)
            
            # Check domain
            if parsed.netloc not in ['linkedin.com', 'www.linkedin.com']:
                return False
            
            # Check path format
            path = parsed.path
            if not re.match(r'^/in/[a-zA-Z0-9\-_]+$', path):
                return False
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check for regional suffixes (should be normalized)
            regional_suffixes = ['/nl', '/br', '/de', '/fr', '/es', '/it', '/jp', '/cn', '/in', '/uk']
            for suffix in regional_suffixes:
                if path.endswith(suffix):
                    logger.warning(f"URL contains regional suffix: {url}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"LinkedIn URL validation failed for {url}: {str(e)}")
            return False
    
    async def discover_additional_social_links(self, name: str, linkedin_url: str = None) -> Dict[str, str]:
        """
        Discover additional social media profiles for a person.
        
        Args:
            name: Full name of the person
            linkedin_url: Known LinkedIn URL (optional)
            
        Returns:
            Dictionary of social platform -> URL
        """
        social_links = {}
        
        try:
            # Search for Twitter/X profile
            twitter_query = f'"{name}" site:twitter.com OR site:x.com'
            twitter_response = self.client.search(
                query=twitter_query,
                search_depth="basic",
                max_results=3,
                include_raw_content=False
            )
            
            for result in twitter_response.get("results", []):
                url = result.get("url", "")
                if ("twitter.com/" in url or "x.com/" in url) and "/status/" not in url:
                    social_links["twitter"] = url
                    break
            
            # Search for GitHub profile
            github_query = f'"{name}" site:github.com'
            github_response = self.client.search(
                query=github_query,
                search_depth="basic",
                max_results=3,
                include_raw_content=False
            )
            
            for result in github_response.get("results", []):
                url = result.get("url", "")
                if "github.com/" in url and "/blob/" not in url and "/issues/" not in url:
                    social_links["github"] = url
                    break
            
            if linkedin_url:
                social_links["linkedin"] = linkedin_url
            
            logger.info(f"Found social links for {name}: {list(social_links.keys())}")
            return social_links
            
        except Exception as e:
            logger.error(f"Social links discovery failed for {name}: {str(e)}")
            return social_links
