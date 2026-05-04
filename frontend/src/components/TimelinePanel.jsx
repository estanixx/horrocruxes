function TimelinePanel({ events }) {
  if (!events || events.length === 0) {
    return null;
  }

  return (
    <div className="section-card timeline-panel">
      <h2>Timeline</h2>
      <div className="timeline-list">
        {events.map((event, index) => (
          <div className="timeline-event" key={`${event.label}-${index}`}>
            <div className="timeline-marker">{index + 1}</div>
            <div>
              <p className="timeline-label">{event.label}</p>
              <p className="timeline-detail">{event.detail}</p>
              {event.source ? (
                <p className="timeline-source">{event.source}</p>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TimelinePanel;
