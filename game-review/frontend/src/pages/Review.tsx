import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, useGame, useQueue, useRoster } from '../api';
import type { Piece, Team } from '../api';
import { CoverageBar, ErrorBox, Loading, Pic, TeamPill } from '../components/Bits';
import { ClipPlayer } from '../components/ClipPlayer';
import { PieceCard } from '../components/PieceCard';
import { mmss, range } from '../format';

interface Answer {
  piece: Piece;
  kind: 'number' | 'ignore' | 'skip';
  team?: Team;
  number?: string;
}

export function ReviewPage() {
  const { gid = '' } = useParams();
  const qc = useQueryClient();
  const game = useGame(gid);
  const queue = useQueue(gid);
  const roster = useRoster(gid);
  const [selected, setSelected] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const items = queue.data?.items ?? [];
  const current = useMemo(
    () => items.find((i) => i.id === selected) ?? items.find((i) => !i.skipped) ?? items[0],
    [items, selected],
  );

  const refresh = () => qc.invalidateQueries({ queryKey: ['game', gid] });

  const answer = useMutation({
    mutationFn: (a: Answer) =>
      api.post(`/api/games/${gid}/answers`, {
        pieceId: a.piece.id, kind: a.kind, number: a.number, team: a.team,
      }),
    onSuccess: (_d, a) => {
      setError(null);
      const at = items.findIndex((i) => i.id === a.piece.id);
      const next = items[at + 1] ?? items.find((i) => i.id !== a.piece.id);
      setSelected(a.kind === 'skip' ? next?.id ?? null : null);
      setPlaying(false);
      setToast(
        a.kind === 'number'
          ? `${a.team === 'light' ? 'Light' : 'Dark'} #${a.number} confirmed for ${range(a.piece.startSec, a.piece.endSec)}`
          : a.kind === 'ignore' ? 'Marked not a player' : 'Skipped, it stays in the queue',
      );
      void refresh();
    },
    onError: (e: Error) => setError(e.message),
  });

  const undo = useMutation({
    mutationFn: () => api.post<{ ok: boolean; undone?: { pieceId: string } }>(`/api/games/${gid}/undo`),
    onSuccess: (r) => {
      if (r.undone) setSelected(r.undone.pieceId);
      setToast(r.ok ? 'Undone' : null);
      setError(null);
      void refresh();
    },
  });

  // keyboard: S skip, N not a player, U undo, arrows move through the queue
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return;
      if (!current) return;
      const idx = items.findIndex((i) => i.id === current.id);
      if (e.key === 's') answer.mutate({ piece: current, kind: 'skip' });
      else if (e.key === 'n') answer.mutate({ piece: current, kind: 'ignore' });
      else if (e.key === 'u') undo.mutate();
      else if (e.key === 'ArrowDown' && idx < items.length - 1) setSelected(items[idx + 1].id);
      else if (e.key === 'ArrowUp' && idx > 0) setSelected(items[idx - 1].id);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [current, items, answer, undo]);

  if (queue.isLoading || game.isLoading) return <Loading label="Loading the review queue" />;
  if (queue.error || !queue.data || !game.data) return <ErrorBox error={queue.error ?? game.error} />;

  const cov = queue.data.coverage;
  const big = (roster.data?.unlisted ?? []).filter((u) => !u.elsewhere && u.reads >= 20);
  const video = `/files/${gid}/media/proxy.mp4`;

  return (
    <>
      <section className="card card--tight row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <strong>Footage with a player name</strong>
            <span className="num" style={{ fontSize: 28 }}>{(cov.namedPct + cov.confirmedPct).toFixed(1)}%</span>
          </div>
          <CoverageBar cov={cov} />
        </div>
        <div className="row" style={{ alignItems: 'center', gap: 24 }}>
          <div>
            <div className="num" style={{ fontSize: 28 }}>{cov.queueCount}</div>
            <div className="muted small">pieces left</div>
          </div>
          <button className="btn" onClick={() => undo.mutate()} disabled={queue.data.history === 0 || undo.isPending} aria-keyshortcuts="u">
            Undo last
          </button>
        </div>
      </section>

      {big.length > 0 && (
        <div className="callout row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ flex: '1 1 420px' }}>
            <strong>
              {big.slice(0, 3).map((u) => `#${u.number}`).join(', ')} {big.length === 1 ? 'was' : 'were'} read many times but {big.length === 1 ? 'is' : 'are'} not on either
              roster.
            </strong>{' '}
            Unlisted numbers are held back here, never dropped.
          </div>
          <Link className="btn btn--amber" to={`/g/${gid}/roster`}>Review the roster</Link>
        </div>
      )}

      {!current ? (
        <div className="card stack" role="status">
          <h2 className="title">Nothing left in the queue</h2>
          <p className="muted">
            Every piece of 3 seconds or more has a name or has been set aside.
            {cov.skippedCount > 0 && ` ${cov.skippedCount} skipped pieces stay open.`}
          </p>
          <div><Link className="btn btn--primary" to={`/g/${gid}/team`}>See the team overview</Link></div>
        </div>
      ) : (
        <div className="row">
          <nav className="queue" aria-label="Review queue">
            <div className="eyebrow">Queue, longest first</div>
            {items.map((it) => (
              <button
                key={it.id}
                className="qitem"
                aria-current={it.id === current.id}
                onClick={() => { setSelected(it.id); setPlaying(false); setError(null); }}
              >
                <span className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                  <strong>{range(it.startSec, it.endSec)}</strong>
                  <TeamPill team={it.team} />
                </span>
                <span className="qitem__state">
                  <span className="dot" style={{ background: it.skipped ? 'var(--grey)' : 'var(--amber)' }} aria-hidden="true" />
                  {Math.round(it.durSec)} s · {it.skipped ? 'Skipped' : it.suggestion.number ? `Maybe #${it.suggestion.number}` : 'Needs you'}
                </span>
              </button>
            ))}
          </nav>

          <div className="review stack" style={{ gap: 16 }}>
            {playing && (
              <div className="card card--tight">
                {game.data.footage.video ? (
                  <ClipPlayer src={video} start={current.startSec} end={current.endSec} />
                ) : (
                  <p className="muted">The video was deleted from this Mac, so there is nothing to play.</p>
                )}
              </div>
            )}
            <PieceCard
              piece={current}
              roster={queue.data.roster}
              busy={answer.isPending}
              error={error}
              onPlay={() => setPlaying((p) => !p)}
              onNumber={(team, number) => answer.mutate({ piece: current, kind: 'number', team, number })}
              onIgnore={() => answer.mutate({ piece: current, kind: 'ignore' })}
              onSkip={() => answer.mutate({ piece: current, kind: 'skip' })}
            />
            {toast && (
              <div className="toast" role="status">
                <span>{toast}</span>
                <button className="btn" onClick={() => undo.mutate()}>Undo</button>
              </div>
            )}
          </div>

          <aside className="context" aria-label="Context">
            <div className="card card--tight">
              <h3 style={{ fontWeight: 600, marginBottom: 8 }}>Where in the camera view</h3>
              <div className="frame">
                <Pic src={current.thumb.url} alt="Camera view at the middle of this piece" />
                <div
                  className="frame__box"
                  style={{
                    left: `${current.thumb.box[0] * 100}%`,
                    top: `${current.thumb.box[1] * 100}%`,
                    width: `${(current.thumb.box[2] - current.thumb.box[0]) * 100}%`,
                    height: `${(current.thumb.box[3] - current.thumb.box[1]) * 100}%`,
                  }}
                />
              </div>
              <p className="muted small" style={{ marginTop: 8 }}>
                Frame at {mmss(current.thumb.sec)}. The box is this player.
              </p>
            </div>
            <div className="card card--tight small">
              <h3 style={{ fontWeight: 600, marginBottom: 6 }}>Shortcuts</h3>
              <div className="muted">
                <div><strong>Type</strong> a number, then Enter</div>
                <div><strong>S</strong> skip · <strong>N</strong> not a player · <strong>U</strong> undo</div>
                <div><strong>Up / Down</strong> move through the queue</div>
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
