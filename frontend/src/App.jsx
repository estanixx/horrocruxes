import { useMemo, useState, useEffect } from "react";
import Header from "./components/Header";
import QuestionBox from "./components/QuestionBox";
import AnswerBox from "./components/AnswerBox";
import SourcesList from "./components/SourcesList";
import HistoryPanel from "./components/HistoryPanel";
import TimelinePanel from "./components/TimelinePanel";
import ReportPanel from "./components/ReportPanel";

function normalizeApiUrl(url) {
  if (!url) return "http://localhost:8080";
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function getOrCreateSessionId() {
  let sessionId = localStorage.getItem("horrocruxes-session-id");
  if (!sessionId) {
    sessionId = "session-" + Date.now() + "-" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("horrocruxes-session-id", sessionId);
  }
  return sessionId;
}

function App() {
  const API_URL = useMemo(
    () => normalizeApiUrl(import.meta.env.VITE_API_URL),
    []
  );

  const [sessionId] = useState(() => getOrCreateSessionId());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [reportMarkdown, setReportMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversationHistory, setConversationHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load conversation history on mount
  useEffect(() => {
    loadConversationHistory();
  }, [sessionId]);

  const loadConversationHistory = async () => {
    try {
      const response = await fetch(`${API_URL}/session/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        // Parse context into conversation pairs
        if (data.context) {
          const lines = data.context.split("\n");
          const pairs = [];
          let currentPair = null;
          for (const line of lines) {
            if (line.startsWith("User: ")) {
              currentPair = { question: line.substring(6), answer: null };
            } else if (line.startsWith("Assistant: ") && currentPair) {
              currentPair.answer = line.substring(11);
              pairs.push(currentPair);
              currentPair = null;
            }
          }
          setConversationHistory(pairs);
        }
      }
    } catch (err) {
      console.error("Failed to load conversation history:", err);
    }
  };

  const handleAsk = async () => {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setSources([]);
    setTimeline([]);
    setReportMarkdown("");

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionId,
        },
        body: JSON.stringify({
          query: trimmedQuestion,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let message = `Error HTTP ${response.status}`;

        try {
          const errorData = await response.json();
          if (errorData?.detail) {
            message = errorData.detail;
          }
        } catch {
          // Si la respuesta no es JSON, dejamos el mensaje por defecto
        }

        throw new Error(message);
      }

      const data = await response.json();
      console.log("Response data:", data);

      const answerText = data?.answer?.trim()
        ? data.answer
        : "El backend respondió, pero no devolvió una respuesta con contenido.";

      setAnswer(answerText);

      // Add to local conversation history
      setConversationHistory(prev => [...prev, { question: trimmedQuestion, answer: answerText }]);

      setSources(Array.isArray(data?.citations) ? data.citations : []);
      setTimeline(Array.isArray(data?.timeline) ? data.timeline : []);
      setReportMarkdown(data?.report_markdown || "");
    } catch (err) {
      if (err.name === "AbortError") {
        setError("La solicitud tardó demasiado. Intenta de nuevo.");
      } else {
        setError(
          "No fue posible conectar con el backend. Verifica que esté encendido y que VITE_API_URL sea correcta. Error: " + err.message
        );
      }

      setAnswer("");
      setSources([]);
      setTimeline([]);
      setReportMarkdown("");
      console.error("Error conectando con backend:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    setQuestion("");
    setAnswer("");
    setSources([]);
    setTimeline([]);
    setReportMarkdown("");
    setError("");
    setLoading(false);
    setConversationHistory([]);

    // Clear session on backend
    try {
      await fetch(`${API_URL}/session/${sessionId}`, { method: "DELETE" });
    } catch (err) {
      console.error("Failed to clear session:", err);
    }
  };

  const handleHistoryClick = (item) => {
    setQuestion(item.question);
    setAnswer(item.answer || "");
    setShowHistory(false);
  };

  return (
    <div className="app-container">
      <div className="main-card">
        <Header />

        <div className="session-indicator">
          <p>Search History: {sessionId.split("-")[1]}</p>
          <button 
            className="history-toggle-btn"
            onClick={() => setShowHistory(!showHistory)}
          >
            {showHistory ? "Hide History" : "Show History"}
          </button>
        </div>

        {showHistory && (
          <HistoryPanel 
            history={conversationHistory}
            onItemClick={handleHistoryClick}
            onClear={() => handleClear()}
          />
        )}

        <QuestionBox
          question={question}
          setQuestion={setQuestion}
          handleAsk={handleAsk}
          handleClear={handleClear}
          loading={loading}
        />

        {error ? <div className="error-banner">{error}</div> : null}

        <AnswerBox answer={answer} loading={loading} />
        <TimelinePanel events={timeline} />
        <ReportPanel report={reportMarkdown} />
        <SourcesList sources={sources} />
      </div>
    </div>
  );
}

export default App;
