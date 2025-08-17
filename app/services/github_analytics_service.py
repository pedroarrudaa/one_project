"""GitHub Analytics Service for collecting repository and contribution data."""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GitHubAnalyticsService:
    """Service to collect GitHub analytics data for O-1 assessment."""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.timeout = 30
    
    def extract_username_from_url(self, github_url: str) -> Optional[str]:
        """Extract GitHub username from various URL formats."""
        if not github_url:
            return None
        
        # Handle different GitHub URL formats
        patterns = [
            r'github\.com/([^/\?#]+)',  # https://github.com/username
            r'@([^/\?#]+)',             # @username
        ]
        
        for pattern in patterns:
            match = re.search(pattern, github_url.lower())
            if match:
                username = match.group(1)
                # Skip invalid usernames
                if username not in ['orgs', 'topics', 'collections', 'explore', 'marketplace']:
                    return username
        
        return None
    
    async def get_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Get basic GitHub user profile information."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/users/{username}")
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(f"GitHub user not found: {username}")
                    return None
                else:
                    logger.error(f"GitHub API error {response.status_code} for user: {username}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to fetch GitHub profile for {username}: {str(e)}")
            return None
    
    async def get_user_repositories(self, username: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get user's repositories with star counts and other metrics."""
        try:
            repos = []
            page = 1
            per_page = min(limit, 100)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                while len(repos) < limit:
                    response = await client.get(
                        f"{self.base_url}/users/{username}/repos",
                        params={
                            "sort": "updated",
                            "direction": "desc",
                            "page": page,
                            "per_page": per_page
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch repos for {username}: {response.status_code}")
                        break
                    
                    page_repos = response.json()
                    if not page_repos:
                        break
                    
                    repos.extend(page_repos)
                    page += 1
                    
                    if len(page_repos) < per_page:
                        break
            
            return repos[:limit]
            
        except Exception as e:
            logger.error(f"Failed to fetch repositories for {username}: {str(e)}")
            return []
    
    async def analyze_github_profile(self, github_url: str) -> Dict[str, Any]:
        """
        Comprehensive GitHub profile analysis for O-1 assessment.
        
        Args:
            github_url: GitHub profile URL or username
            
        Returns:
            Dictionary containing GitHub analytics and scoring
        """
        try:
            username = self.extract_username_from_url(github_url)
            if not username:
                return self._create_empty_analysis("Invalid GitHub URL")
            
            logger.info(f"Analyzing GitHub profile: {username}")
            
            # Get user profile and repositories in parallel
            profile_task = self.get_user_profile(username)
            repos_task = self.get_user_repositories(username, limit=50)
            
            profile, repositories = await asyncio.gather(profile_task, repos_task)
            
            if not profile:
                return self._create_empty_analysis("GitHub profile not found")
            
            # Analyze the data
            analysis = self._analyze_github_data(profile, repositories, username)
            
            logger.info(f"GitHub analysis completed for {username}: {analysis['impact_score']}/10")
            return analysis
            
        except Exception as e:
            logger.error(f"GitHub analysis failed for {github_url}: {str(e)}")
            return self._create_empty_analysis(f"Analysis failed: {str(e)}")
    
    def _analyze_github_data(self, profile: Dict[str, Any], repositories: List[Dict[str, Any]], username: str) -> Dict[str, Any]:
        """Analyze GitHub data and calculate impact score."""
        
        # Basic profile metrics
        followers = profile.get('followers', 0)
        following = profile.get('following', 0)
        public_repos = profile.get('public_repos', 0)
        
        # Repository analysis
        total_stars = sum(repo.get('stargazers_count', 0) for repo in repositories)
        total_forks = sum(repo.get('forks_count', 0) for repo in repositories)
        total_watchers = sum(repo.get('watchers_count', 0) for repo in repositories)
        
        # Find top repositories
        top_repos = sorted(repositories, key=lambda r: r.get('stargazers_count', 0), reverse=True)[:5]
        
        # Language analysis
        languages = {}
        for repo in repositories:
            lang = repo.get('language')
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
        
        # Original vs forked repositories
        original_repos = [repo for repo in repositories if not repo.get('fork', False)]
        forked_repos = [repo for repo in repositories if repo.get('fork', False)]
        
        # Calculate impact score (1-10)
        impact_score = self._calculate_github_impact_score(
            followers, total_stars, total_forks, len(original_repos), public_repos
        )
        
        # Create analysis summary
        analysis_summary = self._create_github_summary(
            impact_score, followers, total_stars, len(original_repos), public_repos
        )
        
        return {
            "username": username,
            "profile_url": f"https://github.com/{username}",
            "impact_score": impact_score,
            "analysis_summary": analysis_summary,
            "metrics": {
                "followers": followers,
                "following": following,
                "public_repos": public_repos,
                "original_repos": len(original_repos),
                "forked_repos": len(forked_repos),
                "total_stars": total_stars,
                "total_forks": total_forks,
                "total_watchers": total_watchers
            },
            "top_repositories": [
                {
                    "name": repo.get('name', ''),
                    "description": repo.get('description', ''),
                    "stars": repo.get('stargazers_count', 0),
                    "forks": repo.get('forks_count', 0),
                    "language": repo.get('language', ''),
                    "url": repo.get('html_url', ''),
                    "is_fork": repo.get('fork', False)
                }
                for repo in top_repos
            ],
            "languages": dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]),
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _calculate_github_impact_score(self, followers: int, total_stars: int, total_forks: int, 
                                     original_repos: int, public_repos: int) -> int:
        """Calculate GitHub impact score (1-10) based on various metrics."""
        
        score = 1  # Base score
        
        # Follower impact (0-3 points)
        if followers >= 10000:
            score += 3
        elif followers >= 5000:
            score += 2.5
        elif followers >= 1000:
            score += 2
        elif followers >= 500:
            score += 1.5
        elif followers >= 100:
            score += 1
        elif followers >= 50:
            score += 0.5
        
        # Star impact (0-4 points)
        if total_stars >= 10000:
            score += 4
        elif total_stars >= 5000:
            score += 3.5
        elif total_stars >= 1000:
            score += 3
        elif total_stars >= 500:
            score += 2.5
        elif total_stars >= 100:
            score += 2
        elif total_stars >= 50:
            score += 1.5
        elif total_stars >= 10:
            score += 1
        elif total_stars >= 5:
            score += 0.5
        
        # Repository quality (0-2 points)
        if original_repos >= 20:
            score += 2
        elif original_repos >= 10:
            score += 1.5
        elif original_repos >= 5:
            score += 1
        elif original_repos >= 2:
            score += 0.5
        
        # Fork impact (0-1 point)
        if total_forks >= 1000:
            score += 1
        elif total_forks >= 100:
            score += 0.7
        elif total_forks >= 10:
            score += 0.3
        
        return min(10, max(1, round(score)))
    
    def _create_github_summary(self, score: int, followers: int, total_stars: int, 
                              original_repos: int, public_repos: int) -> str:
        """Create a human-readable summary of GitHub impact."""
        
        if score >= 9:
            level = "GitHub Superstar"
        elif score >= 8:
            level = "Major GitHub Contributor"
        elif score >= 7:
            level = "Notable GitHub Presence"
        elif score >= 6:
            level = "Active GitHub Developer"
        elif score >= 5:
            level = "Regular GitHub User"
        elif score >= 3:
            level = "Casual GitHub User"
        else:
            level = "Basic GitHub Presence"
        
        return f"{level} - {followers:,} followers, {total_stars:,} total stars across {original_repos} original repos (of {public_repos} total)"
    
    def _create_empty_analysis(self, reason: str) -> Dict[str, Any]:
        """Create empty analysis result."""
        return {
            "username": None,
            "profile_url": None,
            "impact_score": 1,
            "analysis_summary": f"No GitHub Analysis - {reason}",
            "metrics": {
                "followers": 0,
                "following": 0,
                "public_repos": 0,
                "original_repos": 0,
                "forked_repos": 0,
                "total_stars": 0,
                "total_forks": 0,
                "total_watchers": 0
            },
            "top_repositories": [],
            "languages": {},
            "last_updated": datetime.utcnow().isoformat()
        }
