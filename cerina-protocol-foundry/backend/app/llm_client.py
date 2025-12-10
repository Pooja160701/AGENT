# backend/app/llm_client.py
import os
import re
from typing import Optional

# read mode from config env or fallback
LLM_MODE = os.environ.get("LLM_MODE", "mock").lower()

def simple_summary_from_prompt(prompt: str) -> str:
    """
    Rule-based deterministic short summary builder for mock mode.
    Looks for 'Intent:' and 'Final draft:' blocks (as composed by main.py) and
    produces a 3-line human-friendly summary.
    """
    intent = ""
    draft = ""

    # try to extract Intent: <text>
    m_intent = re.search(r"Intent:\s*(.+?)(?:\\n|$)", prompt, re.IGNORECASE)
    if m_intent:
        intent = m_intent.group(1).strip()

    # try to extract Final draft: block (everything after 'Final draft:' or 'Final draft\\n')
    m_draft = re.search(r"Final draft:\s*(.+)$", prompt, re.IGNORECASE | re.DOTALL)
    if m_draft:
        draft = m_draft.group(1).strip()
    else:
        # fallback: try to use the whole prompt if no explicit draft block
        draft = prompt.strip()

    # make summary sentences (simple heuristics)
    # 1. One-line intent summary
    intent_line = f"Intent: {intent}" if intent else "Intent provided."
    # 2. One-line summary of what the exercise does
    exercise_line = "This CBT exercise helps with sleep by teaching brief practical steps."
    # Attempt to personalize using draft if it looks like an exercise
    if len(draft) > 20:
        # use first sentence or 120 chars
        first_sent = re.split(r"[\\n\\.]+", draft.strip())[0]
        snippet = (first_sent[:140] + ("..." if len(first_sent) > 140 else "")).strip()
        exercise_line = f"Draft excerpt: {snippet}"
    # 3. One-line user-facing instruction
    instruction_line = "Use 1–2 minutes nightly to practice the breathing and thought-reframing steps."

    return f"{exercise_line}\\n{instruction_line}\\n{intent_line}"

def call_llm(prompt: str, max_tokens: int = 256, model: Optional[str] = None) -> str:
    """
    Minimal LLM client wrapper.
    - If LLM_MODE==mock: returns helpful deterministic text (no ellipses).
    - If LLM_MODE==ollama or transformers: tries to call the real model (keeps your previous logic).
    """

    mode = LLM_MODE

    # MOCK mode: return deterministic readable outputs (no "...")
    if mode == "mock":
        # If prompt asks explicitly for a short human-friendly summary, synthesize it:
        if re.search(r"short\s*\(3-5 line\)|Produce a short|human-friendly summary", prompt, re.IGNORECASE):
            return simple_summary_from_prompt(prompt)
        # Otherwise return the full prompt as a mock response (no truncation)
        # but format it a bit to feel like a generated output
        short = prompt.strip()
        # Avoid returning a huge wall of text — return up to a reasonable size
        if len(short) > 1500:
            short = short[:1500].rstrip() + "\n\n[truncated]"
        return f"[MOCK] Generated response for prompt:\\n{short}"

    # OLLAMA mode (if you set up ollama) — preserve existing logic if present:
    if mode == "ollama":
        try:
            # lazy import to avoid depending on ollama package until needed
            from ollama import Ollama
            client = Ollama()
            model_to_use = model or os.environ.get("OLLAMA_MODEL", "orca-mini")
            resp = client.generate(model_to_use, prompt)
            return resp["text"] if isinstance(resp, dict) and "text" in resp else str(resp)
        except Exception as e:
            return f"[error: ollama unavailable] {e}"

    # TRANSFORMERS mode (local transformers) — preserve previous behavior if configured
    if mode == "transformers":
        try:
            # only import transformers when needed
            from transformers import pipeline
            model_name = model or os.environ.get("TRANSFORMER_MODEL", "gpt2")
            gen = pipeline("text-generation", model=model_name)
            out = gen(prompt, max_length=max_tokens, do_sample=False)[0]["generated_text"]
            return out
        except Exception as e:
            return f"[error: transformers unavailable] {e}"

    # Default fallback: echo prompt (safe)
    return f"[MOCK] Generated response for prompt:\\n{prompt}"