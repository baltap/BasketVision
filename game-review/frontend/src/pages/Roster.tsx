import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, useRoster } from '../api';
import type { Coverage, Roster, Team } from '../api';
import { ErrorBox, Loading } from '../components/Bits';
import { RosterEditor } from '../components/RosterEditor';

export function RosterPage() {
  const { gid = '' } = useParams();
  const qc = useQueryClient();
  const data = useRoster(gid);
  const [draft, setDraft] = useState<Roster | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    if (data.data && !draft) setDraft(data.data.roster);
  }, [data.data, draft]);

  const save = useMutation({
    mutationFn: async () => {
      await api.put(`/api/games/${gid}/roster`, draft);
      return api.post<{ coverage: Coverage }>(`/api/games/${gid}/recompute`);
    },
    onSuccess: (r) => {
      setResult(`Names recomputed. ${(r.coverage.namedPct + r.coverage.confirmedPct).toFixed(1)}% of player footage now has a name.`);
      void qc.invalidateQueries({ queryKey: ['game', gid] });
      void qc.invalidateQueries({ queryKey: ['games'] });
    },
    onError: (e: Error) => setResult(e.message),
  });

  if (data.isLoading || !draft) return <Loading label="Loading the roster" />;
  if (data.error || !data.data) return <ErrorBox error={data.error} />;

  const addNumber = (team: Team, n: string) =>
    setDraft({ ...draft, [team]: [...new Set([...draft[team], n])].sort((a, b) => Number(a) - Number(b)) });
  const changed = JSON.stringify(draft) !== JSON.stringify(data.data.roster);

  return (
    <>
      <section className="card stack" style={{ maxWidth: 760 }}>
        <h1 className="title">Who plays in this game?</h1>
        <p className="muted">
          List every jersey number for both teams. The reader may only choose from these numbers, so a player missing here is
          held back for you in Review, never guessed at. Numbers 7, 8 and 26 can appear on both teams: a player is always a team
          plus a number.
        </p>
      </section>

      <RosterEditor roster={draft} onChange={setDraft} />

      {data.data.unlisted.length > 0 && (
        <section className="card stack">
          <h2 className="title title--sm">Seen in the footage, not on a roster</h2>
          <p className="muted small">The reader saw these numbers on a player whose team does not list them. Many are misreads; add only the real ones.</p>
          <div className="stack" style={{ gap: 8 }}>
            {data.data.unlisted.map((u) => (
              <div key={`${u.team}-${u.number}`} className="unit">
                <span>
                  <span className="num" style={{ fontSize: 24 }}>#{u.number}</span>{' '}
                  <span className="muted small">
                    read {u.reads} times in {u.pieces} {u.pieces === 1 ? 'piece' : 'pieces'} on a {u.team === 'unk' || u.team === 'none' ? 'team-unknown' : u.team} player{u.elsewhere ? ' · listed for the other team, so probably a neighbour’s number' : ''}
                  </span>
                </span>
                <span className="row" style={{ gap: 6 }}>
                  {(['light', 'dark'] as Team[]).map((t) => (
                    <button key={t} className="btn btn--quiet" onClick={() => addNumber(t, u.number)} disabled={draft[t].includes(u.number)}>
                      Add to {t}
                    </button>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="card row" style={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ flex: '1 1 360px' }} role="status">
          {result ?? (changed ? 'You have unsaved changes to the roster.' : 'The roster is up to date.')}
          <div className="muted small">Saving recomputes names from the stored reads. It takes seconds and uses no model.</div>
        </div>
        <button className="btn btn--primary" disabled={!changed || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Recomputing…' : 'Save and recompute names'}
        </button>
      </section>
    </>
  );
}
