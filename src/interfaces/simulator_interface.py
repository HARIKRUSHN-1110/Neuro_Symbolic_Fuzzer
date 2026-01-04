# src/interfaces/simulator_interface.py
from abc import ABC, abstractmethod
from src.core.models import ScenarioParameters, SimulationResult

class ISimulator(ABC):
    """
    Abstract Base Class ensuring all simulators behave the same way.
    """
    
    @abstractmethod
    async def run_scenario(self, params: ScenarioParameters) -> SimulationResult:
        """
        Takes parameters, generates a file, runs simulation, returns result.
        """
        pass