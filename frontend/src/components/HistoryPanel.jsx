function HistoryPanel({ history, onItemClick, onClear }) {
  if (!history || history.length === 0) {
    return (
      <div className="section-card history-panel">
        <h2>Conversation History</h2>
        <p className="empty-text">No conversations yet. Ask a question to start!</p>
      </div>
    );
  }

  return (
    <div className="section-card history-panel">
      <div className="history-header">
        <h2>Conversation History</h2>
        <button className="clear-history-btn" onClick={onClear}>
          Clear All
        </button>
      </div>
      <div className="history-list">
        {history.map((item, index) => (
          <div 
            key={index} 
            className="history-item"
            onClick={() => onItemClick(item)}
          >
            <div className="history-question">
              <strong>Q{index + 1}:</strong> {item.question.length > 80 
                ? item.question.substring(0, 80) + "..." 
                : item.question}
            </div>
            {item.answer && (
              <div className="history-answer">
                {item.answer.length > 100 
                  ? item.answer.substring(0, 100) + "..." 
                  : item.answer}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default HistoryPanel;