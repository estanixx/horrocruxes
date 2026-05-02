function SourcesList({ sources }) {
  return (
    <div className="section-card">
      <h2>Sources</h2>

      {sources.length > 0 ? (
        <ul className="sources-list">
          {sources.map((source, index) => (
            <li key={`${source.source}-${index}`} className="source-item">
              <p className="source-title">
                <strong>{source.source || `Source ${index + 1}`}</strong>
              </p>

              <p className="source-snippet">
                {source.snippet || "No snippet available."}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-text">There are no sources to display.</p>
      )}
    </div>
  );
}

export default SourcesList;