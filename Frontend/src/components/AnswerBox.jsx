function AnswerBox({ answer, loading }) {
  return (
    <div className="section-card">
      <h2>Respuesta</h2>

      {loading ? (
        <p className="loading-text">Buscando información...</p>
      ) : answer ? (
        <p className="answer-text">{answer}</p>
      ) : (
        <p className="empty-text">
          Aquí aparecerá la respuesta del sistema.
        </p>
      )}
    </div>
  );
}

export default AnswerBox;