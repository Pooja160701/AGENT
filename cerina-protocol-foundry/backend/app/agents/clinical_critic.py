# backend/app/agents/clinical_critic.py
from .base_agent import BaseAgent
from ..llm_client import call_llm
import time

class ClinicalCritic(BaseAgent):
    def run(self, state: dict) -> dict:
        draft = state.get("current_draft_text", "")
        prompt = f"Provide a clinical critique of this CBT exercise focusing on empathy, clarity, and clinical appropriateness. Suggest a one-paragraph revision:\n\n{draft}"
        llm_out = call_llm(prompt)
        state["critic_text"] = llm_out.strip()
        # also propose a revision field
        rev_prompt = f"Revise the draft to improve empathy and clarity:\n\n{draft}"
        revised = call_llm(rev_prompt)
        state["proposed_revision"] = revised.strip()
        self.orchestrator.save_checkpoint(state["run_id"], self.name, state, "Clinical critique & revision")
        time.sleep(0.03)
        return state