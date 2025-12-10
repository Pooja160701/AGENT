# backend/app/orchestrator_langgraph_true.py
"""
LangGraph true-or-fallback orchestrator.

This file:
- attempts to detect and use the installed langgraph SDK (multiple common entrypoints),
- if a compatible SDK API is found, registers nodes and runs the graph,
- otherwise falls back to the FallbackGraph sequential executor (safe behavior).
"""
from typing import Any, Dict
import uuid, traceback, importlib
from .checkpointer import save_checkpoint, load_last_checkpoint
from .llm_client import call_llm

# ---- node implementations (business logic) ----
def draftsman_node(state: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"Create a short CBT exercise based on: {state.get('intent_text','')}"
    out = call_llm(prompt, max_tokens=512)
    state["current_draft_text"] = out
    state.setdefault("draft_versions", []).append({"version": state.get("iteration_count", 0) + 1, "text": out})
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    return state

def safety_guardian_node(state: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"Check this draft for safety: {state.get('current_draft_text','')}"
    out = call_llm(prompt, max_tokens=256)
    state["safety_check_text"] = out
    state.setdefault("safety_flags", [])
    return state

def clinical_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    prompt = f"Critique the draft for empathy & clarity and suggest revision:\n\n{state.get('current_draft_text','')}"
    out = call_llm(prompt, max_tokens=512)
    state["critic_text"] = out
    prompt2 = f"Revise the following for empathy and clarity:\n\n{state.get('current_draft_text','')}\n\nCritic notes:\n{out}"
    rev = call_llm(prompt2, max_tokens=512)
    state["proposed_revision"] = rev
    return state

def supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state["status"] = "paused_for_human"
    return state

# ---- fallback sequential executor (safe) ----
class FallbackGraph:
    def __init__(self, save_checkpoint_fn=save_checkpoint):
        self.save_checkpoint = save_checkpoint_fn
        self.nodes = [
            ("Draftsman", draftsman_node),
            ("SafetyGuardian", safety_guardian_node),
            ("ClinicalCritic", clinical_critic_node),
            ("supervisor", supervisor_node),
        ]

    def _emit_checkpoint(self, run_id: str, agent_name: str, state: Dict[str, Any], note: str):
        self.save_checkpoint(run_id, agent_name, state, note)

    def start_run(self, intent: str) -> str:
        run_id = str(uuid.uuid4())
        state = {
            "run_id": run_id,
            "intent_text": intent,
            "status": "running",
            "draft_versions": [],
            "iteration_count": 0,
            "current_draft_text": "",
            "safety_flags": [],
            "safety_score": None
        }
        self._emit_checkpoint(run_id, "starter", state, "run started")
        for name, fn in self.nodes:
            try:
                state = fn(state)
                self._emit_checkpoint(run_id, name, dict(state), f"{name} completed")
            except Exception as e:
                self._emit_checkpoint(run_id, name, dict(state), f"{name} error: {e}")
                raise
        return run_id

    def resume_run(self, run_id: str) -> Dict[str, Any]:
        cp = load_last_checkpoint(run_id)
        if not cp:
            raise RuntimeError("run not found")
        state = cp.state_snapshot
        last = cp.agent_name
        start_idx = 0
        for idx,(name,_) in enumerate(self.nodes):
            if name == last:
                start_idx = idx + 1
                break
        for name, fn in self.nodes[start_idx:]:
            state = fn(state)
            self._emit_checkpoint(run_id, name, dict(state), f"{name} resumed/completed")
        return state

# ---- SDK detection & adapter logic ----
def try_build_langgraph_graph():
    """
    Try multiple known module/class locations for LangGraph and build a graph.
    Returns (graph_obj, add_node_method_name, run_method_name) on success, else None.
    """
    candidates = [
        ("langgraph", None),
        ("langgraph.sdk", None),
        ("langgraph.prebuilt", None),
        ("langgraph_sdk", None),
    ]
    for modname, _ in candidates:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue

        # Common API: StateGraph / Graph / Workflow classes
        for clsname in ("StateGraph", "Graph", "LangGraph", "Workflow"):
            cls = getattr(mod, clsname, None)
            if cls:
                try:
                    graph = cls()
                    # try to detect available methods
                    if hasattr(graph, "add_node") and hasattr(graph, "add_edge") and (hasattr(graph, "run") or hasattr(graph, "execute") or hasattr(graph, "start")):
                        return (graph, "add_node", "run" if hasattr(graph, "run") else ("execute" if hasattr(graph, "execute") else "start"))
                    # some SDKs expect add_task or add_step
                    if hasattr(graph, "add_task") and (hasattr(graph, "run") or hasattr(graph, "execute")):
                        return (graph, "add_task", "run" if hasattr(graph, "run") else "execute")
                except Exception:
                    continue

        # try prebuilt 'StateGraphBuilder' style if present
        # e.g., langgraph.prebuilt.StateGraphBuilder or similar
        for builder_name in ("StateGraphBuilder", "GraphBuilder", "WorkflowBuilder"):
            builder = getattr(mod, builder_name, None)
            if builder:
                try:
                    b = builder()
                    # builder may expose build/run methods - return it and mark builder usage
                    if hasattr(b, "add_node") and (hasattr(b, "build") or hasattr(b, "run")):
                        return (b, "add_node", "run" if hasattr(b, "run") else "build")
                except Exception:
                    continue

    return None

def create_true_or_fallback_orchestrator():
    found = try_build_langgraph_graph()
    if not found:
        # SDK not usable - return fallback
        return FallbackGraph()
    graph_obj, add_method, run_method = found

    # Adapter to register our Python callables as nodes/tasks for the SDK graph
    # We'll try to use the discovered add_method name.
    def register_node(name: str, func):
        try:
            add = getattr(graph_obj, add_method)
            # best-effort: some SDKs accept (name, callable) others accept different signatures
            try:
                add(name, func)
                return True
            except TypeError:
                # try different permutations
                try:
                    add(func, name=name)
                    return True
                except Exception:
                    try:
                        add(name, handler=func)
                        return True
                    except Exception:
                        return False
        except Exception:
            return False

    # Register nodes
    ok = True
    ok = ok and register_node("Draftsman", draftsman_node)
    ok = ok and register_node("SafetyGuardian", safety_guardian_node)
    ok = ok and register_node("ClinicalCritic", clinical_critic_node)
    ok = ok and register_node("supervisor", supervisor_node)

    # If registration failed for any reason, fallback to safe executor
    if not ok:
        return FallbackGraph()

    # Create wrapper exposing start_run and resume_run
    class LangGraphSDKWrapper:
        def __init__(self, graph):
            self.graph = graph

        def start_run(self, intent: str) -> str:
            run_id = str(uuid.uuid4())
            state = {
                "run_id": run_id,
                "intent_text": intent,
                "status": "running",
                "draft_versions": [],
                "iteration_count": 0,
                "current_draft_text": "",
                "safety_flags": []
            }
            save_checkpoint(run_id, "starter", state, "run started (langgraph-sdk)")

            # run graph - try common run method names
            try:
                runner = getattr(self.graph, run_method)
                # try to call runner with 'state' param or 'initial_state'
                try:
                    final = runner(state)
                except TypeError:
                    try:
                        final = runner(initial_state=state)
                    except Exception:
                        # as last resort, try runner() with no args
                        final = runner()
                # persist final if returned
                if isinstance(final, dict):
                    save_checkpoint(run_id, "langgraph_run", final, "graph run complete")
                return run_id
            except Exception as e:
                traceback.print_exc()
                # fallback: run sequentially
                return FallbackGraph().start_run(intent)

        def resume_run(self, run_id: str) -> Dict[str, Any]:
            try:
                cp = load_last_checkpoint(run_id)
                state = cp.state_snapshot if cp else {}
                # try an SDK resume if available
                if hasattr(self.graph, "resume"):
                    res = self.graph.resume(state)
                    if isinstance(res, dict):
                        save_checkpoint(run_id, "langgraph_resume", res, "graph resumed")
                        return res
                # fallback to sequential resume
            except Exception:
                traceback.print_exc()
            return FallbackGraph().resume_run(run_id)

    return LangGraphSDKWrapper(graph_obj)

# expose orchestrator
Orchestrator = create_true_or_fallback_orchestrator()
