import { useState } from "react";
import axios from "axios";
import "./App.css";
import hclTechBackground from "./hcltech-bg.webp";

function App() {

  const [message, setMessage] = useState("");
  const [result, setResult] = useState([]);
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!message.trim() || loading) {
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(
        "http://localhost:8000/chat",
        {
          message
        }
      );

      setResult(response.data.workflow);
    } catch (error) {
      setResult([
        {
          agent: "Frontend",
          task: "Could not reach the backend AI service. Make sure FastAPI is running on http://localhost:8000."
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="app-shell">
      <div
        className="brand-backdrop"
        style={{ backgroundImage: `url(${hclTechBackground})` }}
        aria-hidden="true"
      />

      <section className="chat-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Powered by Regression</p>
            <h1>HCL AgentHub</h1>
          </div>
          <div className="status-pill">
            <span />
            Online
          </div>
        </div>

        <div className="prompt-row">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                send();
              }
            }}
            placeholder="Ask anything about IT, HR, approvals, or general knowledge..."
          />

          <button onClick={send} disabled={loading}>
            {loading ? "Thinking..." : "Ask AI"}
          </button>
        </div>

        <div className="answers">
          {result.length === 0 && (
            <div className="empty-state">
              Start with a question and your AI workflow will appear here.
            </div>
          )}

          {result.map((r, i) => (
            <article className="answer-card" key={i}>
              <div className="agent-name">{r.agent || "Unknown Agent"}</div>
              <p>{r.task || "No task returned"}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
