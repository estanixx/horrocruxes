import { useState } from "react";

function ReportPanel({ report }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!report) {
    return null;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="section-card report-panel">
      <div className="report-header">
        <h2>Research Report</h2>
        <div className="report-actions">
          <button type="button" onClick={handleCopy} className="small-action-btn">
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="small-action-btn"
          >
            {expanded ? "Hide" : "Show"}
          </button>
        </div>
      </div>

      {expanded ? (
        <pre className="report-markdown">{report}</pre>
      ) : (
        <p className="empty-text">
          Markdown report generated with answer, confidence, timeline and sources.
        </p>
      )}
    </div>
  );
}

export default ReportPanel;
