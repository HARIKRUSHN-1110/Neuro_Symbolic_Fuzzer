# src/core/models.py
from pydantic import BaseModel, Field #type: ignore
from typing import Optional

class ScenarioParameters(BaseModel):
    """
    Defines the base parameters of a scenario. 
    The LLM will generate this, and the Simulator will consume it.
    """
    scenario_name: str = Field(..., description="Unique name for the file")
    ego_speed: float = Field(..., ge=0, le=150, description="Speed of the autonomous car in km/h")
    target_speed: float = Field(..., ge=0, le=150, description="Speed of the adversary car in km/h")
    cut_in_distance: float = Field(..., ge=5, le=100, description="Distance (m) before target cuts in")
    map_name: str = "e6mini"
    
class SimulationResult(BaseModel):
    """
    The output after running Esmini.
    """
    is_collision: bool
    min_ttc: float = Field(..., description="Minimum Time To Collision recorded")
    min_distance: float = Field(..., description="Minimum distance recorded between cars")
    log_path: str