# backend/app/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict

class BaseAgent(ABC):
    def __init__(self, name: str, orchestrator):
        self.name = name
        self.orchestrator = orchestrator

    @abstractmethod
    def run(self, state: Dict) -> Dict:
        """
        Accepts shared state, returns updated state.
        Should call orchestrator.save_checkpoint(...) to persist.
        """
        pass