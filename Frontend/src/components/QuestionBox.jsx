function QuestionBox({ question, setQuestion, handleAsk, loading }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      handleAsk();
    }
  };

  return (
    <div className="question-box">
      <input
        type="text"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escribe tu pregunta aquí..."
        className="question-input"
      />

      <button
        onClick={handleAsk}
        disabled={loading}
        className="send-button"
      >
        {loading ? "Consultando..." : "Enviar"}
      </button>
    </div>
  );
}

export default QuestionBox;