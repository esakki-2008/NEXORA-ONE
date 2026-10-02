interface LoadingStateProps {
  label?: string;
  rows?: number;
}

export function LoadingState({ label = "Loading data…", rows = 3 }: LoadingStateProps) {
  return (
    <div className="loading-block" role="status" aria-live="polite" aria-label={label}>
      <div className="loading-label"><span className="loading-dot" />{label}</div>
      <div className="skeleton-stack" aria-hidden="true">
        {Array.from({ length: rows }).map((_, index) => (
          <div className="skeleton-row" key={index}>
            <span className="skeleton short" />
            <span className="skeleton long" />
            <span className="skeleton medium" />
          </div>
        ))}
      </div>
    </div>
  );
}
