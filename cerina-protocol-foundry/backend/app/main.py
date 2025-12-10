# backend/app/main.py
import os
import uuid
import asyncio
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from .llm_client import call_llm
from .checkpointer import init_db, save_checkpoint, load_last_checkpoint, list_checkpoints
from .config import USE_LANGGRAPH

# Use the LangGraph true-or-fallback orchestrator implemented separately
from .orchestrator_langgraph_true import Orchestrator as LangGraphOrchestrator

# Initialize DB (creates tables if needed)
init_db()

app = FastAPI(title="Cerina Foundry - Backend")

# allow local frontend dev (Vite / CRA)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# instantiate orchestrator
if USE_LANGGRAPH:
    orchestrator = LangGraphOrchestrator  # exposes start_run(intent) and resume_run(run_id)
else:
    raise RuntimeError("USE_LANGGRAPH=false not currently supported by this deployment. Set USE_LANGGRAPH=true")

# ---------------- SSE EVENT STREAM ---------------- #
async def event_stream(run_id: str):
    """
    Server-Sent Events stream that yields the latest checkpoint for a run.
    Uses json.dumps(..., default=str) so timestamps and non-serializable objects are safe.
    """
    last_seen = None
    while True:
        cp = load_last_checkpoint(run_id)
        if cp and cp.id != last_seen:
            last_seen = cp.id
            payload = {
                "agent": cp.agent_name,
                "timestamp": cp.timestamp.isoformat() if hasattr(cp.timestamp, "isoformat") else str(cp.timestamp),
                "note": cp.note,
                "state": cp.state_snapshot,
            }
            # strict JSON for safe client parsing
            yield f"data: {json.dumps(payload, default=str)}\n\n"
        await asyncio.sleep(0.5)

# ---------------- API ROUTES ---------------- #

@app.get("/")
async def root():
    return {"message": "Cerina Foundry backend is running"}

@app.post("/start")
async def start_run(payload: dict):
    """
    Start a new run. Expects JSON body: { "intent": "<text>" }
    Returns: { "run_id": "<uuid>" }
    """
    intent = payload.get("intent", "")
    if not intent:
        raise HTTPException(status_code=400, detail="intent required")

    run_id = orchestrator.start_run(intent)
    return {"run_id": run_id}

@app.get("/stream/{run_id}")
async def stream(run_id: str):
    """
    SSE endpoint clients use to receive live checkpoint events.
    """
    return StreamingResponse(event_stream(run_id), media_type="text/event-stream")

@app.get("/status/{run_id}")
async def status(run_id: str):
    cp = load_last_checkpoint(run_id)
    if not cp:
        raise HTTPException(status_code=404, detail="run not found")
    return cp.state_snapshot

@app.get("/history/{run_id}")
async def history(run_id: str):
    cps = list_checkpoints(run_id)
    items = [
        {
            "agent": c.agent_name,
            "timestamp": c.timestamp.isoformat() if hasattr(c.timestamp, "isoformat") else str(c.timestamp),
            "note": c.note
        }
        for c in cps
    ]
    return {"history": items}

@app.post("/approve/{run_id}")
async def approve(run_id: str, payload: dict):
    """
    Human approves the current draft. Payload optional: { "text": "<approved text>" }
    This saves an approval checkpoint and asks the orchestrator to resume/finalize the run.
    """
    cp = load_last_checkpoint(run_id)
    if not cp:
        raise HTTPException(status_code=404, detail="run not found")

    state = cp.state_snapshot
    state["approved_text"] = payload.get("text", state.get("current_draft_text"))
    state["status"] = "approved_by_human"

    save_checkpoint(run_id, "human", state, "approved by human")

    # resume orchestrator to finalize the run
    final_state = orchestrator.resume_run(run_id)

    return {"ok": True, "final_state": final_state}

# Generate a short human-friendly summary for a run
@app.get("/summary/{run_id}")
async def summary(run_id: str):
    cp = load_last_checkpoint(run_id)
    if not cp:
        raise HTTPException(status_code=404, detail="run not found")
    state = cp.state_snapshot

    # If already has a final short summary, return it
    if state.get("final_summary"):
        return {"summary": state["final_summary"]}

    # Compose a short prompt for the LLM (safe and brief)
    draft = state.get("approved_text") or state.get("current_draft_text", "")
    intent = state.get("intent_text", "")
    prompt = (
        f"Produce a short (3-5 line) human-friendly summary of the final CBT exercise.\n\n"
        f"Intent: {intent}\n\n"
        f"Final draft:\n{draft}\n\n"
        "Output a concise summary suitable for a clinician reviewer."
    )

    # call the LLM (mock / ollama / transformers)
    try:
        summary_text = call_llm(prompt, max_tokens=256)
        # defensive cleaning: strip mock prefixes if present
        if isinstance(summary_text, str) and summary_text.startswith("[MOCK]"):
            # remove the leading mock phrase to make it human-friendly
            summary_text = summary_text.split(":", 1)[-1].strip()
    except Exception as e:
        summary_text = f"[error generating summary] {e}"

    # persist summary into the run (so it can be reused)
    state["final_summary"] = summary_text
    save_checkpoint(run_id, "summary_agent", state, "final summary generated")

    return {"summary": summary_text}