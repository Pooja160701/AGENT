# backend/app/agents/safety_guardian.py
from .base_agent import BaseAgent
from ..llm_client import call_llm
import time

class SafetyGuardian(BaseAgent):
    def run(self, state: dict) -> dict:
        draft = state.get("current_draft_text", "")
        prompt = f"Check the following draft for potential safety issues (self-harm, medical advice, instructions to harm):\n\n{draft}\n\nReturn a short safety summary."
        llm_out = call_llm(prompt)
        flags = []
        lower = draft.lower()
        if "suicide" in lower or "self-harm" in lower:
            flags.append("possible self-harm")
        state["safety_flags"] = flags
        state["safety_check_text"] = llm_out.strip()
        state["safety_score"] = 0.95 if not flags else 0.2
        self.orchestrator.save_checkpoint(state["run_id"], self.name, state, f"Safety result: {flags}")
        time.sleep(0.03)
        return state