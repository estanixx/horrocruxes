function SourcesList({ sources }) {
  return (
    <div className="section-card">
      <h2>Fuentes</h2>

      {sources.length > 0 ? (
        <ul className="sources-list">
          {sources.map((source, index) => (
            <li key={index}>{source}</li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">Todavía no hay fuentes para mostrar.</p>
      )}
    </div>
  );
}

export default SourcesList;