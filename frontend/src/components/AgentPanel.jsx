const loadingSteps = [
  {
    agent: "Coordinador",
    status: "running",
    detail: "Clasificando la pregunta y preparando la ruta de busqueda.",
  },
  {
    agent: "Recuperador PDF",
    status: "pending",
    detail: "Listo para consultar los libros indexados.",
  },
  {
    agent: "Agente CSV",
    status: "pending",
    detail: "Listo para usar datos estructurados si la pregunta lo requiere.",
  },
  {
    agent: "Verificador",
    status: "pending",
    detail: "Validara la respuesta contra las fuentes recuperadas.",
  },
  {
    agent: "Redactor de reporte",
    status: "pending",
    detail: "Preparara timeline, confianza y reporte auditable.",
  },
];

function AgentPanel({ steps, loading, confidence }) {
  const visibleSteps = loading && (!steps || steps.length === 0) ? loadingSteps : steps;

  if (!loading && (!visibleSteps || visibleSteps.length === 0) && !confidence) {
    return null;
  }

  return (
    <div className="section-card agent-panel">
      <div className="agent-panel-header">
        <h2>Agent Trace</h2>
        {confidence ? (
          <span className={`confidence-pill confidence-${confidence.level?.toLowerCase().replaceAll(" ", "-")}`}>
            {confidence.level}
          </span>
        ) : null}
      </div>

      {confidence ? (
        <p className="confidence-reason">{confidence.reason}</p>
      ) : null}

      <div className="agent-step-list">
        {visibleSteps.map((step, index) => (
          <div className="agent-step" key={`${step.agent}-${index}`}>
            <span className={`agent-status agent-status-${step.status || "pending"}`} />
            <div>
              <p className="agent-name">{step.agent}</p>
              <p className="agent-detail">{step.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AgentPanel;
