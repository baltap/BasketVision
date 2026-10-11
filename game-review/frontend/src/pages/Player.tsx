import { Link, useParams } from 'react-router-dom';
import { useGame, usePlayer, useTimeline } from '../api';
import type { Segment } from '../api';
import { ErrorBox, Loading, Pic, TeamPill } from '../components/Bits';
import { Moments } from '../components/Moments';
import { PlayerRail } from '../components/PlayerRail';
import { keyParts, mmss, playerKey, range } from '../format';

export function PlayerPage() {
  const { gid = '', slug = '' } = useParams();
  const key = playerKey(slug);
  const { team, number } = keyParts(key);
  const game = useGame(gid);
  const p = usePlayer(gid, key);
  const tl = useTimeline(gid);

  if (p.isLoading) return <Loading label="Loading player" />;
  if (p.error || !p.data) return <ErrorBox error={p.error} />;
  const d = p.data;
  const dur = d.windowSec;
  const total = d.namedSeconds + d.confirmedSeconds || 1;
  const namedPct = Math.round((100 * d.namedSeconds) / total);
  const confirmedPct = 100 - namedPct;
  const max = Math.max(1, ...d.heat.flat());
  const gy = d.heat.length;
  const gx = d.heat[0]?.length ?? 1;
  const strongest = d.pieces[0];
  const lane = tl.data?.lanes.find((l) => l.key === key);
  const strip: Segment[] = lane?.segments ?? d.presence.map((s) => ({ ...s, state: 'named' as const }));
  const s = d.stats;

  return (
    <div className="row">
      <PlayerRail gid={gid} current={key} />

      <div className="stack" style={{ flex: '999 1 560px', minWidth: 0, gap: 16 }}>
        <p className="small muted">
          <Link to={`/g/${gid}/team`}>Team overview</Link> / {team === 'light' ? 'Team A' : 'Team B'} / #{number}
        </p>

        <section className="card row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="row" style={{ alignItems: 'center', gap: 24 }}>
            <div className="num hero-num" aria-label={`Number ${number}`}>{number}</div>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 600 }}>[Player name]</h1>
              <div className="row" style={{ gap: 8, marginTop: 6 }}>
                <TeamPill team={team} />
                <span className="pill pill--blue">
                  {confirmedPct > 0 ? `${confirmedPct}% confirmed by you` : `${namedPct}% named from numbers`}
                </span>
              </div>
            </div>
          </div>
          <p className="muted" style={{ maxWidth: 380, background: 'var(--wash)', borderRadius: 10, padding: '12px 14px' }}>
            <strong style={{ color: 'var(--ink)' }}>How sure are we?</strong>{' '}
            {strongest
              ? `The number ${number} was read ${strongest.suggestion.count} times in this player's strongest piece (${range(strongest.startSec, strongest.endSec)}).`
              : 'This player was named by hand.'}{' '}
            {d.confirmedSeconds > 0 ? `${mmss(d.confirmedSeconds)} was confirmed by you.` : 'Nothing confirmed by you yet.'}
          </p>
        </section>

        <div className="row">
          <div className="card stat"><div className="muted small">On court, named</div><div className="num">{mmss(d.seconds)}</div><div className="muted small">of {mmss(dur)} window</div></div>
          <div className="card stat"><div className="muted small">Shifts seen</div><div className="num">{d.shifts}</div><div className="muted small">continuous pieces</div></div>
          <div className="card stat card--dashed">
            <div className="muted small">Distance and top speed</div>
            <div style={{ fontWeight: 600, marginTop: 6 }}>[Needs court calibration]</div>
            <div className="muted small">Not computed yet.</div>
          </div>
          <div className={`card stat ${s.total === 0 ? 'card--dashed' : ''}`}>
            <div className="muted small">Points · assists · rebounds</div>
            {s.total === 0 ? (
              <>
                <div style={{ fontWeight: 600, marginTop: 6 }}>[Tapped in by a person]</div>
                <div className="muted small">Tag moments below.</div>
              </>
            ) : (
              <>
                <div className="num">{s.points} · {s.assists} · {s.rebounds}</div>
                <div className="muted small">{s.made} made, {s.missed} missed · tapped in by you</div>
              </>
            )}
          </div>
        </div>

        <section className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
            <strong>Presence on court</strong>
            <span className="muted small">0:00 to {mmss(dur)}</span>
          </div>
          <div className="lane__track" style={{ height: 30, cursor: 'default' }} role="img" aria-label="Time on court">
            {strip.map((g, i) => (
              <div key={`s${i}`} className={`seg seg--${g.state ?? 'named'}`}
                   style={{ left: `${(g.start / dur) * 100}%`, width: `${Math.max(0.3, ((g.end - g.start) / dur) * 100)}%` }} />
            ))}
            {d.maybe.map((g, i) => (
              <div key={`m${i}`} className="seg seg--open"
                   style={{ left: `${(g.start / dur) * 100}%`, width: `${Math.max(0.3, ((g.end - g.start) / dur) * 100)}%` }} />
            ))}
          </div>
          <div className="legend" style={{ marginTop: 10 }}>
            <span><span className="swatch swatch--named" />Named from numbers</span>
            <span><span className="swatch swatch--confirmed" />Confirmed by you</span>
            <span><span className="swatch swatch--stripe" />Might be this player, needs you{d.maybe.length ? ` (${d.maybe.length})` : ''}</span>
          </div>
        </section>

        <div className="row">
          <div className="stack" style={{ flex: '1 1 360px', minWidth: 0, gap: 16 }}>
            <section className="card">
              <strong>Where #{number} spent the time</strong>
              <div className="frame" style={{ marginTop: 10 }}>
                {strongest && <Pic src={strongest.thumb.url} alt="Camera view" />}
                <div className="heat" style={{ gridTemplateColumns: `repeat(${gx}, 1fr)`, gridTemplateRows: `repeat(${gy}, 1fr)` }} aria-hidden="true">
                  {d.heat.flatMap((row, y) =>
                    row.map((v, x) => (
                      <div key={`${x}-${y}`} style={{ background: v ? `rgba(31,79,216,${0.15 + 0.7 * (v / max)})` : 'transparent' }} />
                    )),
                  )}
                </div>
              </div>
              <p className="muted small" style={{ marginTop: 8 }}>
                Foot positions in the camera image. A top-down court map needs the four court corners marked first.
              </p>
            </section>
            <section className="card stack">
              <strong>Evidence: strongest pieces</strong>
              {d.pieces.slice(0, 3).map((pc) => (
                <div key={pc.id}>
                  <div className="small muted" style={{ marginBottom: 6 }}>
                    {range(pc.startSec, pc.endSec)} · {Math.round(pc.durSec)} s · {pc.state === 'confirmed' ? 'confirmed by you' : `read ${pc.suggestion.count} times`}
                  </div>
                  <div className="crops">
                    {pc.crops.slice(0, 4).map((c) => (
                      <div className="crop" key={c.file}>
                        <div className="crop__img"><Pic src={c.url} alt={`Player at ${mmss(c.sec)}`} /></div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </section>
          </div>

          <div style={{ flex: '1 1 360px', minWidth: 0 }}>
            <Moments gid={gid} data={d} hasVideo={game.data?.footage.video ?? false} />
          </div>
        </div>
      </div>
    </div>
  );
}
