import { Link, useParams } from 'react-router-dom';
import { useTeam } from '../api';
import type { PlayerRow, Team, TeamData } from '../api';
import { ErrorBox, Loading } from '../components/Bits';
import { mmss, playerPath, range } from '../format';

function Minutes({ gid, team, rows, windowSec }: { gid: string; team: Team; rows: PlayerRow[]; windowSec: number }) {
  return (
    <section className="card" style={{ flex: '1 1 340px', minWidth: 0 }} aria-label={`${team} team minutes`}>
      <div className="row" style={{ gap: 10, alignItems: 'center' }}>
        <span className={`dot dot--${team}`} aria-hidden="true" />
        <h2 className="title title--sm">{team === 'light' ? 'Team A · light' : 'Team B · dark'}</h2>
      </div>
      <p className="muted small" style={{ margin: '4px 0 12px' }}>
        On court, named footage only, of a {mmss(windowSec)} window
      </p>
      {rows.length === 0 && <p className="muted">No named footage yet for this team.</p>}
      <div className="bars">
        {rows.map((r) => (
          <div className="bars__row" key={r.key}>
            <Link className="bars__num num" to={playerPath(gid, r.key)} aria-label={`Open player number ${r.number}`}>
              #{r.number}
            </Link>
            <div className="bars__track">
              <div className="bars__fill" style={{ width: `${Math.min(100, (r.seconds / windowSec) * 100)}%` }} />
            </div>
            <div className="bars__time">{mmss(r.seconds)}</div>
            <div className={`bars__note ${r.tiny ? 'bars__note--warn' : ''}`}>
              {r.tiny ? 'check' : `${r.shifts} ${r.shifts === 1 ? 'stretch' : 'stretches'}`}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Lineups({ data }: { data: TeamData }) {
  const block = (team: Team, title: string) => (
    <div>
      <div className="eyebrow" style={{ marginBottom: 6 }}>{title}</div>
      <div className="stack" style={{ gap: 8 }}>
        {data.lineups[team].length === 0 && <p className="muted small">Not enough named footage for a lineup yet.</p>}
        {data.lineups[team].map((l) => (
          <div className="unit" key={l.units}>
            <span className="num">{l.units}</span>
            <strong>{mmss(l.seconds)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
  return (
    <section className="card stack" style={{ gap: 16 }}>
      <div>
        <h2 className="title title--sm">Lineups</h2>
        <p className="muted small">Five on court together. A ? is a slot nobody was named for.</p>
      </div>
      {block('light', 'Team A · light')}
      {block('dark', 'Team B · dark')}
    </section>
  );
}

function Checks({ gid, data }: { gid: string; data: TeamData }) {
  const nothing = data.overfull.length === 0 && data.tiny.length === 0;
  return (
    <section className="card stack" style={{ borderColor: 'var(--amber)', borderWidth: 2 }}>
      <h2 className="title title--sm">Worth a look before you trust these</h2>
      {nothing && <p className="muted">Nothing stands out.</p>}
      {data.overfull.map((o) => (
        <div key={`${o.team}-${o.startSec}`}>
          <div style={{ fontWeight: 600, color: 'var(--amber-ink)' }}>
            {o.keys.length} {o.team} players named at once
          </div>
          <div className="muted small">
            {range(o.startSec, o.endSec)}: {o.keys.map((k) => `#${k.split('#')[1]}`).join(', ')}. A team has five, so one
            name is probably wrong.
          </div>
          <Link className="btn" style={{ marginTop: 6, borderColor: 'var(--blue)', color: 'var(--blue)' }} to={`/g/${gid}/timeline`}>
            See it on the timeline
          </Link>
        </div>
      ))}
      {data.tiny.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, color: 'var(--amber-ink)' }}>Tiny stretches that may be misreads</div>
          <div className="muted small">
            {data.tiny.map((t) => `${t.key.split('#')[0]} #${t.key.split('#')[1]} for ${mmss(t.seconds)}`).join(', ')}.
          </div>
        </div>
      )}
      <div>
        <div style={{ fontWeight: 600 }}>On the roster, not seen in this window</div>
        <div className="muted small">
          Light {data.notSeen.light.length ? data.notSeen.light.map((n) => `#${n}`).join(', ') : 'none'}. Dark{' '}
          {data.notSeen.dark.length ? data.notSeen.dark.map((n) => `#${n}`).join(', ') : 'none'}. This is a short
          sample, so that is expected.
        </div>
      </div>
    </section>
  );
}

export function TeamPage() {
  const { gid = '' } = useParams();
  const team = useTeam(gid);
  if (team.isLoading) return <Loading label="Loading team overview" />;
  if (team.error || !team.data) return <ErrorBox error={team.error} />;
  const d = team.data;
  const unnamed = (100 - d.coverage.namedPct - d.coverage.confirmedPct).toFixed(0);

  return (
    <>
      <div className="callout row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ flex: '1 1 420px' }}>
          <strong>These minutes are a floor, not a total.</strong> About {unnamed}% of player footage is still unnamed, so
          every figure here can only go up. {d.coverage.queueCount} pieces are open.
        </div>
        <Link className="btn btn--amber" to={`/g/${gid}/review`}>
          Review the open pieces
        </Link>
      </div>
      <div className="row">
        <div className="row" style={{ flex: '999 1 640px', minWidth: 0 }}>
          <Minutes gid={gid} team="light" rows={d.players.light} windowSec={d.windowSec} />
          <Minutes gid={gid} team="dark" rows={d.players.dark} windowSec={d.windowSec} />
          <div className="card card--tight card--dashed muted small" style={{ flex: '1 1 100%' }}>
            <strong>Plus/minus</strong> needs the scoreboard read. <strong>Points, assists and rebounds</strong> are not
            detected; they will be tapped in while reviewing. <strong>Click a number</strong> to open that player.
          </div>
        </div>
        <div className="stack" style={{ flex: '1 1 340px', maxWidth: 420 }}>
          <Lineups data={d} />
          <Checks gid={gid} data={d} />
        </div>
      </div>
    </>
  );
}
