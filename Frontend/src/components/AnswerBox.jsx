function AnswerBox({ answer, loading }) {
  return (
    <div className="section-card">
      <h2>Respuesta</h2>

      {loading ? (
        <p className="loading-text">Consultando el backend y verificando fuentes...</p>
      ) : answer ? (
        <div className="answer-text">
          {answer.split("\n").map((line, index) => (
            <p key={index} className="answer-paragraph">
              {line || "\u00A0"}
            </p>
          ))}
        </div>
      ) : (
        <p className="empty-text">
          Aquí aparecerá la respuesta real del sistema.
        </p>
      )}
    </div>
  );
}

export default AnswerBox;