# backend/app/config.py
import os

# LLM Mode: "ollama", "transformers", "mock"
LLM_MODE = os.getenv("LLM_MODE", "mock").lower()

# Toggle LangGraph orchestrator or custom orchestrator
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "true").lower() in ("1", "true", "yes")

# Ollama settings (if using ollama)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Database URL (sqlite by default)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cerina_foundry.db")