import { useState } from "react";
import Header from "./components/Header";
import QuestionBox from "./components/QuestionBox";
import AnswerBox from "./components/AnswerBox";
import SourcesList from "./components/SourcesList";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setAnswer("");
    setSources([]);

    setTimeout(() => {
      setAnswer(
        `Respuesta simulada para la pregunta: "${question}". Aquí el backend luego devolverá la respuesta real basada en los libros y las fuentes estructuradas.`
      );

      setSources([
        "Harry Potter and the Chamber of Secrets - Chapter 17",
        "Harry Potter and the Half-Blood Prince - Chapter 23",
      ]);

      setLoading(false);
    }, 1200);
  };

  return (
    <div className="app-container">
      <div className="main-card">
        <Header />

        <QuestionBox
          question={question}
          setQuestion={setQuestion}
          handleAsk={handleAsk}
          loading={loading}
        />

        <AnswerBox answer={answer} loading={loading} />

        <SourcesList sources={sources} />
      </div>
    </div>
  );
}

export default App;