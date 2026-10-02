import { Link } from "react-router-dom";

import { Icon } from "../components/Icon";
import { PageHeader } from "../components/PageHeader";
import { Panel } from "../components/Panel";

interface PlaceholderPageProps {
  eyebrow: string;
  title: string;
  description: string;
  phase: string;
  path?: string;
}

export function PlaceholderPage({ eyebrow, title, description, phase, path }: PlaceholderPageProps) {
  return (
    <section className="page-section">
      <PageHeader eyebrow={eyebrow} title={title} description={description} meta={<><Icon name="layers" size={13} /> Planned boundary · {phase}</>} />
      <Panel className="locked-surface">
        <div className="locked-icon"><Icon name="shield" size={21} /></div>
        <div>
          <span className="eyebrow">BOUNDARY VISIBLE / WORKFLOW LOCKED</span>
          <h2>This surface is ready for its implementation phase</h2>
          <p>This navigation entry is intentionally visible so the operating model is clear. It does not display fabricated data or pretend that a future workflow has run.</p>
          {path ? <Link className="text-link" to={path}>Open related surface <Icon name="arrow" size={13} /></Link> : null}
        </div>
      </Panel>
    </section>
  );
}
