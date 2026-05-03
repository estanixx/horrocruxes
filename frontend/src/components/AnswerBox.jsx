import ReactMarkdown from "react-markdown";

function AnswerBox({ answer, loading }) {
  return (
    <div className="section-card">
      <h2>Answer</h2>

      {loading ? (
        <p className="loading-text">
          Consulting the backend and verifying sources...
        </p>
      ) : answer ? (
        <div className="answer-text markdown-content">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      ) : (
        <p className="empty-text">
          The real answer will appear here.
        </p>
      )}
    </div>
  );
}

export default AnswerBox;