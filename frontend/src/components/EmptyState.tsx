interface EmptyStateProps {
  eyebrow?: string;
  title: string;
  description: string;
}

export function EmptyState({ eyebrow = "NO DATA", title, description }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="eyebrow">{eyebrow}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
