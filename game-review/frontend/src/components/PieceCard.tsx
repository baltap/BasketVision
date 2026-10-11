import { useEffect, useMemo, useState } from 'react';
import type { Piece, Roster, Team } from '../api';
import { mmss, range } from '../format';
import { Pic, TeamPill } from './Bits';

export function explain(p: Piece, teamLabel = 'the'): string {
  const s = p.suggestion;
  const parts: string[] = [];
  if (p.status === 'mixed') parts.push('The reader saw different numbers in this piece, so it may be two players tracked as one.');
  else if (p.status === 'conflict') parts.push('Another piece with the same number overlaps this one, so this one was held back.');
  else if (!s.number) parts.push('No number was readable in any picture. Type it from the clip, or skip.');
  else if (s.count === 1) parts.push('Only one clear read. One read is not enough to name someone on its own, so it needs your yes.');
  else parts.push(`${s.number} was read ${s.count} times.`);
  if (p.crowdedReads > 0) parts.push(`${p.crowdedReads} read${p.crowdedReads > 1 ? 's were' : ' was'} taken in a crowd and ignored.`);
  const un = Object.entries(s.unlisted);
  if (un.length) parts.push(`Also read, but not on ${teamLabel} roster: ${un.map(([n, c]) => `#${n} x${c}`).join(', ')}.`);
  return parts.join(' ');
}

interface Props {
  piece: Piece;
  roster: Roster;
  busy: boolean;
  error: string | null;
  onNumber: (team: Team, number: string) => void;
  onIgnore: () => void;
  onSkip: () => void;
  onPlay: () => void;
}

export function PieceCard({ piece, roster, busy, error, onNumber, onIgnore, onSkip, onPlay }: Props) {
  const s = piece.suggestion;
  const guess: Team = useMemo(() => {
    if (piece.team === 'light' || piece.team === 'dark') return piece.team;
    if (s.number && roster.dark.includes(s.number) && !roster.light.includes(s.number)) return 'dark';
    return 'light';
  }, [piece.team, s.number, roster]);
  const [team, setTeam] = useState<Team>(guess);
  const [typed, setTyped] = useState('');
  useEffect(() => {
    setTeam(guess);
    setTyped('');
  }, [piece.id, guess]);

  const teamKnown = piece.team === 'light' || piece.team === 'dark';
  const chips = roster[team];

  return (
    <section className="card stack" style={{ gap: 20 }} aria-label="Current piece">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="title">{range(piece.startSec, piece.endSec)}</h2>
          <div className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span>{Math.round(piece.durSec)} s of footage</span>
            <TeamPill team={piece.team} />
            <span>
              {s.number ? `${s.number} read ${s.count} ${s.count === 1 ? 'time' : 'times'}, of ${s.reads} reads` : 'no number readable'}
            </span>
          </div>
        </div>
        <button className="btn" onClick={onPlay} aria-label={`Play this ${Math.round(piece.durSec)} second clip`}>
          Play this clip
        </button>
      </div>

      <div>
        <h3 style={{ fontWeight: 600, marginBottom: 8 }}>What the reader saw in this piece</h3>
        <div className="crops">
          {piece.crops.map((c) => (
            <div className="crop" key={c.file}>
              <div className="crop__img">
                <Pic src={c.url} alt={`Player at ${mmss(c.sec)}`} />
                <span className="crop__time">{mmss(c.sec)}</span>
              </div>
              <div className={`crop__label crop__label--${c.kind}`}>
                {c.kind === 'read' && `Read ${c.read}`}
                {c.kind === 'neighbor' && `Read ${c.read}, in a crowd`}
                {c.kind === 'none' && 'No number read'}
              </div>
            </div>
          ))}
        </div>
        <p className="card--tight" style={{ marginTop: 10, background: 'var(--wash)', borderRadius: 8, padding: '10px 12px', color: '#374151' }}>
          {explain(piece, piece.team === 'light' ? 'the light' : piece.team === 'dark' ? 'the dark' : 'the')}
        </p>
      </div>

      <div>
        <div className="row" style={{ alignItems: 'center', marginBottom: 8, gap: 12 }}>
          <h3 style={{ fontWeight: 600 }}>
            Who is this? <span className="muted" style={{ fontWeight: 400 }}>Tap a number from the {team} roster</span>
          </h3>
          {!teamKnown && (
            <div role="group" aria-label="Team" className="row" style={{ gap: 6 }}>
              {(['light', 'dark'] as Team[]).map((t) => (
                <button key={t} className={`btn ${team === t ? 'btn--primary' : 'btn--quiet'}`} aria-pressed={team === t} onClick={() => setTeam(t)}>
                  {t === 'light' ? 'Light' : 'Dark'}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="chips">
          {chips.map((n) => {
            const sug = n === s.number;
            const alt = n === s.alt;
            return (
              <button
                key={n}
                className={`numchip ${sug ? 'numchip--sug' : alt ? 'numchip--alt' : ''}`}
                disabled={busy}
                onClick={() => onNumber(team, n)}
                aria-label={`Number ${n}${sug ? ', suggested' : alt ? ', also read' : ''}`}
              >
                <span className="num">{n}</span>
                <small>{sug ? 'suggested' : alt ? 'also read' : ' '}</small>
              </button>
            );
          })}
        </div>
        <form
          className="row"
          style={{ alignItems: 'center', gap: 10, marginTop: 14 }}
          onSubmit={(e) => {
            e.preventDefault();
            if (typed) onNumber(team, typed);
          }}
        >
          <label htmlFor="typed" className="muted small">Or type a number and press Enter</label>
          <input
            id="typed"
            className="input input--num"
            inputMode="numeric"
            maxLength={2}
            value={typed}
            onChange={(e) => setTyped(e.target.value.replace(/\D/g, ''))}
            autoComplete="off"
          />
          {error && <span role="alert" style={{ color: 'var(--amber-ink)', fontWeight: 600 }}>{error}</span>}
        </form>
      </div>

      <div className="row" style={{ paddingTop: 16, borderTop: '1px solid var(--line)' }}>
        <button className="btn btn--quiet" onClick={onIgnore} disabled={busy} aria-keyshortcuts="n">
          Not a player (referee, coach, spectator)
        </button>
        <button className="btn btn--quiet" onClick={onSkip} disabled={busy} aria-keyshortcuts="s">
          Can't tell, skip
        </button>
      </div>
    </section>
  );
}
