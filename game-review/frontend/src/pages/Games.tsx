import { Link } from 'react-router-dom';
import { isActive, useGames, useJobs } from '../api';
import { CoverageBar, ErrorBox, Loading } from '../components/Bits';
import { mmss } from '../format';

export function GamesPage() {
  const games = useGames();
  const jobs = useJobs();
  const working = (jobs.data ?? []).filter((j) => j.state !== 'done');
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand__name">GAME REVIEW</span>
          <span className="brand__game">Everything stays on this computer</span>
        </div>
      </header>
      <main className="page">
        <div className="row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
          <h1 className="title">Your games</h1>
          <Link className="btn btn--primary" to="/new">Add a game</Link>
        </div>
        {working.length > 0 && (
          <section className="stack" aria-label="In progress">
            <div className="eyebrow">In progress</div>
            <div className="row">
              {working.map((j) => (
                <article key={j.id} className="card stack" style={{ flex: '1 1 360px', maxWidth: 520 }}>
                  <div>
                    <h2 className="title title--sm">{j.title}</h2>
                    <div className="muted small">{j.date} · {mmss(j.footageSec)} of footage</div>
                  </div>
                  <div className="progress"><div style={{ width: `${j.overall * 100}%` }} /></div>
                  <div className="muted small">
                    {isActive(j.state) ? `Processing, ${Math.round(j.overall * 100)}%` : j.state === 'cancelled' ? 'Stopped' : 'Needs attention'}
                  </div>
                  <div><Link className="btn" to={`/jobs/${j.id}`}>Open</Link></div>
                </article>
              ))}
            </div>
          </section>
        )}
        {games.isLoading && <Loading label="Loading games" />}
        {games.error && <ErrorBox error={games.error} />}
        {games.data?.length === 0 && (
          <div className="card">
            <h2 className="title title--sm">No games yet</h2>
            <p className="muted">Add your first game: choose a video, list the jersey numbers, mark the court.</p>
            <div><Link className="btn btn--primary" to="/new">Add a game</Link></div>
          </div>
        )}
        <div className="row">
          {games.data?.map((g) => (
            <article key={g.id} className="card stack" style={{ flex: '1 1 360px', maxWidth: 520 }}>
              <div>
                <h2 className="title title--sm">{g.title}</h2>
                <div className="muted">
                  {g.date} · sample window {g.windowLabel}
                </div>
              </div>
              <CoverageBar cov={g.coverage} />
              <div className="muted small">
                {g.coverage.queueCount} pieces need you, about {Math.round(g.coverage.queueSeconds / 60)} min of footage
                {!g.footage.video && ' · video deleted'}
              </div>
              <div className="row">
                <Link className="btn btn--primary" to={`/g/${g.id}/team`}>
                  Open team overview
                </Link>
                <Link className="btn" to={`/g/${g.id}/review`}>
                  Review
                </Link>
              </div>
            </article>
          ))}
        </div>
      </main>
    </div>
  );
}
