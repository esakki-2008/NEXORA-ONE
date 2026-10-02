export function formatDateTime(value: string | Date): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function formatShortTime(value: string | Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

export function formatDuration(start: string, end = new Date()): string {
  const elapsedMinutes = Math.max(0, Math.floor((new Date(end).getTime() - new Date(start).getTime()) / 60_000));
  if (elapsedMinutes < 1) return "< 1 min";
  if (elapsedMinutes < 60) return `${elapsedMinutes} min`;
  const hours = Math.floor(elapsedMinutes / 60);
  const minutes = elapsedMinutes % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function humanize(value: string): string {
  return value
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatUnknown(value: unknown): string {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
