# backend/app/llm_client.py
import os
from .config import LLM_MODE, OLLAMA_MODEL, OLLAMA_HOST

def call_llm(prompt: str, system: str = None, max_tokens: int = 512) -> str:
    """
    Unified LLM entry point. Returns string responses.
    Modes supported: ollama, transformers, mock
    """
    mode = (LLM_MODE or "mock").lower()
    if mode == "ollama":
        return _call_ollama(prompt, system=system, max_tokens=max_tokens)
    elif mode == "transformers":
        return _call_transformers(prompt, max_tokens=max_tokens)
    else:
        return _call_mock(prompt)

# --------- Ollama mode ----------
def _call_ollama(prompt: str, system: str = None, max_tokens: int = 512) -> str:
    # Try python client first, else CLI fallback
    try:
        import ollama
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = ollama.chat(model=OLLAMA_MODEL, messages=messages)
        # adapt to possible resp structures
        if isinstance(resp, dict):
            if "message" in resp and isinstance(resp["message"], dict) and "content" in resp["message"]:
                return resp["message"]["content"]
            if "choices" in resp and len(resp["choices"]) > 0:
                try:
                    return resp["choices"][0]["message"]["content"]
                except:
                    return str(resp)
        return str(resp)
    except Exception as e:
        # CLI fallback
        try:
            import subprocess, json, shlex, tempfile
            # some ollama CLI versions accept `ollama chat <model>` with stdin messages
            cmd = f"ollama --json chat {OLLAMA_MODEL}"
            proc = subprocess.Popen(shlex.split(cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            payload = {"messages":[{"role":"user","content":prompt}]}
            out, err = proc.communicate(input=str(payload), timeout=30)
            if out:
                return out.strip()
            return f"[ollama cli error] {err}"
        except Exception as e2:
            return f"[ollama error] {e} / {e2}"

# --------- Transformers mode (local HF) ----------
def _call_transformers(prompt: str, max_tokens: int = 512) -> str:
    try:
        from transformers import pipeline
        # NOTE: change model to a local one you have downloaded. gpt2 is a tiny example.
        generator = pipeline("text-generation", model="gpt2")
        out = generator(prompt, max_length=len(prompt.split()) + 100, do_sample=True)[0]["generated_text"]
        return out
    except Exception as e:
        return f"[transformers error] {e}"

# --------- Mock mode ----------
def _call_mock(prompt: str) -> str:
    # deterministic short mock
    summary = prompt if len(prompt) < 200 else prompt[:197] + "..."
    return f"[MOCK] Generated response for prompt: {summary}"