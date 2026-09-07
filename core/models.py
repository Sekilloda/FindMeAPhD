from pydantic import BaseModel, Field
from typing import List, Optional

# --- Reference Document Schemas ---

class PhysicsInterests(BaseModel):
    topics: List[str] = Field(default_factory=list, description="Core topics of interest (e.g., Quantum Information, String Theory)")
    preferences_summary: str = Field(..., description="A detailed natural language summary of the user's physics preferences")

class LogisticsPreferences(BaseModel):
    preferred_regions: List[str] = Field(default_factory=list, description="Geographical regions the user prefers")
    travel_ease_importance: int = Field(..., ge=1, le=10, description="1-10 rating of how important easy travel is")
    max_duration_weeks: Optional[int] = Field(None, description="Maximum duration in weeks for summer/winter schools")

class FinancialPreferences(BaseModel):
    min_adjusted_compensation: Optional[float] = Field(None, description="Minimum cost-of-living adjusted compensation desired (in USD/EUR eq)")

class ReferenceDocument(BaseModel):
    physics_interests: PhysicsInterests
    logistics_preferences: LogisticsPreferences
    financial_preferences: FinancialPreferences
    
# --- Database Schemas (Sites & Offerings) ---

class SearchInstruction(BaseModel):
    site_url: str = Field(..., description="URL of the site to search")
    scraping_method: str = Field(..., description="Instructions on how to scrape/search (e.g., 'Google site:', 'XPath //div[@class=job]')")
    target_type: str = Field(..., description="'course' or 'phd'")

class Offering(BaseModel):
    id: Optional[int] = None
    title: str
    institution: str
    location: str
    offering_type: str = Field(..., description="'course' or 'phd'")
    url: str
    description: str
    
    # Optional fields to be populated by Hunter-Gatherer or Graders
    duration_weeks: Optional[int] = None
    compensation_raw: Optional[str] = None
    topics_mentioned: List[str] = Field(default_factory=list)
    
    # Grading fields
    score_geography: Optional[float] = None
    score_academic: Optional[float] = None
    score_financial: Optional[float] = None
    total_score: Optional[float] = None
