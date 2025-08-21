"""GPT-4o-mini Intelligent Scoring Service for O-1 Visa Assessment (V1 - Legacy)."""

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
    
    def analyze_social_influence(self, profile_data: Dict[str, Any]) -> Tuple[int, str, Dict[str, int]]:
        """
        Analyze social media influence - LinkedIn only (simplified).
        
        Args:
            profile_data: Dictionary containing LinkedIn data only
            
        Returns:
            Tuple of (influence_score_1_to_10, analysis_summary, follower_breakdown)
        """
        basic_info = profile_data.get("basic_info", {})
        
        # Extract LinkedIn follower counts only
        linkedin_followers = basic_info.get("followers_count", 0) or 0
        linkedin_connections = basic_info.get("connections_count", 0) or 0
        
        followers = {
            "linkedin_followers": linkedin_followers,
            "linkedin_connections": linkedin_connections
        }
        
        # LinkedIn-only reach calculation with logarithmic scaling
        reach_raw = linkedin_followers + linkedin_connections
        
        # Use logarithmic scaling adjusted for LinkedIn-only
        import math
        if reach_raw > 0:
            # Adjusted formula for LinkedIn-only: more generous scaling
            logarithmic_reach_score = min(10, max(0, 1.5 + 2.5 * math.log10(reach_raw + 50)))
        else:
            logarithmic_reach_score = 0
        
        total_social_reach = reach_raw
        social_reach_score = logarithmic_reach_score
        
        # Scoring based on social reach (1-10 scale)
        if total_social_reach >= 50000:  # 50K+ = Influencer level
            score = 10
            level = "Major Influencer"
        elif total_social_reach >= 25000:  # 25K+ = Strong influence
            score = 9
            level = "Strong Influencer"
        elif total_social_reach >= 10000:  # 10K+ = Notable influence
            score = 8
            level = "Notable Influence"
        elif total_social_reach >= 5000:   # 5K+ = Good influence
            score = 7
            level = "Good Influence"
        elif total_social_reach >= 2500:   # 2.5K+ = Moderate influence
            score = 6
            level = "Moderate Influence"
        elif total_social_reach >= 1000:   # 1K+ = Some influence
            score = 5
            level = "Some Influence"
        elif total_social_reach >= 500:    # 500+ = Limited influence
            score = 4
            level = "Limited Influence"
        elif total_social_reach >= 100:    # 100+ = Minimal influence
            score = 3
            level = "Minimal Influence"
        elif total_social_reach > 0:       # Some presence
            score = 2
            level = "Basic Presence"
        else:                               # No social presence
            score = 1
            level = "No Social Presence"
        
        # Create simplified analysis - LinkedIn only
        analysis = f"{level} - LinkedIn: {linkedin_connections:,} connections + {linkedin_followers:,} followers = {total_social_reach:,} total reach (Log Score: {social_reach_score:.1f}/10)"
        
        # Return the logarithmic score for better scaling
        return int(social_reach_score), analysis, followers
    
    # GitHub impact analysis completely removed
    
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
5. **Social Influence & Recognition**: IMPORTANT - Use the social influence analysis provided (LinkedIn followers, reach)
6. **Technical Impact & Open Source**: Based on LinkedIn projects, publications, and technical achievements

**SENIORITY LEVEL SCORING (Most Important Factor):**
- **VP Level (9-10 points)**: CTO, CEO, Founder, VP, Chief Officer, Head of Department
- **Executive Level (7-8 points)**: Director, Principal, Distinguished Engineer, Engineering Manager
- **Senior Level (4-6 points)**: Senior Engineer, Staff Engineer, Senior Specialist, Senior Consultant  
- **Junior Level (1-3 points)**: Engineer, Analyst, Coordinator, Associate, Entry-level roles

**EDUCATION PRESTIGE BONUS (Important Factor):**
- **Top-Tier Universities (+2 points)**: Stanford, MIT, Harvard, Carnegie Mellon, UC Berkeley, Caltech, Princeton, Yale
- **Prestigious Programs (+1.5 points)**: Ivy League, Top 20 CS programs, renowned research institutions
- **Research Experience (+1 point)**: PhD programs, research positions, academic publications

**SOCIAL INFLUENCE SCORING (Recognition Factor):**
- **Major Influencer (10 points)**: 50K+ total reach - Industry thought leader level
- **Strong Influencer (9 points)**: 25K+ total reach - Significant industry presence
- **Notable Influence (8 points)**: 10K+ total reach - Well-known in field
- **Good Influence (7 points)**: 5K+ total reach - Established professional network
- **Moderate Influence (6 points)**: 2.5K+ total reach - Growing influence
- **Some Influence (5 points)**: 1K+ total reach - Active professional presence
- **Limited Influence (1-4 points)**: <1K total reach - Basic or minimal presence

**GITHUB IMPACT SCORING (Technical Excellence Factor):**
- **GitHub Superstar (9-10 points)**: 5K+ stars, 1K+ followers - Major open source contributor
- **Major Contributor (8 points)**: 1K+ stars, 500+ followers - Significant technical impact
- **Notable Developer (7 points)**: 500+ stars, 100+ followers - Well-recognized projects
- **Active Developer (6 points)**: 100+ stars, 50+ followers - Quality contributions
- **Regular User (5 points)**: 10+ stars, active repos - Consistent development
- **Casual User (1-4 points)**: <10 stars or minimal activity - Basic presence

**PATENTS & INTELLECTUAL PROPERTY SCORING (High Impact Factor):**
- **Multiple Patents (9-10 points)**: 5+ patents - Demonstrates innovation and extraordinary ability
- **Significant Patents (7-8 points)**: 2-4 patents - Strong technical innovation
- **Single Patent (5-6 points)**: 1 patent - Notable technical achievement
- **No Patents (1-2 points)**: No patent activity

**AWARDS & RECOGNITIONS SCORING (Recognition Factor):**
- **Major Awards (9-10 points)**: Industry awards, national recognition, prestigious honors
- **Professional Awards (7-8 points)**: Company awards, professional society recognition
- **Academic Awards (5-6 points)**: University honors, research awards, scholarships
- **Certifications (3-4 points)**: Professional certifications, technical credentials
- **No Awards (1-2 points)**: No visible recognition

**MEMBERSHIPS & PROFESSIONAL INVOLVEMENT SCORING (Industry Standing Factor):**
- **Leadership Roles (9-10 points)**: Board member, committee chair, organization leader
- **Active Member (7-8 points)**: Professional societies, technical committees, advisory roles
- **Basic Membership (5-6 points)**: Member of professional organizations, industry groups
- **Volunteer Work (3-4 points)**: Community involvement, non-profit work
- **No Involvement (1-2 points)**: No visible professional involvement

Assess the CORE 5 criteria on a scale of 1-10, then apply BONUS POINTS for exceptional achievements:

**CORE CRITERIA (Base Score 1-10):**
- **Professional Seniority**: Use the provided seniority analysis - this is pre-calculated and crucial. APPLY EDUCATION BONUS for prestigious institutions.
- **Company Prestige**: Google, Meta, Apple, Microsoft, OpenAI, top startups, well-known brands
- **Career Progression**: Multiple promotions, increasing scope, job title evolution. CONSIDER internships at top universities as strong progression indicators.
- **Professional Network**: 500+ connections, recommendations from executives/leaders
- **Technical Impact & Open Source**: Based on LinkedIn projects, publications, technical skills, and achievements

**BONUS FACTORS (Add to base score, max +3.0 total bonus):**
- **Patents & IP Bonus (+0.5 to +1.5)**: Each patent adds significant value - patents are CRITICAL evidence of extraordinary ability
- **Awards & Recognition Bonus (+0.2 to +1.0)**: Industry awards, honors, certifications show peer recognition
- **Publications Bonus (+0.2 to +0.8)**: Academic/technical publications demonstrate thought leadership
- **Projects & Innovation Bonus (+0.1 to +0.5)**: Technical projects show practical expertise
- **Specialized Education Bonus (+0.1 to +0.3)**: Advanced courses, specialized training
- **Volunteer Leadership Bonus (+0.1 to +0.3)**: Leadership roles, community involvement

**HYBRID SCORING METHODOLOGY (V1 Enhanced with V2 Logic):**
1. Calculate base score from 4 core criteria using WEIGHTED AVERAGE:
   - Professional Seniority: 30% weight (most important)
   - Company Prestige: 25% weight  
   - Career Progression: 25% weight
   - Professional Network: 20% weight (LinkedIn connections/followers)

2. Apply BONUS POINTS for exceptional achievements (max +3.0 total):
   - Patents: +1.0 to +1.5 per patent (CRITICAL for O-1)
   - Awards/Honors: +0.3 to +1.0 depending on prestige
   - Publications: +0.2 to +0.8 depending on venue
   - Technical Projects: +0.1 to +0.5 for innovation
   - Specialized Courses: +0.1 to +0.3 for advanced training
   - Volunteer Leadership: +0.1 to +0.3 for community impact

3. MINIMUM SCORE GUARANTEES:
   - Candidates with US Patents: minimum 5.5/10
   - Prestigious education (Stanford, MIT, etc.): minimum 5.0/10
   - Multiple awards + strong network: minimum 5.0/10

4. Final score = min(10.0, weighted_base_score + total_bonus)

**IMPORTANT EDUCATION CONSIDERATIONS:**
- Internships or research positions at Stanford, MIT, Harvard, Carnegie Mellon, UC Berkeley, Brown University, IISc should significantly boost scores
- Academic research experience, even at junior levels, demonstrates extraordinary ability potential
- Publications, patents, or projects from prestigious institutions carry high weight
- Consider the prestige of educational institutions when evaluating overall potential
- Research leadership roles (leading labs, research divisions) indicate exceptional ability
- Graduate programs at top universities (MS, PhD) show advanced expertise

Respond in JSON format with the following HYBRID structure:
{
  "overall_score": float (1-10),
  "base_score": float (1-10),
  "bonus_points": float (0-3.0),
  "scoring_method": "hybrid_v1_enhanced",
  "criteria_scores": {
    "professional_seniority": float (1-10),
    "company_prestige": float (1-10),
    "career_progression": float (1-10),
    "professional_network": float (1-10)
  },
  "bonus_factors": {
    "patents_ip_bonus": float (0-1.5),
    "awards_recognition_bonus": float (0-1.0),
    "publications_bonus": float (0-0.8),
    "projects_innovation_bonus": float (0-0.5),
    "specialized_education_bonus": float (0-0.3),
    "volunteer_leadership_bonus": float (0-0.3)
  },
  "weighted_breakdown": {
    "seniority_weighted": float (criteria_score * 0.30),
    "prestige_weighted": float (criteria_score * 0.25),
    "progression_weighted": float (criteria_score * 0.25),
    "network_weighted": float (criteria_score * 0.20)
  },
  "evidence": {
    "professional_seniority": [list of specific evidence from LinkedIn],
    "company_prestige": [list of specific evidence from LinkedIn],
    "career_progression": [list of specific evidence from LinkedIn],
    "professional_network": [list of specific evidence from LinkedIn],

    "bonus_achievements": [list of patents, awards, publications, projects that earned bonus points]
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
        
        # Add V2 hybrid enhancements - company tier resolution
        company_tier = self._resolve_company_tier(current_company)
        tier_scores = {"A": 9.0, "A-": 8.0, "B": 6.5, "C": 5.0, "D": 3.0}
        company_prestige_score_v2 = tier_scores.get(company_tier, 3.0)
        
        # Analyze social influence
        influence_score, influence_analysis, follower_breakdown = self.analyze_social_influence(profile_data)
        
        # GitHub analysis completely removed - focusing on LinkedIn data only
        
        prompt = f"""Please assess the following professional's O-1 visa eligibility using HYBRID V1+V2 methodology:

**BASIC INFORMATION:**
- Name: {basic_info.get('name', 'N/A')}
- Current Title: {current_title}
- **SENIORITY LEVEL: {seniority_level} (Score: {seniority_score}/10)**
- **Seniority Analysis: {seniority_reasoning}**
- **SOCIAL INFLUENCE: {influence_analysis} (Score: {influence_score}/10)**
- Location: {basic_info.get('location', 'N/A')}
- Professional Summary: {basic_info.get('summary', 'N/A')[:300]}...
- Current Company: {current_company}

**V2 HYBRID ENHANCEMENTS:**
- **Company Tier: {company_tier}** (Prestige Score: {company_prestige_score_v2:.1f}/10)
- **Social Reach (V2 Log Scale): {influence_score}/10** (more balanced than linear scaling)
- **Enhanced Data**: Now includes projects, courses, volunteer experience, bio links

**LINKEDIN PROFESSIONAL NETWORK:**
- LinkedIn Connections: {follower_breakdown['linkedin_connections']:,}
- LinkedIn Followers: {follower_breakdown['linkedin_followers']:,}
- **Total LinkedIn Reach: {follower_breakdown['linkedin_connections'] + follower_breakdown['linkedin_followers']:,}**
- **Network Analysis: {influence_analysis}**

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

**EDUCATION (CRITICAL for O-1 Assessment):**"""
        
        # Analyze education prestige
        prestigious_institutions = []
        for edu in education:
            school = edu.get('school', '')
            degree = edu.get('degree', '')
            field = edu.get('field', '')
            
            # Check for top-tier institutions
            top_tier_keywords = [
                'stanford', 'mit', 'harvard', 'carnegie mellon', 'uc berkeley', 'caltech', 'princeton', 'yale',
                'brown university', 'columbia', 'cornell', 'dartmouth', 'university of pennsylvania', 'upenn',
                'georgia tech', 'university of washington', 'university of michigan', 'ucla', 'usc',
                'indian institute of science', 'iisc', 'iit', 'indian institute of technology'
            ]
            is_top_tier = any(keyword in school.lower() for keyword in top_tier_keywords)
            
            if is_top_tier:
                prestigious_institutions.append(school)
            
            prestige_indicator = "TOP-TIER INSTITUTION" if is_top_tier else ""
            prompt += f"""
- {degree} in {field} from {school} ({edu.get('start_year', 'N/A')}-{edu.get('end_year', 'N/A')}) {prestige_indicator}"""
        
        if prestigious_institutions:
            prompt += f"""

**PRESTIGIOUS EDUCATION BONUS: This candidate has studied/worked at {', '.join(prestigious_institutions)} - this significantly enhances O-1 eligibility even for junior-level professionals.**"""
        
        prompt += f"""

**SKILLS:**
{', '.join(str(skill) for skill in skills[:20]) if skills else 'None listed'}

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
            cert_names = []
            for cert in accomplishments['certifications'][:5]:
                if isinstance(cert, dict):
                    cert_names.append(cert.get('title', 'Unknown Certification'))
                else:
                    cert_names.append(str(cert))
            prompt += f"""
Certifications: {', '.join(cert_names)}"""
        
        # Enhanced project analysis
        projects = accomplishments.get("projects", [])
        if projects:
            prompt += f"""
Technical Projects ({len(projects)} total):"""
            for project in projects[:3]:
                if isinstance(project, dict):
                    title = project.get('title', 'Unknown Project')
                    description = project.get('description', '')[:200]
                    dates = f"{project.get('start_date', 'N/A')} - {project.get('end_date', 'N/A')}"
                    prompt += f"""
- Project: {title} ({dates})
  Description: {description}..."""
                else:
                    prompt += f"""
- Project: {str(project)}"""
        
        # Add courses (specialized education)
        courses = accomplishments.get("courses", [])
        if courses:
            prompt += f"""

Specialized Courses ({len(courses)} total):"""
            for course in courses[:5]:
                if isinstance(course, dict):
                    title = course.get('title', 'Unknown Course')
                    subtitle = course.get('subtitle', '')
                    prompt += f"""
- Course: {title} ({subtitle})"""
                else:
                    prompt += f"""
- Course: {str(course)}"""
        
        # Add volunteer experience (shows leadership and involvement)
        volunteer = accomplishments.get("volunteer_experience", [])
        if volunteer:
            prompt += f"""

Volunteer Experience ({len(volunteer)} total):"""
            for vol in volunteer[:3]:
                if isinstance(vol, dict):
                    title = vol.get('title', 'Unknown Role')
                    subtitle = vol.get('subtitle', '')
                    info = vol.get('info', '')
                    prompt += f"""
- Volunteer: {title} at {subtitle} - {info}"""
                else:
                    prompt += f"""
- Volunteer: {str(vol)}"""
        
        # Add bio links (portfolio, websites)
        bio_links = accomplishments.get("bio_links", [])
        if bio_links:
            prompt += f"""

Portfolio & Bio Links ({len(bio_links)} total):"""
            for link in bio_links[:3]:
                if isinstance(link, dict):
                    title = link.get('title', 'Link')
                    url = link.get('link', '')
                    prompt += f"""
- {title}: {url}"""
                else:
                    prompt += f"""
- Link: {str(link)}"""
        
        prompt += f"""

**PROFESSIONAL NETWORK & RECOMMENDATIONS (Focus on network quality):**
- Total LinkedIn Connections: {basic_info.get('connections_count', 0)}
- Recommendations Received: {len(recommendations)}"""
        
        for i, rec in enumerate(recommendations[:3], 1):  # Limit to top 3 recommendations
            prompt += f"""
{i}. Recommendation from {rec.get('recommender', 'N/A')} ({rec.get('relationship', 'N/A')}):
   "{rec.get('text', 'N/A')[:200]}...\""""
        
        prompt += f"""

**PATENTS & INTELLECTUAL PROPERTY (CRITICAL for O-1):**"""
        patents = accomplishments.get("patents", [])
        if patents:
            prompt += f"""
Patents ({len(patents)} total):"""
            for patent in patents[:3]:  # Show top 3
                if isinstance(patent, dict):
                    prompt += f"""
- Patent: {patent.get('title', 'N/A')} (US Patent {patent.get('patents_id', 'N/A')}, Issued: {patent.get('date_issued', 'N/A')})"""
                else:
                    prompt += f"""
- Patent: {patent}"""
        else:
            prompt += """
No patents found."""

        prompt += f"""

**AWARDS & RECOGNITIONS (IMPORTANT for O-1):**"""
        awards = accomplishments.get("awards", [])
        certifications = accomplishments.get("certifications", [])
        
        if awards:
            prompt += f"""
Honors and Awards ({len(awards)} total):"""
            for award in awards[:3]:
                award_text = award if isinstance(award, str) else str(award)
                prompt += f"""
- Award: {award_text}"""
        
        if certifications:
            prompt += f"""
Professional Certifications ({len(certifications)} total):"""
            for cert in certifications[:3]:
                if isinstance(cert, dict):
                    prompt += f"""
- Certification: {cert.get('title', 'N/A')} from {cert.get('subtitle', 'N/A')} (Issued: {cert.get('meta', 'N/A')})"""
                else:
                    prompt += f"""
- Certification: {cert}"""
        
        if not awards and not certifications:
            prompt += """
No awards or certifications found."""

        prompt += f"""

**MEMBERSHIPS & PROFESSIONAL INVOLVEMENT (IMPORTANT for O-1):**"""
        memberships = accomplishments.get("memberships", [])
        professional_memberships = accomplishments.get("professional_memberships", [])
        
        if memberships:
            prompt += f"""
Organizations and Memberships ({len(memberships)} total):"""
            for membership in memberships[:3]:
                membership_text = membership if isinstance(membership, str) else str(membership)
                prompt += f"""
- Membership: {membership_text}"""
        
        if professional_memberships:
            prompt += f"""
Professional Memberships ({len(professional_memberships)} total):"""
            for membership in professional_memberships[:3]:
                membership_text = membership if isinstance(membership, str) else str(membership)
                prompt += f"""
- Professional Membership: {membership_text}"""
        
        if not memberships and not professional_memberships:
            prompt += """
No professional memberships found."""
        
        prompt += """

ASSESSMENT INSTRUCTIONS:
Focus on LinkedIn-visible indicators of extraordinary ability:
1. Senior/leadership titles (VP, Director, CTO, Founder, Principal)
2. Prestigious companies (FAANG, unicorns, Fortune 500, well-known startups)
3. Career advancement pattern (promotions, increasing responsibilities)
4. Professional network size and quality of recommendations
5. Technical expertise and industry certifications

**SPECIAL CONSIDERATIONS FOR RESEARCH PROFESSIONALS:**
- Research leadership roles (leading labs, research divisions) should score highly for career progression
- Strong LinkedIn networking (1K+ followers, 500+ connections) indicates industry recognition
- Graduate studies at prestigious institutions demonstrate advanced expertise
- Research positions at top universities/institutes show extraordinary academic ability
- Technical contributions in cutting-edge fields (3D Vision, ML, AI) demonstrate specialized expertise

**SCORING ADJUSTMENTS:**
- If candidate has 1K+ LinkedIn followers + prestigious education + research leadership → minimum 6.0 score
- Research positions at Brown, IISc, or similar institutions should boost professional_seniority to at least 5.0
- Strong social presence (1K+ followers) should boost professional_network to at least 7.0

Provide a realistic O-1 assessment based ONLY on what's visible in this LinkedIn profile."""
        
        return prompt
    
    def _create_fallback_assessment(self, error_message: str) -> Dict[str, Any]:
        """Create a fallback assessment when GPT fails."""
        return {
            "overall_score": 0.0,
            "base_score": 0.0,
            "bonus_points": 0.0,
            "criteria_scores": {
                "professional_seniority": 0.0,
                "company_prestige": 0.0,
                "career_progression": 0.0,
                "professional_network": 0.0,
                "technical_impact": 0.0
            },
            "bonus_factors": {
                "patents_ip_bonus": 0.0,
                "awards_recognition_bonus": 0.0,
                "publications_bonus": 0.0,
                "projects_innovation_bonus": 0.0,
                "specialized_education_bonus": 0.0,
                "volunteer_leadership_bonus": 0.0
            },
            "evidence": {
                "professional_seniority": [],
                "company_prestige": [],
                "career_progression": [],
                "professional_network": [],
                "technical_impact": [],
                "bonus_achievements": []
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

    def _resolve_company_tier(self, company_name: str) -> str:
        """Resolve company tier based on company name (integrated from V2)."""
        if not company_name or company_name == "N/A":
            return "D"
        
        company_lower = company_name.lower()
        
        # Tier A: FAANG + Top Tech
        tier_a = ["google", "apple", "meta", "facebook", "amazon", "netflix", "microsoft", "nvidia", "openai", "anthropic"]
        if any(company in company_lower for company in tier_a):
            return "A"
        
        # Tier A-: High-tier tech companies
        tier_a_minus = ["uber", "airbnb", "stripe", "spotify", "twitter", "x corp", "tesla", "spacex", "palantir"]
        if any(company in company_lower for company in tier_a_minus):
            return "A-"
        
        # Tier B: Established tech companies
        tier_b = ["oracle", "salesforce", "adobe", "intel", "ibm", "cisco", "vmware", "snowflake", "databricks", "atlassian"]
        if any(company in company_lower for company in tier_b):
            return "B"
        
        # Tier C: Mid-tier companies
        tier_c = ["startup", "consulting", "accenture", "deloitte", "pwc", "kpmg", "ey"]
        if any(company in company_lower for company in tier_c):
            return "C"
        
        # Default to D for unknown companies
        return "D"
