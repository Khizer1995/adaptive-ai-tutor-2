from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class StudentProfile(BaseModel):
    # Basic Info
    student_id: str = Field(..., description="Unique ID for the student")
    name: str
    
    # Educational Context
    knowledge_level: str = "beginner"  # Options: beginner, intermediate, advanced
    current_topic: Optional[str] = None
    completed_topics: List[str] = []
    
    # Behavioral Metrics (For the Monitor Agent)
    frustration_level: int = Field(default=0, ge=0, le=10) # Scale 0-10
    engagement_score: int = Field(default=5, ge=0, le=10)
    
    # Preferences (For Monish's RAG & Khizer's Persona)
    learning_style: str = "balanced" # Options: visual, text-heavy, Socratic
    
    # Metadata
    last_active: datetime = Field(default_factory=datetime.now)

    class Config:
        # This allows the model to be easily updated
        validate_assignment = True