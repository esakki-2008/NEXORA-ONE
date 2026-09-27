import { Icon } from "./Icon";

interface ErrorStateProps {
  title?: string;
  description: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Unable to load data", description, onRetry }: ErrorStateProps) {
  return (
    <div className="message-state error-state" role="alert">
      <div className="message-icon"><Icon name="incidents" size={18} /></div>
      <div>
        <span className="eyebrow">REQUEST FAILED</span>
        <h3>{title}</h3>
        <p>{description}</p>
        {onRetry ? (
          <button className="secondary-button" type="button" onClick={onRetry}>
            <Icon name="refresh" size={14} /> Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}
