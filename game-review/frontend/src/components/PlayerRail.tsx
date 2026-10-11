import { Link } from 'react-router-dom';
import { useTeam } from '../api';
import type { Team } from '../api';
import { playerPath } from '../format';

/** Everyone with named footage, so you can move between players without going back. */
export function PlayerRail({ gid, current }: { gid: string; current: string }) {
  const team = useTeam(gid);
  const groups: { team: Team; title: string }[] = [
    { team: 'light', title: 'Team A · light' },
    { team: 'dark', title: 'Team B · dark' },
  ];
  return (
    <nav className="card stack" aria-label="Players" style={{ flex: '1 1 200px', maxWidth: 240, gap: 14 }}>
      {groups.map((g) => (
        <div key={g.team}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>{g.title}</div>
          <div className="chips" style={{ gap: 6 }}>
            {(team.data?.players[g.team] ?? []).map((p) => (
              <Link
                key={p.key}
                to={playerPath(gid, p.key)}
                className={`railnum num ${p.key === current ? 'railnum--on' : ''}`}
                aria-current={p.key === current ? 'page' : undefined}
                aria-label={`Number ${p.number}, ${g.team} team`}
              >
                {p.number}
              </Link>
            ))}
          </div>
        </div>
      ))}
      <div className="muted small">Only players with footage in this game are listed.</div>
    </nav>
  );
}
