# backend/app/agents/draftsman.py
from .base_agent import BaseAgent
from ..llm_client import call_llm
import time

class Draftsman(BaseAgent):
    def run(self, state: dict) -> dict:
        intent = state.get("intent_text", "Create a CBT exercise")
        prompt = f"Create a short CBT exercise based on this intent:\n\n{intent}\n\nOutput a concise step-by-step exercise."
        llm_out = call_llm(prompt)
        draft_text = llm_out.strip()
        state["current_draft_text"] = draft_text
        versions = state.get("draft_versions", [])
        versions.append({"version": len(versions)+1, "text": draft_text})
        state["draft_versions"] = versions
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        self.orchestrator.save_checkpoint(state["run_id"], self.name, state, f"Draft created v{len(versions)}")
        time.sleep(0.05)
        return state