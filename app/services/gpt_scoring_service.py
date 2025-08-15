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
1. **Professional Seniority**: Senior roles, leadership positions, C-level titles, founding roles
2. **Company Prestige**: Work at top-tier companies (FAANG, unicorns, Fortune 500, prestigious startups)
3. **Career Progression**: Rapid advancement, increasing responsibilities, salary progression indicators
4. **Professional Network**: High connection count, recommendations from senior professionals
5. **Skills & Expertise**: Specialized skills, certifications, technical expertise relevant to field

Assess each criterion on a scale of 1-10 based on what's visible in LinkedIn:
- **Professional Seniority**: VP, Director, CTO, Founder, Principal, Senior titles
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
        
        prompt = f"""Please assess the following professional's O-1 visa eligibility based on LinkedIn data:

**BASIC INFORMATION:**
- Name: {basic_info.get('name', 'N/A')}
- Current Title: {basic_info.get('headline', 'N/A')}
- Location: {basic_info.get('location', 'N/A')}
- Professional Summary: {basic_info.get('summary', 'N/A')[:300]}...
- LinkedIn Connections: {basic_info.get('connections_count', 0)}
- Current Company: {basic_info.get('current_company', 'N/A')}

**PROFESSIONAL EXPERIENCE (Focus on seniority and company prestige):**"""
        
        for i, exp in enumerate(experience[:5], 1):  # Limit to top 5 experiences
            prompt += f"""
{i}. {exp.get('title', 'N/A')} at {exp.get('company', 'N/A')}
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
