import { useState } from 'react';
import type { Roster, Team } from '../api';

const TEAMS: { team: Team; title: string }[] = [
  { team: 'light', title: 'Team A · light jerseys' },
  { team: 'dark', title: 'Team B · dark jerseys' },
];

const sortNumbers = (xs: string[]) => [...new Set(xs)].sort((a, b) => Number(a) - Number(b));

function TeamColumn({ team, title, numbers, onChange }: { team: Team; title: string; numbers: string[]; onChange: (n: string[]) => void }) {
  const [draft, setDraft] = useState('');
  const add = () => {
    const n = String(Number(draft.replace(/\D/g, '')));
    if (draft.replace(/\D/g, '') && !numbers.includes(n)) onChange(sortNumbers([...numbers, n]));
    setDraft('');
  };
  return (
    <section className="card stack" style={{ flex: '1 1 320px', minWidth: 0 }}>
      <div className="row" style={{ alignItems: 'center', gap: 12 }}>
        <span className={`dot dot--${team}`} style={{ width: 28, height: 28 }} aria-hidden="true" />
        <h2 className="eyebrow">{title}</h2>
      </div>
      <div className="chips">
        {numbers.map((n) => (
          <span className="rchip" key={n}>
            <span className="num">{n}</span>
            <button aria-label={`Remove number ${n} from the ${team} roster`} onClick={() => onChange(numbers.filter((x) => x !== n))}>
              ×
            </button>
          </span>
        ))}
        {numbers.length === 0 && <span className="muted small">No numbers yet</span>}
      </div>
      <form
        className="row"
        style={{ alignItems: 'center', gap: 10 }}
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <label className="muted small" htmlFor={`add-${team}`}>Add a number</label>
        <input id={`add-${team}`} className="input input--num" inputMode="numeric" maxLength={2} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button className="btn" type="submit">Add</button>
      </form>
      <div className="muted small">{numbers.length} numbers</div>
    </section>
  );
}

export function RosterEditor({ roster, onChange }: { roster: Roster; onChange: (r: Roster) => void }) {
  return (
    <div className="row">
      {TEAMS.map((t) => (
        <TeamColumn key={t.team} team={t.team} title={t.title} numbers={roster[t.team]} onChange={(n) => onChange({ ...roster, [t.team]: n })} />
      ))}
    </div>
  );
}
