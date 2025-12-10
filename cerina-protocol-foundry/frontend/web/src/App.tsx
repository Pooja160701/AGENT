// frontend/web/src/App.tsx
import React, { useEffect, useRef, useState } from "react";

type Checkpoint = {
  agent: string;
  timestamp: string;
  note?: string;
  state?: any;
};

function formatTime(iso?: string) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

export default function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<Checkpoint[]>([]);
  const [draft, setDraft] = useState<string>("");
  const [status, setStatus] = useState<string>("idle");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [finalSummary, setFinalSummary] = useState<string>("");
  const [loadingSummary, setLoadingSummary] = useState<boolean>(false);
  const [intentText, setIntentText] = useState<string>("Create a CBT exercise for insomnia");
  const [intentSaving, setIntentSaving] = useState<boolean>(false);
  const eventsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.body.style.background = theme === "light" ? "#f5f7fb" : "#0f1720";
    document.body.style.color = theme === "light" ? "#0b1220" : "#e6eef6";
  }, [theme]);

  useEffect(() => {
    if (eventsRef.current) {
      eventsRef.current.scrollTop = eventsRef.current.scrollHeight;
    }
  }, [events]);

  async function startRun() {
    setStatus("starting");
    try {
      const resp = await fetch("http://127.0.0.1:8000/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent: intentText }),
      });
      const data = await resp.json();
      setRunId(data.run_id);
      setStatus("running");
      setFinalSummary("");
      setEvents([]);
      setDraft("");
    } catch (err) {
      console.error(err);
      setStatus("error");
      alert("Failed to contact backend. Is the server running?");
    }
  }

  // Update intent on the running run (PATCH)
  async function updateIntentOnRun() {
    if (!runId) return alert("No active run to update");
    setIntentSaving(true);
    try {
      const resp = await fetch(`http://127.0.0.1:8000/run/${runId}/intent`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent: intentText }),
      });
      const j = await resp.json();
      if (!j.ok) throw new Error("Failed to update intent");
      // add an event locally to show instant feedback
      setEvents((prev) => [
        ...prev,
        {
          agent: "human",
          timestamp: new Date().toISOString(),
          note: `intent updated to: ${intentText}`,
          state: { intent_text: intentText },
        },
      ]);
      alert("Intent updated for run");
    } catch (err) {
      console.error(err);
      alert("Failed to update intent on server");
    } finally {
      setIntentSaving(false);
    }
  }

  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`http://127.0.0.1:8000/stream/${runId}`);
    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        setEvents((prev) => [...prev, payload]);
        if (payload.state?.current_draft_text) {
          setDraft(payload.state.current_draft_text);
        }
        if (payload.state?.status) {
          setStatus(payload.state.status);
        }
        // if agent writes an intent_text into state, sync local input
        if (payload.state?.intent_text) {
          setIntentText(payload.state.intent_text);
        }
      } catch (err) {
        console.error("Failed to parse SSE:", err);
      }
    };
    es.onerror = (err) => {
      console.warn("SSE error", err);
      es.close();
    };
    return () => es.close();
  }, [runId]);

  async function approve() {
    if (!runId) return alert("No run to approve");
    setStatus("approving");
    try {
      const resp = await fetch(`http://127.0.0.1:8000/approve/${runId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: draft }),
      });
      const j = await resp.json();
      setStatus("approved");
      if (j.final_state) {
        setEvents((prev) => [
          ...prev,
          { agent: "human", timestamp: new Date().toISOString(), note: "approved", state: j.final_state },
        ]);
      }
      alert("Approved — final state recorded.");
    } catch (err) {
      console.error(err);
      setStatus("error");
      alert("Approve failed. Check backend logs.");
    }
  }

  async function generateSummary() {
    if (!runId) return alert("No run to summarize");
    setLoadingSummary(true);
    try {
      const resp = await fetch(`http://127.0.0.1:8000/summary/${runId}`);
      const j = await resp.json();
      setFinalSummary(j.summary || "");
      setLoadingSummary(false);
    } catch (err) {
      console.error(err);
      setLoadingSummary(false);
      alert("Summary generation failed. Check backend logs.");
    }
  }

  function copyDraft() {
    navigator.clipboard.writeText(draft).then(
      () => alert("Draft copied to clipboard"),
      () => alert("Failed to copy")
    );
  }

  function copySummary() {
    navigator.clipboard.writeText(finalSummary).then(
      () => alert("Summary copied to clipboard"),
      () => alert("Failed to copy")
    );
  }

  function downloadFinal() {
    const dataStr = JSON.stringify({ runId, draft, events, finalSummary }, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cerina_run_${runId || "untitled"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div>
          <h1 style={{ margin: 0 }}>Agent Dashboard</h1>
          <div style={{ color: "#6b7280", marginTop: 6 }}>Human-in-the-loop preview • Cerina Foundry</div>
        </div>

        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={intentText}
              onChange={(e) => setIntentText(e.target.value)}
              style={styles.intentInput}
            />
            <button onClick={() => (runId ? updateIntentOnRun() : startRun())} style={styles.startButton}>
              {runId ? (intentSaving ? "Saving…" : "Update Intent") : "Start Run"}
            </button>
          </div>

          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <div style={{ fontSize: 14, color: theme === "light" ? "#334155" : "#cbd5e1" }}>
              Theme
              <button
                onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                style={styles.smallButton}
              >
                {theme === "light" ? "Dark" : "Light"}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main style={styles.main}>
        <section style={styles.left}>
          <div style={styles.panelHeader}>
            <strong>Status:</strong> <span style={{ marginLeft: 8 }}>{status}</span>
            <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
              <button onClick={copyDraft} style={styles.ghostButton} title="Copy draft">Copy</button>
              <button onClick={downloadFinal} style={styles.ghostButton} title="Download run">Download</button>
            </div>
          </div>

          <div ref={eventsRef} style={styles.events}>
            {events.length === 0 && <div style={{ color: "#94a3b8" }}>No events yet. Click Start Run.</div>}
            {events.map((ev, i) => (
              <div key={i} style={styles.eventCard}>
                <div style={styles.eventHeader}>
                  <div style={{ fontWeight: 700 }}>{ev.agent}</div>
                  <div style={{ color: "#64748b", fontSize: 12 }}>{formatTime(ev.timestamp)}</div>
                </div>
                {ev.note && <div style={{ marginTop: 6 }}>{ev.note}</div>}
                {ev.state && (
                  <pre style={styles.prettyJson}>
                    {JSON.stringify(ev.state, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </section>

        <section style={styles.right}>
          <div style={styles.panelHeader}>
            <strong>Draft / Human-in-the-loop</strong>
            <div style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>Edit and Approve</div>
          </div>

          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            style={styles.editor}
            placeholder="Draft will appear here. Edit before approving."
          />

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button onClick={approve} style={styles.approveButton} disabled={!runId}>
              Approve & Finalize
            </button>

            <button onClick={generateSummary} style={{ ...styles.ghostButton, minWidth: 140 }} disabled={!runId || loadingSummary}>
              {loadingSummary ? "Generating…" : "Generate Summary"}
            </button>

            <button onClick={() => { setEvents([]); setDraft(""); setRunId(null); setStatus("idle"); setFinalSummary(""); }} style={styles.ghostButton}>
              Reset
            </button>
          </div>

          <div style={{ marginTop: 16 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Final Summary</div>
            <div style={styles.summaryControls}>
              <button onClick={copySummary} style={styles.ghostButton} disabled={!finalSummary}>
                Copy Summary
              </button>
            </div>

            <div style={styles.summaryBoxContainer}>
              {finalSummary ? (
                <div style={styles.summaryBox}>{finalSummary}</div>
              ) : (
                <div style={{ color: "#94a3b8", padding: 12, borderRadius: 8, background: theme === "light" ? "#fff" : "#071018" }}>
                  No summary yet. Generate a summary after approving.
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer style={styles.footer}>
        <div>Local demo • no OpenAI key required • Ollama/mock modes supported</div>
        <div>GitHub: <code>pooja160701/cerina-protocol-foundry</code></div>
      </footer>
    </div>
  );
}

/* ---------- simple inline styles (easy to tweak) ---------- */
const styles: {[k: string]: React.CSSProperties} = {
  app: {
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial",
    padding: 20,
    minHeight: "100vh",
    boxSizing: "border-box",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 14,
  },
  intentInput: {
    minWidth: 420,
    padding: "10px 12px",
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    fontSize: 14,
    marginRight: 8,
  },
  startButton: {
    background: "#0f172a",
    color: "white",
    border: "none",
    padding: "10px 14px",
    borderRadius: 8,
    cursor: "pointer"
  },
  smallButton: {
    marginLeft: 8,
    borderRadius: 6,
    padding: "6px 8px",
    border: "1px solid #cbd5e1",
    background: "white",
    cursor: "pointer"
  },
  main: {
    display: "flex",
    gap: 20,
  },
  left: {
    flex: 1,
    minWidth: 420,
  },
  right: {
    flexBasis: 540,
    display: "flex",
    flexDirection: "column",
  },
  panelHeader: {
    display: "flex",
    alignItems: "center",
    padding: "8px 12px",
    marginBottom: 8,
    background: "transparent",
  },
  events: {
    background: "white",
    borderRadius: 8,
    padding: 12,
    minHeight: 420,
    maxHeight: 620,
    overflow: "auto",
    boxShadow: "0 2px 8px rgba(12, 14, 20, 0.04)"
  },
  eventCard: {
    marginBottom: 12,
    padding: 10,
    borderRadius: 8,
    border: "1px solid #e6eef6",
    background: "#fbfdff"
  },
  eventHeader: {
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
    alignItems: "center"
  },
  prettyJson: {
    marginTop: 8,
    padding: 8,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    fontSize: 12,
    background: "#f8fafc",
    borderRadius: 6,
    border: "1px solid #eef2ff",
    color: "#0f172a",
  },
  editor: {
    width: "100%",
    minHeight: 320,
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    lineHeight: 1.5,
    border: "1px solid #e2e8f0",
    background: "white",
    resize: "vertical",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, 'Courier New', monospace"
  },
  approveButton: {
    background: "#059669",
    color: "white",
    padding: "10px 14px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer"
  },
  ghostButton: {
    background: "transparent",
    border: "1px solid #cbd5e1",
    padding: "8px 10px",
    borderRadius: 8,
    cursor: "pointer"
  },
  footer: {
    marginTop: 22,
    display: "flex",
    justifyContent: "space-between",
    color: "#94a3b8",
    fontSize: 13
  },
  // Summary UI
  summaryControls: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 8,
    marginBottom: 8,
  },
  summaryBoxContainer: {
    marginTop: 6,
  },
  summaryBox: {
    whiteSpace: "pre-wrap",
    overflowWrap: "break-word",
    maxHeight: 400,
    overflowY: "auto",
    padding: 14,
    borderRadius: 10,
    border: "1px solid rgba(148,163,184,0.15)",
    background: "#071426",
    color: "#e6eef6",
    fontSize: 14,
    lineHeight: 1.5,
    fontFamily: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto",
  },
};