import { useMemo, useState } from "react";
import Header from "./components/Header";
import QuestionBox from "./components/QuestionBox";
import AnswerBox from "./components/AnswerBox";
import SourcesList from "./components/SourcesList";

function normalizeApiUrl(url) {
  if (!url) return "http://localhost:8080";
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function App() {
  const API_URL = useMemo(
    () => normalizeApiUrl(import.meta.env.VITE_API_URL),
    []
  );

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAsk = async () => {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setSources([]);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
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

      setAnswer(
        data?.answer?.trim()
          ? data.answer
          : "El backend respondió, pero no devolvió una respuesta con contenido."
      );

      setSources(Array.isArray(data?.citations) ? data.citations : []);
    } catch (err) {
      if (err.name === "AbortError") {
        setError("La solicitud tardó demasiado. Intenta de nuevo.");
      } else {
        setError(
          "No fue posible conectar con el backend. Verifica que esté encendido y que VITE_API_URL sea correcta."
        );
      }

      setAnswer("");
      setSources([]);
      console.error("Error conectando con backend:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuestion("");
    setAnswer("");
    setSources([]);
    setError("");
    setLoading(false);
  };

  return (
    <div className="app-container">
      <div className="main-card">
        <Header />

        <QuestionBox
          question={question}
          setQuestion={setQuestion}
          handleAsk={handleAsk}
          handleClear={handleClear}
          loading={loading}
        />

        {error ? <div className="error-banner">{error}</div> : null}

        <AnswerBox answer={answer} loading={loading} />
        <SourcesList sources={sources} />
      </div>
    </div>
  );
}

export default App;