import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { api, useGames, useProbe, useSystem } from '../api';
import type { Job, Roster, RosterData } from '../api';
import { ErrorBox, Loading } from '../components/Bits';
import { CourtPicker, DEFAULT_COURT } from '../components/CourtPicker';
import type { Point } from '../components/CourtPicker';
import { FilePicker } from '../components/FilePicker';
import { RosterEditor } from '../components/RosterEditor';
import { TopBar } from '../components/TopBar';
import { bytes, mmss } from '../format';

function parseClock(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const parts = t.split(':').map(Number);
  if (parts.some((p) => Number.isNaN(p) || p < 0)) return null;
  return parts.reduce((acc, p) => acc * 60 + p, 0);
}

function span(min: number): string {
  if (min < 60) return `${Math.max(1, Math.round(min))} min`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function NewGamePage() {
  const nav = useNavigate();
  const system = useSystem();
  const games = useGames();
  const [roster, setRoster] = useState<Roster>({ light: [], dark: [] });
  const [video, setVideo] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const probe = useProbe(video);
  const [mode, setMode] = useState<'sample' | 'whole'>('sample');
  const [startText, setStartText] = useState('0:00');
  const [lenText, setLenText] = useState('3:00');
  const [court, setCourt] = useState<Point[]>(DEFAULT_COURT);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [teams, setTeams] = useState({ light: 'Team A', dark: 'Team B' });
  const [error, setError] = useState<string | null>(null);

  // start from the most recent game's roster: rosters rarely change between games
  const first = games.data?.[0]?.id;
  useEffect(() => {
    if (first && roster.light.length === 0 && roster.dark.length === 0) {
      api.get<RosterData>(`/api/games/${first}/roster`).then((r) => setRoster(r.roster)).catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [first]);

  const startSec = parseClock(startText);
  const lenSec = parseClock(lenText);
  const info = probe.data;
  const footage = mode === 'whole' ? info?.durationSec ?? 0 : lenSec ?? 0;
  const sectionOk = mode === 'whole' || (startSec !== null && lenSec !== null && lenSec >= 20 && !!info && startSec + lenSec <= info.durationSec + 0.5);
  const need = (footage / 60) * (system.data?.gbPerFootageMin ?? 0.2);
  const diskOk = !system.data || system.data.diskFreeGB >= need + 2;
  const [lo, hi] = system.data?.minPerFootageMin ?? [8, 15];

  const problems = useMemo(() => {
    const p: string[] = [];
    if (!roster.light.length || !roster.dark.length) p.push('List the jersey numbers for both teams.');
    if (!video || !info) p.push('Choose a video file.');
    if (info && !sectionOk) p.push('Check the section: it must fit inside the video and be at least 20 seconds.');
    if (court.length < 4) p.push('Mark at least four points around the playing area.');
    if (!title.trim()) p.push('Give the game a name.');
    if (system.data && !system.data.ok) p.push('Something this app needs is missing (see the checks below).');
    if (!diskOk) p.push('Not enough free disk space for this much footage.');
    return p;
  }, [roster, video, info, sectionOk, court, title, system.data, diskOk]);

  const create = useMutation({
    mutationFn: () =>
      api.post<Job>('/api/jobs', {
        video, title: title.trim(), date, teams, roster, polygon: court,
        startSec: mode === 'sample' ? startSec : null, durSec: mode === 'sample' ? lenSec : null,
      }),
    onSuccess: (j) => nav(`/jobs/${j.id}`),
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="shell">
      <TopBar subtitle="Add a game" />
      <main className="page" style={{ maxWidth: 1000, width: '100%', margin: '0 auto' }}>
        <h1 className="title">Add a game</h1>

        <section className="card stack" aria-labelledby="s1">
          <div className="step">Step 1</div>
          <h2 id="s1" className="title title--sm">Who plays in this game?</h2>
          <p className="muted">
            List every jersey number for both teams. The reader may only choose from these numbers, so a missing player is held back
            for you in Review, never guessed at.
          </p>
          <RosterEditor roster={roster} onChange={setRoster} />
        </section>

        <section className="card stack" aria-labelledby="s2">
          <div className="step">Step 2</div>
          <h2 id="s2" className="title title--sm">Which video?</h2>
          <p className="muted">Use the original file from the camera. A copy from a video site was re-encoded and reads worse.</p>
          {video && (
            <div className="callout" style={{ background: 'var(--wash)', borderColor: 'var(--line)', color: 'var(--ink)' }}>
              <strong>{video.split('/').pop()}</strong>
              {probe.isLoading && <span className="muted"> · reading…</span>}
              {probe.error && <div role="alert" style={{ color: 'var(--danger)' }}>{(probe.error as Error).message}</div>}
              {info && (
                <div className="muted">
                  {info.width} x {info.height} · {info.fps} fps · {mmss(info.durationSec)} · {bytes(info.sizeBytes)}
                </div>
              )}
              {info && info.height < 1440 && (
                <div style={{ color: 'var(--amber-ink)', marginTop: 4 }}>
                  Below 4K, jersey numbers are small and may read poorly. 4K gave the best results.
                </div>
              )}
              {info && Math.abs(info.fps - 30) >= 0.5 && (
                <div style={{ color: 'var(--amber-ink)', marginTop: 4 }}>
                  This is {info.fps} fps. It will be converted to 30 fps first, which adds some minutes.
                </div>
              )}
            </div>
          )}
          <div><button className="btn" onClick={() => setPicking((p) => !p)}>{video ? 'Choose a different file' : 'Choose a video file'}</button></div>
          {picking && <FilePicker onPick={(p) => { setVideo(p); setPicking(false); setTitle((t) => t || p.split('/').pop()!.replace(/\.[^.]+$/, '')); }} onClose={() => setPicking(false)} />}

          {info && (
            <div role="radiogroup" aria-label="How much to process" className="stack" style={{ gap: 10 }}>
              <label className="option" data-checked={mode === 'sample'}>
                <input type="radio" name="mode" checked={mode === 'sample'} onChange={() => setMode('sample')} />
                <span>
                  <strong>Try a short section first</strong> <span className="pill pill--blue">recommended</span>
                  <span className="muted small" style={{ display: 'block' }}>Gets you reviewing quickly and shows whether the footage reads well.</span>
                  {mode === 'sample' && (
                    <span className="row" style={{ gap: 12, marginTop: 8 }}>
                      <label className="field">Start at<input className="input" style={{ width: 110 }} value={startText} onChange={(e) => setStartText(e.target.value)} placeholder="0:00" /></label>
                      <label className="field">Length<input className="input" style={{ width: 110 }} value={lenText} onChange={(e) => setLenText(e.target.value)} placeholder="3:00" /></label>
                    </span>
                  )}
                </span>
              </label>
              <label className="option" data-checked={mode === 'whole'}>
                <input type="radio" name="mode" checked={mode === 'whole'} onChange={() => setMode('whole')} />
                <span>
                  <strong>The whole video</strong> <span className="muted">({mmss(info.durationSec)})</span>
                  <span className="muted small" style={{ display: 'block' }}>A full game takes many hours on a laptop. Leave it running overnight.</span>
                </span>
              </label>
            </div>
          )}
        </section>

        {info && video && (
          <section className="card stack" aria-labelledby="s3">
            <div className="step">Step 3</div>
            <h2 id="s3" className="title title--sm">Mark the playing area</h2>
            <p className="muted">
              Click around the court in order. People whose feet are inside count as players; referees, benches and spectators outside
              are ignored. The first two games used the court below.
            </p>
            <CourtPicker video={video} t={(mode === 'sample' ? startSec ?? 0 : info.durationSec / 3) + 5} value={court} onChange={setCourt} />
          </section>
        )}

        <section className="card stack" aria-labelledby="s4">
          <div className="step">Step 4</div>
          <h2 id="s4" className="title title--sm">About the game</h2>
          <div className="row">
            <label className="field" style={{ flex: '2 1 280px' }}>Name<input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="[Team A vs Team B]" /></label>
            <label className="field" style={{ flex: '1 1 160px' }}>Date<input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          </div>
          <div className="row">
            <label className="field" style={{ flex: '1 1 220px' }}>Light jerseys<input className="input" value={teams.light} onChange={(e) => setTeams({ ...teams, light: e.target.value })} /></label>
            <label className="field" style={{ flex: '1 1 220px' }}>Dark jerseys<input className="input" value={teams.dark} onChange={(e) => setTeams({ ...teams, dark: e.target.value })} /></label>
          </div>
        </section>

        <section className="card stack" aria-labelledby="s5">
          <h2 id="s5" className="title title--sm">Ready?</h2>
          {system.isLoading && <Loading label="Checking this computer" />}
          {system.error && <ErrorBox error={system.error} />}
          {system.data && (
            <div className="stack" style={{ gap: 6 }}>
              {system.data.checks.map((c) => (
                <div key={c.key} className={`check ${c.ok ? '' : 'check--bad'}`}>
                  <span aria-hidden="true">{c.ok ? '✓' : '✕'}</span>
                  <span>{c.label}{!c.ok && <span className="small"> · {c.fix}</span>}</span>
                </div>
              ))}
            </div>
          )}
          {footage > 0 && system.data && (
            <div className="muted">
              For {mmss(footage)} of footage expect about <strong style={{ color: 'var(--ink)' }}>{span((footage / 60) * lo)} to {span((footage / 60) * hi)}</strong> of
              processing on this computer, and about <strong style={{ color: 'var(--ink)' }}>{need.toFixed(1)} GB</strong> of disk while it works
              ({system.data.diskFreeGB} GB free).
            </div>
          )}
          {problems.length > 0 && (
            <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--amber-ink)' }}>
              {problems.map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}
          {error && <div className="callout" role="alert">{error}</div>}
          <div className="row" style={{ alignItems: 'center' }}>
            <button className="btn btn--primary" disabled={problems.length > 0 || create.isPending} onClick={() => { setError(null); create.mutate(); }}>
              {create.isPending ? 'Starting…' : 'Start processing'}
            </button>
            <Link className="btn btn--quiet" to="/">Cancel</Link>
          </div>
        </section>
      </main>
    </div>
  );
}
