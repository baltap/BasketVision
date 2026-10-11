import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, isActive, useJob } from '../api';
import type { Job } from '../api';
import { ErrorBox, Loading } from '../components/Bits';
import { TopBar } from '../components/TopBar';
import { mmss } from '../format';

function eta(job: Job): string | null {
  if (!isActive(job.state) || job.overall < 0.04) return null;
  const elapsed = Date.now() / 1000 - job.startedAt;
  const left = (elapsed * (1 - job.overall)) / job.overall / 60;
  if (left < 1) return 'less than a minute left';
  if (left < 90) return `about ${Math.round(left)} min left`;
  return `about ${(left / 60).toFixed(1)} h left`;
}

export function JobPage() {
  const { jid = '' } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const job = useJob(jid);
  const act = useMutation({
    mutationFn: (what: 'cancel' | 'resume') => api.post<Job>(`/api/jobs/${jid}/${what}`),
    onSuccess: (j) => qc.setQueryData(['job', jid], j),
  });
  const discard = useMutation({
    mutationFn: () => fetch(`/api/jobs/${jid}`, { method: 'DELETE' }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['jobs'] }); nav('/'); },
  });

  const j = job.data;
  const done = j?.state === 'done';
  const failed = j && ['failed', 'interrupted', 'cancelled'].includes(j.state);

  return (
    <div className="shell">
      <TopBar subtitle={j ? `${j.title} · ${j.date}` : 'Processing'} />
      <main className="page" style={{ maxWidth: 860, width: '100%', margin: '0 auto' }}>
        {job.isLoading && <Loading label="Loading job" />}
        {job.error && <ErrorBox error={job.error} />}
        {j && (
          <>
            <section className="card stack">
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
                <h1 className="title">
                  {done ? 'Ready to review' : j.state === 'cancelled' ? 'Stopped' : failed ? 'Needs attention' : 'Processing this game'}
                </h1>
                <span className="num" style={{ fontSize: 36 }} aria-label={`${Math.round(j.overall * 100)} percent`}>{Math.round(j.overall * 100)}%</span>
              </div>
              <div className="progress" role="progressbar" aria-valuenow={Math.round(j.overall * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div style={{ width: `${j.overall * 100}%` }} />
              </div>
              <div className="muted">
                {mmss(j.footageSec)} of footage{eta(j) ? ` · ${eta(j)}` : ''}
                {isActive(j.state) && ' · you can leave this page, it keeps going'}
              </div>

              {j.error && <div className="callout" role="alert"><strong>What happened.</strong> <span style={{ whiteSpace: 'pre-wrap' }}>{j.error}</span></div>}

              <div className="row">
                {done && (
                  <>
                    <Link className="btn btn--primary" to={`/g/${j.id}/team`}>Open the team overview</Link>
                    <Link className="btn" to={`/g/${j.id}/review`}>Review the open pieces</Link>
                  </>
                )}
                {isActive(j.state) && (
                  <button className="btn" onClick={() => act.mutate('cancel')} disabled={act.isPending}>Stop</button>
                )}
                {failed && (
                  <button className="btn btn--primary" onClick={() => act.mutate('resume')} disabled={act.isPending}>
                    Resume from where it stopped
                  </button>
                )}
                {!done && !isActive(j.state) && (
                  <button className="btn btn--quiet" onClick={() => discard.mutate()} disabled={discard.isPending}>Discard this job</button>
                )}
              </div>
            </section>

            <section className="card stack" aria-label="Stages">
              {j.stages.map((s, i) => (
                <div className="stage" key={s.key}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <strong>{i + 1}  {s.label}</strong>
                    <span className="small" style={{ fontWeight: 600, color: s.state === 'done' ? 'var(--blue)' : s.state === 'running' ? 'var(--ink)' : 'var(--ink-3)' }}>
                      {s.state === 'done' ? 'Done' : s.state === 'running' ? `${Math.round(s.pct * 100)}%` : 'Waiting'}
                    </span>
                  </div>
                  <div className={`progress ${s.state === 'done' ? 'progress--done' : ''}`}>
                    <div style={{ width: `${(s.state === 'done' ? 1 : s.pct) * 100}%` }} />
                  </div>
                </div>
              ))}
              {j.stages.length === 0 && <p className="muted">Starting…</p>}
            </section>

            <section className="card">
              <details>
                <summary>Technical log</summary>
                <pre className="log">{j.log || 'Nothing yet.'}</pre>
              </details>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
