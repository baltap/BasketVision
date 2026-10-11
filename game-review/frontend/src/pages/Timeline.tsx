import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useGame, useOverlay, useTimeline } from '../api';
import type { OverlayData, Segment } from '../api';
import { CoverageBar, ErrorBox, Loading } from '../components/Bits';
import { keyLabel, mmss, playerPath } from '../format';

const COLORS = { named: '#7fa0f2', confirmed: '#1f4fd8', open: '#e8892b', nonplayer: '#9ca3af' } as const;

function useBoxIndex(overlay: OverlayData | undefined) {
  return useMemo(() => {
    const idx = new Map<number, OverlayData['items']>();
    overlay?.items.forEach((it) => {
      const list = idx.get(it[0]);
      if (list) list.push(it);
      else idx.set(it[0], [it]);
    });
    return idx;
  }, [overlay]);
}

function VideoWithBoxes({ src, overlay, videoRef, onTime }: {
  src: string;
  overlay: OverlayData;
  videoRef: React.RefObject<HTMLVideoElement>;
  onTime: (t: number) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const index = useBoxIndex(overlay);

  const draw = useCallback(() => {
    const v = videoRef.current;
    const c = canvas.current;
    if (!v || !c) return;
    const w = v.clientWidth;
    const h = v.clientHeight;
    if (c.width !== w || c.height !== h) {
      c.width = w;
      c.height = h;
    }
    const ctx = c.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, w, h);
    const t = Math.floor((v.currentTime * overlay.fps) / overlay.step);
    const list = index.get(t) ?? index.get(t - 1) ?? [];
    ctx.font = '600 13px "IBM Plex Sans", sans-serif';
    for (const [, pi, x1, y1, x2, y2] of list) {
      const lab = overlay.labels[pi];
      if (!lab || lab.state === 'nonplayer') continue;
      const color = COLORS[lab.state];
      const bx = x1 * w, by = y1 * h, bw = (x2 - x1) * w, bh = (y2 - y1) * h;
      ctx.lineWidth = lab.state === 'confirmed' ? 3 : 2;
      ctx.setLineDash(lab.state === 'open' ? [6, 4] : []);
      ctx.strokeStyle = color;
      ctx.strokeRect(bx, by, bw, bh);
      const text = keyLabel(lab.key);
      const tw = ctx.measureText(text).width + 10;
      ctx.setLineDash([]);
      ctx.fillStyle = color;
      ctx.fillRect(bx, by - 20, tw, 20);
      ctx.fillStyle = lab.state === 'confirmed' ? '#fff' : '#111827';
      ctx.fillText(text, bx + 5, by - 6);
    }
  }, [index, overlay, videoRef]);

  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    let raf = 0;
    let last = 0;
    const loop = () => {
      draw();
      const now = performance.now();
      if (now - last > 100) {
        last = now;
        onTime(v.currentTime);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [draw, onTime, videoRef]);

  return (
    <div className="frame" style={{ position: 'relative' }}>
      <video ref={videoRef} src={src} controls muted playsInline preload="auto" />
      <canvas ref={canvas} aria-hidden="true" style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }} />
    </div>
  );
}

function LaneTrack({ segs, kind, duration, onSeek }: {
  segs: Segment[];
  kind: 'named' | 'confirmed' | 'open' | 'nonplayer';
  duration: number;
  onSeek: (sec: number) => void;
}) {
  return (
    <div
      className="lane__track"
      role="presentation"
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        onSeek(((e.clientX - r.left) / r.width) * duration);
      }}
    >
      {segs.map((s, i) => (
        <div
          key={i}
          className={`seg seg--${s.state ?? kind}`}
          style={{ left: `${(s.start / duration) * 100}%`, width: `${Math.max(0.3, ((s.end - s.start) / duration) * 100)}%` }}
        />
      ))}
    </div>
  );
}

export function TimelinePage() {
  const { gid = '' } = useParams();
  const game = useGame(gid);
  const tl = useTimeline(gid);
  const overlay = useOverlay(gid);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const onTime = useCallback((t: number) => setTime(t), []);

  const seek = (sec: number) => {
    const v = videoRef.current;
    if (v) v.currentTime = Math.max(0, Math.min(sec, v.duration || sec));
  };

  if (tl.isLoading || overlay.isLoading || game.isLoading) return <Loading label="Loading timeline" />;
  if (!tl.data || !overlay.data || !game.data) return <ErrorBox error={tl.error ?? overlay.error ?? game.error} />;
  const d = tl.data;
  const dur = d.durationSec;

  return (
    <>
      <div className="row">
        <section className="card card--tight" style={{ flex: '999 1 560px', minWidth: 0 }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <strong>Game video with names</strong>
            <div className="legend">
              <span><span className="swatch swatch--named" />Named from numbers</span>
              <span><span className="swatch swatch--confirmed" />Confirmed by you</span>
              <span><span className="swatch swatch--stripe" />Needs you</span>
            </div>
          </div>
          {game.data.footage.video ? (
            <VideoWithBoxes src={`/files/${gid}/media/proxy.mp4`} overlay={overlay.data} videoRef={videoRef} onTime={onTime} />
          ) : (
            <div className="callout">The video was deleted from this Mac. Names and minutes are still available.</div>
          )}
          <p className="muted small" style={{ marginTop: 8 }}>
            Click a lane to jump there. Orange dashed boxes still need a name; <Link to={`/g/${gid}/review`}>review them</Link>.
          </p>
        </section>
        <aside className="card" style={{ flex: '1 1 280px', maxWidth: 360 }}>
          <h2 className="title title--sm">How much can you trust this game</h2>
          <div style={{ margin: '10px 0' }}>
            <span className="num" style={{ fontSize: 44 }}>{(d.coverage.namedPct + d.coverage.confirmedPct).toFixed(0)}%</span>{' '}
            <span className="muted">of player footage has a name</span>
          </div>
          <CoverageBar cov={d.coverage} />
          <Link className="btn btn--primary" style={{ marginTop: 14, width: '100%' }} to={`/g/${gid}/review`}>
            Review the {d.coverage.queueCount} open pieces
          </Link>
        </aside>
      </div>

      <section className="card" aria-label="Who was on court">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
          <strong>Who was on court, second by second</strong>
          <span className="muted small">0:00 to {mmss(dur)} · playhead {mmss(time)}</span>
        </div>
        <div className="lanes">
          <div className="lanes__grid">
            {d.lanes.map((l) => (
              <div className="lane" key={l.key}>
                <div className="lane__name">
                  <span className={`dot dot--${l.team}`} aria-hidden="true" />
                  <Link to={playerPath(gid, l.key)} style={{ color: 'inherit' }}>#{l.number}</Link>
                </div>
                <LaneTrack segs={l.segments} kind="named" duration={dur} onSeek={seek} />
              </div>
            ))}
            <div className="lane">
              <div className="lane__name"><span className="dot" style={{ background: 'var(--amber)' }} aria-hidden="true" />Unnamed</div>
              <LaneTrack segs={d.open} kind="open" duration={dur} onSeek={seek} />
            </div>
            <div className="lane">
              <div className="lane__name"><span className="dot" style={{ background: 'var(--line-strong)' }} aria-hidden="true" />Not players</div>
              <LaneTrack segs={d.nonplayer} kind="nonplayer" duration={dur} onSeek={seek} />
            </div>
            <div className="playhead" style={{ left: `calc(96px + (100% - 96px) * ${time / dur})` }} aria-hidden="true" />
          </div>
        </div>
      </section>
    </>
  );
}
