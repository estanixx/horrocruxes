function SourcesList({ sources }) {
  return (
    <div className="section-card">
      <h2>Fuentes</h2>

      {sources.length > 0 ? (
        <ul className="sources-list">
          {sources.map((source, index) => (
            <li key={`${source.source}-${index}`} className="source-item">
              <p className="source-title">
                <strong>{source.source || `Fuente ${index + 1}`}</strong>
              </p>

              <p className="source-snippet">
                {source.snippet || "Sin fragmento disponible."}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">Todavía no hay fuentes para mostrar.</p>
      )}
    </div>
  );
}

export default SourcesList;