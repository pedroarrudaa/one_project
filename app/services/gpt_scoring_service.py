"""GPT-4o-mini Intelligent Scoring Service for O-1 Visa Assessment."""

import json
import logging
from typing import Dict, Any, List, Tuple
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)


class GPTScoringService:
    """Service to assess O-1 visa compatibility using GPT-4o-mini."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model
        self.temperature = settings.gpt_temperature
        self.max_tokens = settings.gpt_max_tokens
    
    def classify_seniority_level(self, job_title: str, company: str = "") -> Tuple[str, int, str]:
        """
        Classify professional seniority level based on job title.
        
        Args:
            job_title: Current or most recent job title
            company: Company name for context
            
        Returns:
            Tuple of (level_name, score_1_to_10, reasoning)
        """
        if not job_title:
            return ("Junior", 2, "No job title available")
        
        title_lower = job_title.lower()
        
        # VP Level (9-10 points) - Must be exact matches to avoid false positives
        vp_keywords = [
            'vp of', 'vp ', 'vice president', 'svp', 'senior vice president', 'evp', 'executive vice president',
            'chief technology officer', 'chief executive officer', 'chief financial officer',
            'chief operating officer', 'chief marketing officer', 'cto', 'ceo', 'cfo', 'coo', 'cmo',
            'head of engineering', 'head of product', 'head of data', 'head of ai', 'head of ml',
            'founder', 'co-founder', 'cofounder'
        ]
        
        # Executive Level (7-8 points)  
        executive_keywords = [
            'director', 'senior director', 'managing director', 'executive director',
            'principal', 'senior principal', 'distinguished', 'fellow', 'architect',
            'lead', 'team lead', 'tech lead', 'engineering manager', 'senior manager',
            'group manager', 'program manager', 'senior program manager'
        ]
        
        # Senior Level (4-6 points)
        senior_keywords = [
            'senior', 'sr.', 'staff', 'senior staff', 'specialist', 'senior specialist',
            'consultant', 'senior consultant', 'expert', 'senior expert'
        ]
        
        # Check VP level - More precise matching
        for keyword in vp_keywords:
            # Exact match or word boundary match
            if (keyword == title_lower or 
                f' {keyword} ' in f' {title_lower} ' or
                title_lower.startswith(keyword + ' ') or
                title_lower.endswith(' ' + keyword)):
                
                # Extra validation for common words that might be false positives
                if keyword in ['president'] and 'vice' not in title_lower and 'senior' not in title_lower:
                    continue
                    
                # Allow single word VP titles for specific C-level and founder roles
                if len(job_title.split()) == 1 and keyword not in ['cto', 'ceo', 'cfo', 'coo', 'cmo', 'founder']:
                    continue
                    
                score = 10 if any(k in title_lower for k in ['cto', 'ceo', 'founder', 'chief']) else 9
                return ("VP", score, f"VP-level title: {job_title}")
        
        # Check Executive level
        for keyword in executive_keywords:
            if keyword in title_lower:
                score = 8 if any(k in title_lower for k in ['director', 'principal', 'distinguished']) else 7
                return ("Executive", score, f"Executive-level title: {job_title}")
        
        # Check Senior level
        for keyword in senior_keywords:
            if keyword in title_lower:
                score = 6 if 'staff' in title_lower else 5 if 'senior' in title_lower else 4
                return ("Senior", score, f"Senior-level title: {job_title}")
        
        # Default to Junior
        return ("Junior", 2, f"Entry/mid-level title: {job_title}")
    
    async def assess_o1_compatibility(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess O-1 visa compatibility using GPT-4o-mini analysis.
        
        Args:
            profile_data: Complete profile data including LinkedIn information
            
        Returns:
            Dictionary containing assessment results
        """
        try:
            logger.info(f"Starting GPT assessment for profile: {profile_data.get('basic_info', {}).get('name', 'Unknown')}")
            
            # Prepare the prompt with profile data
            prompt = self._build_assessment_prompt(profile_data)
            
            # Make GPT API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Parse GPT response
            assessment_text = response.choices[0].message.content
            assessment = json.loads(assessment_text)
            
            logger.info(f"GPT assessment completed with score: {assessment.get('overall_score', 'N/A')}")
            return assessment
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {str(e)}")
            return self._create_fallback_assessment("JSON parsing error")
        
        except Exception as e:
            logger.error(f"GPT assessment failed: {str(e)}")
            return self._create_fallback_assessment(str(e))
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for O-1 assessment."""
        return """You are an expert immigration attorney specializing in O-1 visa applications. Your task is to assess a professional's eligibility for an O-1 visa based ONLY on their LinkedIn profile data.

The O-1 visa requires demonstrating "extraordinary ability" through sustained national or international acclaim. Since we only have LinkedIn data, focus on these LinkedIn-specific criteria:

Key LinkedIn-based O-1 criteria to evaluate:
1. **Professional Seniority**: CRITICAL - Use the seniority classification provided (Junior/Senior/Executive/VP)
2. **Company Prestige**: Work at top-tier companies (FAANG, unicorns, Fortune 500, prestigious startups)
3. **Career Progression**: Rapid advancement, increasing responsibilities, clear progression through seniority levels
4. **Professional Network**: High connection count, recommendations from senior professionals
5. **Skills & Expertise**: Specialized skills, certifications, technical expertise relevant to field

**SENIORITY LEVEL SCORING (Most Important Factor):**
- **VP Level (9-10 points)**: CTO, CEO, Founder, VP, Chief Officer, Head of Department
- **Executive Level (7-8 points)**: Director, Principal, Distinguished Engineer, Engineering Manager
- **Senior Level (4-6 points)**: Senior Engineer, Staff Engineer, Senior Specialist, Senior Consultant  
- **Junior Level (1-3 points)**: Engineer, Analyst, Coordinator, Associate, Entry-level roles

Assess each criterion on a scale of 1-10 based on what's visible in LinkedIn:
- **Professional Seniority**: Use the provided seniority analysis - this is pre-calculated and crucial
- **Company Prestige**: Google, Meta, Apple, Microsoft, OpenAI, top startups, well-known brands
- **Career Progression**: Multiple promotions, increasing scope, job title evolution
- **Professional Network**: 500+ connections, recommendations from executives/leaders
- **Skills & Expertise**: Advanced technical skills, industry certifications, specialized knowledge

Respond in JSON format with the following structure:
{
  "overall_score": float (1-10),
  "criteria_scores": {
    "professional_seniority": float (1-10),
    "company_prestige": float (1-10),
    "career_progression": float (1-10),
    "professional_network": float (1-10),
    "skills_expertise": float (1-10)
  },
  "evidence": {
    "professional_seniority": [list of specific evidence from LinkedIn],
    "company_prestige": [list of specific evidence from LinkedIn],
    "career_progression": [list of specific evidence from LinkedIn],
    "professional_network": [list of specific evidence from LinkedIn],
    "skills_expertise": [list of specific evidence from LinkedIn]
  },
  "strengths": [list of key strengths visible on LinkedIn],
  "weaknesses": [list of areas that appear weak on LinkedIn],
  "likelihood": "High|Medium|Low",
  "recommendation": "detailed recommendation based on LinkedIn profile",
  "reasoning": "detailed explanation focusing on LinkedIn-visible achievements"
}"""
    
    def _build_assessment_prompt(self, profile_data: Dict[str, Any]) -> str:
        """Build the assessment prompt with profile data."""
        
        basic_info = profile_data.get("basic_info", {})
        experience = profile_data.get("experience", [])
        education = profile_data.get("education", [])
        skills = profile_data.get("skills", [])
        accomplishments = profile_data.get("accomplishments", {})
        recommendations = profile_data.get("recommendations", [])
        
        # Classify seniority level for current role
        current_title = basic_info.get('headline', 'N/A')
        current_company = basic_info.get('current_company', 'N/A')
        seniority_level, seniority_score, seniority_reasoning = self.classify_seniority_level(current_title, current_company)
        
        prompt = f"""Please assess the following professional's O-1 visa eligibility based on LinkedIn data:

**BASIC INFORMATION:**
- Name: {basic_info.get('name', 'N/A')}
- Current Title: {current_title}
- **SENIORITY LEVEL: {seniority_level} (Score: {seniority_score}/10)**
- **Seniority Analysis: {seniority_reasoning}**
- Location: {basic_info.get('location', 'N/A')}
- Professional Summary: {basic_info.get('summary', 'N/A')[:300]}...
- LinkedIn Connections: {basic_info.get('connections_count', 0)}
- Current Company: {current_company}

**PROFESSIONAL EXPERIENCE (Focus on seniority progression and company prestige):**"""
        
        for i, exp in enumerate(experience[:5], 1):  # Limit to top 5 experiences
            # Analyze seniority for each role
            exp_title = exp.get('title', 'N/A')
            exp_company = exp.get('company', 'N/A')
            exp_seniority, exp_score, _ = self.classify_seniority_level(exp_title, exp_company)
            
            prompt += f"""
{i}. {exp_title} at {exp_company} - [{exp_seniority} Level: {exp_score}/10]
   Duration: {exp.get('start_date', 'N/A')} - {exp.get('end_date', 'Present')}
   Location: {exp.get('location', 'N/A')}
   Description: {exp.get('description', 'N/A')[:500]}..."""
        
        prompt += f"""

**EDUCATION:**"""
        for edu in education:
            prompt += f"""
- {edu.get('degree', 'N/A')} in {edu.get('field', 'N/A')} from {edu.get('school', 'N/A')} ({edu.get('start_year', 'N/A')}-{edu.get('end_year', 'N/A')})"""
        
        prompt += f"""

**SKILLS:**
{', '.join(skills[:20]) if skills else 'None listed'}

**ACCOMPLISHMENTS:**"""
        
        if accomplishments.get("publications"):
            prompt += f"""
Publications: {len(accomplishments['publications'])} publications including:"""
            for pub in accomplishments["publications"][:3]:
                prompt += f"\n- {pub}"
        
        if accomplishments.get("patents"):
            prompt += f"""
Patents: {len(accomplishments['patents'])} patents including:"""
            for patent in accomplishments["patents"][:3]:
                prompt += f"\n- {patent}"
        
        if accomplishments.get("awards"):
            prompt += f"""
Awards: {len(accomplishments['awards'])} awards including:"""
            for award in accomplishments["awards"][:3]:
                prompt += f"\n- {award}"
        
        if accomplishments.get("certifications"):
            prompt += f"""
Certifications: {', '.join(accomplishments['certifications'][:5])}"""
        
        if accomplishments.get("projects"):
            prompt += f"""
Notable Projects: {len(accomplishments['projects'])} projects"""
        
        prompt += f"""

**PROFESSIONAL NETWORK & RECOMMENDATIONS (Focus on network quality):**
- Total LinkedIn Connections: {basic_info.get('connections_count', 0)}
- Recommendations Received: {len(recommendations)}"""
        
        for i, rec in enumerate(recommendations[:3], 1):  # Limit to top 3 recommendations
            prompt += f"""
{i}. Recommendation from {rec.get('recommender', 'N/A')} ({rec.get('relationship', 'N/A')}):
   "{rec.get('text', 'N/A')[:200]}...\""""
        
        prompt += f"""

**PATENTS & CERTIFICATIONS (If available):**"""
        if accomplishments.get("patents"):
            for patent in accomplishments["patents"][:2]:
                if isinstance(patent, dict):
                    prompt += f"""
- Patent: {patent.get('title', 'N/A')} (Issued: {patent.get('date_issued', 'N/A')})"""
                else:
                    prompt += f"""
- Patent: {patent}"""
        
        if accomplishments.get("certifications"):
            for cert in accomplishments["certifications"][:3]:
                if isinstance(cert, dict):
                    prompt += f"""
- Certification: {cert.get('title', 'N/A')} from {cert.get('subtitle', 'N/A')}"""
                else:
                    prompt += f"""
- Certification: {cert}"""
        
        prompt += """

ASSESSMENT INSTRUCTIONS:
Focus on LinkedIn-visible indicators of extraordinary ability:
1. Senior/leadership titles (VP, Director, CTO, Founder, Principal)
2. Prestigious companies (FAANG, unicorns, Fortune 500, well-known startups)
3. Career advancement pattern (promotions, increasing responsibilities)
4. Professional network size and quality of recommendations
5. Technical expertise and industry certifications

Provide a realistic O-1 assessment based ONLY on what's visible in this LinkedIn profile."""
        
        return prompt
    
    def _create_fallback_assessment(self, error_message: str) -> Dict[str, Any]:
        """Create a fallback assessment when GPT fails."""
        return {
            "overall_score": 0.0,
            "criteria_scores": {
                "professional_seniority": 0.0,
                "company_prestige": 0.0,
                "career_progression": 0.0,
                "professional_network": 0.0,
                "skills_expertise": 0.0
            },
            "evidence": {
                "professional_seniority": [],
                "company_prestige": [],
                "career_progression": [],
                "professional_network": [],
                "skills_expertise": []
            },
            "strengths": [],
            "weaknesses": ["Assessment failed due to technical error"],
            "likelihood": "Unknown",
            "recommendation": f"Assessment could not be completed due to error: {error_message}",
            "reasoning": "Technical error prevented proper assessment",
            "error": error_message
        }
    
    async def test_connection(self) -> bool:
        """
        Test OpenAI API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {str(e)}")
            return False
