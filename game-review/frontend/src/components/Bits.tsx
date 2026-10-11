import { useState } from 'react';
import type { Coverage, PieceTeam } from '../api';
import { teamName } from '../format';

export function Loading({ label }: { label: string }) {
  return <div className="skeleton" role="status" aria-busy="true" aria-label={label} />;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="callout" role="alert">
      <strong>Something went wrong.</strong> {msg}
      <div className="small">Is the backend running? It listens on port 8000.</div>
    </div>
  );
}

export function TeamPill({ team }: { team: PieceTeam }) {
  const cls = team === 'light' ? 'pill--light' : team === 'dark' ? 'pill--dark' : 'pill--amber';
  return <span className={`pill ${cls}`}>{teamName(team)}</span>;
}

export function CoverageBar({ cov, showLegend = true }: { cov: Coverage; showLegend?: boolean }) {
  const named = Math.max(0, cov.namedPct);
  const confirmed = Math.max(0, cov.confirmedPct);
  return (
    <div className="cover">
      <div className="cover__bar" role="img" aria-label={`${(named + confirmed).toFixed(1)} percent of player footage has a name`}>
        <div className="cover__named" style={{ width: `${named}%` }} />
        <div className="cover__confirmed" style={{ width: `${confirmed}%` }} />
      </div>
      {showLegend && (
        <div className="legend">
          <span><span className="swatch swatch--named" />Named from numbers {cov.namedPct}%</span>
          <span><span className="swatch swatch--confirmed" />Confirmed by you {cov.confirmedPct}%</span>
          <span><span className="swatch swatch--open" />Still unnamed {cov.openPct}%</span>
        </div>
      )}
    </div>
  );
}

/** A picture that falls back to a plain note when the footage was deleted or is missing. */
export function Pic({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div className="missing">Picture not available</div>;
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}
