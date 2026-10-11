import { Link, NavLink, Outlet, useParams } from 'react-router-dom';
import { useGame, useQueue } from '../api';
import { ErrorBox, Loading } from './Bits';

export function Shell() {
  const { gid = '' } = useParams();
  const game = useGame(gid);
  const queue = useQueue(gid);
  const open = queue.data?.coverage.queueCount ?? 0;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand__name">
            GAME REVIEW
          </Link>
          {game.data && (
            <span className="brand__game">
              {game.data.title} · {game.data.date} · sample window {game.data.windowLabel}
            </span>
          )}
        </div>
        <nav className="nav" aria-label="Game">
          <NavLink to={`/g/${gid}/team`}>Team</NavLink>
          <NavLink to={`/g/${gid}/review`}>
            Review
            {open > 0 && <span className="badge">{open}</span>}
          </NavLink>
          <NavLink to={`/g/${gid}/timeline`}>Timeline</NavLink>
          <NavLink to={`/g/${gid}/roster`}>Roster</NavLink>
          <NavLink to={`/g/${gid}/storage`}>Storage</NavLink>
        </nav>
      </header>
      <main className="page">
        {game.isLoading && <Loading label="Loading game" />}
        {game.error && <ErrorBox error={game.error} />}
        {game.data && <Outlet />}
      </main>
    </div>
  );
}
