interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
  phase: string;
}

export function PlaceholderPage({ eyebrow, title, description, phase }: PlaceholderPageProps) {
  return (
    <section className="page-section">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <span className="phase-chip">{phase}</span>
      </div>
      <div className="surface-card foundation-surface">
        <div className="surface-icon">—</div>
        <div>
          <h2>Surface ready for its implementation phase</h2>
          <p>
            This navigation entry is intentionally visible so the operating model is clear. It does not
            display fabricated data or pretend that future workflows have run.
          </p>
        </div>
      </div>
    </section>
  );
}
