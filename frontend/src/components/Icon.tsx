import type { SVGProps } from "react";

export type IconName =
  | "activity"
  | "agents"
  | "arrow"
  | "bell"
  | "business"
  | "check"
  | "chevron"
  | "clock"
  | "close"
  | "command"
  | "database"
  | "evidence"
  | "filter"
  | "history"
  | "incidents"
  | "investigation"
  | "layers"
  | "menu"
  | "operations"
  | "refresh"
  | "reports"
  | "remediation"
  | "search"
  | "settings"
  | "shield"
  | "verification";

const paths: Record<IconName, JSX.Element> = {
  activity: <><path d="M3 12h4l2-7 4 14 2-7h6" /><path d="M3 20h18" /></>,
  agents: <><circle cx="8" cy="8" r="3" /><circle cx="16" cy="8" r="3" /><path d="M2.5 20c.5-3 2.5-4.5 5.5-4.5s5 1.5 5.5 4.5" /><path d="M13 16c.8-.4 1.8-.6 3-.6 3 0 5 1.5 5.5 4.6" /></>,
  arrow: <><path d="M5 12h13" /><path d="m13 6 6 6-6 6" /></>,
  bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
  business: <><path d="M4 20V8l8-4 8 4v12" /><path d="M2 20h20" /><path d="M8 20v-5h8v5" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m8 10 4 4 4-4" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  close: <><path d="m6 6 12 12" /><path d="m18 6-12 12" /></>,
  command: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
  evidence: <><path d="M6 3h9l3 3v15H6z" /><path d="M15 3v4h4M9 12h6M9 16h6" /></>,
  filter: <><path d="M4 6h16M7 12h10M10 18h4" /></>,
  history: <><path d="M4 12a8 8 0 1 0 2-5" /><path d="M4 4v5h5" /><path d="M12 8v5l3 2" /></>,
  incidents: <><path d="M12 3 3.5 19h17z" /><path d="M12 9v4M12 16v.5" /></>,
  investigation: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /><path d="M8 10.5h5" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 12 9 5 9-5" /><path d="m3 16 9 5 9-5" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  operations: <><path d="M5 20V9M12 20V4M19 20v-7" /><path d="M3 20h18" /><circle cx="5" cy="6" r="2" /><circle cx="19" cy="11" r="2" /><circle cx="12" cy="2" r="1" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.5-4L3 10" /><path d="M3 5v5h5" /><path d="M4 13a8 8 0 0 0 14.5 4L21 14" /><path d="M21 19v-5h-5" /></>,
  reports: <><path d="M5 3h10l4 4v14H5z" /><path d="M15 3v5h5M8 12h8M8 16h8" /></>,
  remediation: <><path d="m14.5 6.5 3-3a4 4 0 0 1 5 5l-3 3" /><path d="m13 8-5 5" /><path d="m4 16-1 5 5-1 10-10-4-4z" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  settings: <><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z" /><path d="m19.4 15 .1.1a2 2 0 1 1-2.8 2.8l-.1-.1a2 2 0 0 0-3.4 1.4v.3a2 2 0 1 1-4 0v-.2a2 2 0 0 0-3.4-1.4l-.1.1A2 2 0 1 1 3 15.2l.1-.1A2 2 0 0 0 1.7 12h-.2a2 2 0 1 1 0-4h.2a2 2 0 0 0 1.4-3.4L3 4.5a2 2 0 1 1 2.8-2.8l.1.1A2 2 0 0 0 9.3.4V.2a2 2 0 1 1 4 0v.2a2 2 0 0 0 3.4 1.4l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A2 2 0 0 0 20.8 8h.2a2 2 0 1 1 0 4h-.2a2 2 0 0 0-1.4 3.4z" /></>,
  shield: <><path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z" /><path d="m8 12 2.5 2.5L16 9" /></>,
  verification: <><path d="M12 3 4 6v6c0 4.5 3.1 7.7 8 9 4.9-1.3 8-4.5 8-9V6z" /><path d="m8 12 2.5 2.5L16 9" /></>
};

export function Icon({ name, size = 16, strokeWidth = 1.7, ...props }: { name: IconName; size?: number; strokeWidth?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
