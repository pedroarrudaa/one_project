"""Configuration settings for the LinkedIn-based O-1 Visa Assessment System."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = (
        "sqlite:////Users/pedroarruda/Desktop/one/o1_visa_profiles.db"
    )
    
    # API Keys
    openai_api_key: str
    tavily_api_key: str  # For LinkedIn discovery only
    brightdata_api_key: str  # For LinkedIn scraping
    
    # Application
    debug: bool = True
    log_level: str = "INFO"
    
    # LinkedIn Discovery Settings
    linkedin_discovery_enabled: bool = True
    max_linkedin_search_results: int = 5
    
    # BrightData Settings
    brightdata_timeout: int = 300  # seconds (5 minutes)
    brightdata_retries: int = 3
    
    # GPT-4o-mini Settings
    gpt_model: str = "gpt-4o-mini"
    gpt_temperature: float = 0.3
    gpt_max_tokens: int = 2000
    
    # Processing Settings
    max_concurrent_profiles: int = 5
    processing_timeout: int = 300  # seconds per profile
    
    class Config:
        env_file = ".env"


settings = Settings()