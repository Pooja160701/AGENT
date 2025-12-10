# **Cerina Protocol Foundry — Human-in-the-Loop AI Agent Workflow (LangGraph + FastAPI + React)**

This project implements a **multi-agent clinical content generation system** powered by **LangGraph**, **FastAPI**, **SQLite Checkpointing**, and a **React dashboard** for human-in-the-loop interaction.

It replicates the essential logic of **Cerina’s clinician-aligned workflows**:
draft → safety check → critique → refinement → supervisor pause → human approval → finalization → summary.

The system runs **fully locally** using:

* **Mock LLM mode**
* Optionally: **Ollama**, **Local Transformers**, or any LangChain-compatible LLM

---

---

# ⭐ **Features**

### ✅ **1. Multi-Agent LangGraph Workflow**

The orchestrator automatically runs:

| Agent              | Role                                              |
| ------------------ | ------------------------------------------------- |
| **Draftsman**      | Generates the first draft of the CBT exercise.    |
| **SafetyGuardian** | Flags unsafe / harmful / unethical content.       |
| **ClinicalCritic** | Improves empathy, clarity, clinical quality.      |
| **Supervisor**     | Decides pause/resume; hands off to human.         |
| **Human**          | Reviewer/editor inside the UI.                    |
| **SummaryAgent**   | Produces a final 3–5 line human-friendly summary. |

---

### ✅ **2. Human-In-The-Loop Dashboard (React)**

The UI allows:

* ✨ Start a run
* 📝 Provide or edit **intent text**
* 🧠 Watch agent events in **live event stream (SSE)**
* ✏️ Edit the draft manually
* ✔️ Approve & finalize
* 📄 Generate summary
* 📥 Export run data as JSON
* 📌 Intent updating mid-run (PATCH)

---

### ✅ **3. Checkpointing + Replay**

Every agent writes a checkpoint snapshot:

```
{
  "agent": "ClinicalCritic",
  "timestamp": "...",
  "note": "Critic completed",
  "state": { ... }
}
```

Stored in SQLite:
`backend/app/checkpointer.py`.

You can:

* `/status/{run_id}` → get latest state
* `/history/{run_id}` → get entire timeline
* `/stream/{run_id}` → SSE real-time events

---

### ✅ **4. Mock LLM / Local LLM support**

The system works **out of the box** with:

* Mock LLM mode
* Ollama (`llama3`, `mistral`, `phi3`, etc.)
* HuggingFace Transformers local models

Configured in:
`backend/app/llm_client.py`.

---

---

# 🚀 **1. Installation**

## **Clone the repo**

```bash
git clone https://github.com/<your-repo>/cerina-protocol-foundry
cd cerina-protocol-foundry
```

---

# 🚀 **2. Backend Setup (FastAPI + LangGraph)**

### **Create virtual environment**

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
```

### **Install requirements**

```bash
pip install -r backend/requirements.txt
```

If missing:

```bash
pip install langgraph fastapi uvicorn sqlmodel pydantic transformers
```

### **Run backend**

```bash
./.venv/Scripts/python -m uvicorn backend.app.main:app --reload --port 8000 --host 127.0.0.1
```

You should see:

```
Cerina Foundry backend is running
```

Open API docs:
👉 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

---

# 🚀 **3. Frontend Setup (React)**

```bash
cd frontend/web
npm install --legacy-peer-deps
npm start
```

UI runs at:
👉 [http://localhost:3000](http://localhost:3000)

---

---

# 📁 **Project Structure**

```
cerina-protocol-foundry/
│
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI server
│   │   ├── orchestrator_langgraph_true.py
│   │   ├── checkpointer.py            # SQLite checkpointing
│   │   ├── llm_client.py              # Mock/LLM integration
│   │   ├── config.py
│   │   ├── agents/
│   │   │   ├── draftsman.py
│   │   │   ├── safety_guardian.py
│   │   │   ├── critic.py
│   │   │   └── supervisor.py
│   └── requirements.txt
│
├── frontend/
│   └── web/
│       ├── src/
│       │   └── App.tsx                # Full dashboard UI
│       └── package.json
│
└── README.md
```

---

---

# ⚙️ **4. API Overview**

### **Start a run**

```bash
POST /start
{
  "intent": "Create a CBT exercise for insomnia"
}
```

### **Stream live events (SSE)**

```
GET /stream/{run_id}
```

### **Check run status**

```
GET /status/{run_id}
```

### **Get full history**

```
GET /history/{run_id}
```

### **Approve & finalize**

```bash
POST /approve/{run_id}
{
  "text": "Looks good — finalize this version."
}
```

### **Update intent mid-run**

```bash
PATCH /run/{run_id}/intent
{
  "intent": "Rewrite for clarity and add a breathing step"
}
```

### **Generate summary**

```
GET /summary/{run_id}
```

---

---

# 🧠 **5. How the System Works (Detailed Explanation)**

When a user **starts a run**, the following happens:

---

## **Step 1 — Draftsman Agent**

* Reads the **intent text**
* Generates a **first draft**
* Example: *CBT exercise for insomnia focusing on stimulus control*

---

## **Step 2 — SafetyGuardian**

* Analyzes draft:

  * self-harm content
  * medical misinformation
  * unethical recommendations

If unsafe → flags + rewrites

---

## **Step 3 — ClinicalCritic**

* Improves:

  * empathy
  * clarity
  * readability
  * clinical relevance

---

## **Step 4 — Supervisor**

* Pauses for human review
* Final editable draft sent to UI
* State: `"paused_for_human"`

---

## **Step 5 — Human Edits (UI)**

User may:

* edit the draft
* modify intent
* request new summary
* approve final version

---

## **Step 6 — Finalization**

After approval:

* system produces the **final state**
* SummaryAgent creates a 3–5 line summary
* Stored in `final_summary`

---

---

# 📝 **6. Example Summary Output**

Example generated summary:

> A structured CBT exercise introducing nighttime breathing practice, cognitive reframing, and sleep-onset reduction strategies.
> Tailored for individuals with insomnia and includes a brief rationale for each step.
> Suitable for clinical review and user-facing instruction.

---

---

# 🛠️ **7. Troubleshooting**

### **UI shows truncated summary ("…")**

This is **UI text overflow**, not backend.
Use the *copy* button to confirm full text exists.

Fix included in latest UI version — long summaries now expand vertically.

---

### **ModuleNotFoundError: sqlmodel**

Install again inside venv:

```bash
./.venv/Scripts/pip install sqlmodel
```

---

### **React dependency conflicts**

Use:

```bash
npm install --legacy-peer-deps
```

---

### **SSE stream not updating**

Check CORS rules in `main.py`.

---

---

# 🔧 **8. Extending the System**

You can easily add:

### ➕ **New Agents**

Drop a new file under `backend/app/agents/` and add it to the LangGraph workflow.

### 🎤 Voice input

Integrate Whisper or VAD in frontend.

### 📄 Export PDF

Use Python’s reportlab.

### 🔐 Authentication

Add JWT middleware to FastAPI.

---

---

# 🎉 **9. Credits**

Built for educational + prototype purposes using:

* **LangGraph**
* **FastAPI**
* **React (Vite)**
* **SQLite Checkpoints**
* **Ollama / Transformers**

---

Here is a **clean, professional architecture diagram** of your Cerina Protocol Foundry system, showing **LangGraph agents**, **FastAPI backend**, **checkpointing**, **frontend UI**, and **LLM integration**.

---