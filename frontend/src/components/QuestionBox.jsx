function QuestionBox({
  question,
  setQuestion,
  handleAsk,
  handleClear,
  loading,
}) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !loading) {
      handleAsk();
    }
  };

  return (
    <div className="question-box-wrapper">
      <div className="question-box">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu pregunta aquí..."
          className="question-input"
          disabled={loading}
        />

        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="send-button"
        >
          {loading ? "Consulting..." : "Send"}
        </button>

        <button
          onClick={handleClear}
          disabled={loading}
          className="clear-button"
          type="button"
        >
          Clear
        </button>
      </div>

      <p className="helper-text">
        Ejemplo: ¿Quién destruyó el relicario de Slytherin?
      </p>
    </div>
  );
}

export default QuestionBox;