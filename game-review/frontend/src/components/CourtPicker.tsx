import { useState } from 'react';
import { frameUrl } from '../api';

export type Point = [number, number];

/** Same gym and camera as the first two games: the playing area drawn once. */
export const DEFAULT_COURT: Point[] = [
  [0, 0.481], [0.25, 0.338], [0.781, 0.435], [0.885, 0.491], [1, 0.917], [1, 1], [0.302, 1],
];

/** The person clicks around the playing area; players with their feet inside count as "on court". */
export function CourtPicker({ video, t, value, onChange }: { video: string; t: number; value: Point[]; onChange: (p: Point[]) => void }) {
  const [failed, setFailed] = useState(false);
  const pts = value.map(([x, y]) => `${x * 100},${y * 100}`).join(' ');

  return (
    <div className="stack">
      <div
        className="frame courtpick"
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
          const y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
          onChange([...value, [Number(x.toFixed(4)), Number(y.toFixed(4))]]);
        }}
        role="application"
        aria-label="Click around the playing area to mark the court"
      >
        {failed ? (
          <div className="missing" style={{ minHeight: 200 }}>Could not read a picture from this video.</div>
        ) : (
          <img src={frameUrl(video, t)} alt="A frame from the game" onError={() => setFailed(true)} draggable={false} />
        )}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="courtpick__svg" aria-hidden="true">
          {value.length >= 2 && <polygon points={pts} fill="rgba(31,79,216,0.22)" stroke="#1f4fd8" strokeWidth="3" vectorEffect="non-scaling-stroke" />}
        </svg>
        {value.map(([x, y], i) => (
          <span key={i} className="courtpick__pt" style={{ left: `${x * 100}%`, top: `${y * 100}%` }}>{i + 1}</span>
        ))}
      </div>
      <div className="row" style={{ alignItems: 'center', gap: 8 }}>
        <button className="btn btn--quiet" onClick={() => onChange(value.slice(0, -1))} disabled={value.length === 0}>Undo last point</button>
        <button className="btn btn--quiet" onClick={() => onChange([])} disabled={value.length === 0}>Clear</button>
        <button className="btn btn--quiet" onClick={() => onChange(DEFAULT_COURT)}>Use the court from my first games</button>
        <span className="muted small">{value.length} points</span>
      </div>
    </div>
  );
}
