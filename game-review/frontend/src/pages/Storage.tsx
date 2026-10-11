import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, useGame, useStorage } from '../api';
import { ErrorBox, Loading } from '../components/Bits';
import { bytes } from '../format';

type What = 'video' | 'video_and_pictures' | 'everything';

const OPTIONS: { what: What; title: string; detail: string; danger?: boolean }[] = [
  { what: 'video', title: 'Delete the video, keep the results', detail: 'Names, minutes, lineups and player pages stay. You can no longer play clips or recompute names.' },
  { what: 'video_and_pictures', title: 'Delete the video and all working pictures', detail: 'Also removes the cropped pictures shown as evidence. Results stay.' },
  { what: 'everything', title: 'Delete everything about this game', detail: 'Video, pictures and results. This cannot be undone.', danger: true },
];

export function StoragePage() {
  const { gid = '' } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const game = useGame(gid);
  const storage = useStorage(gid);
  const [what, setWhat] = useState<What>('video');
  const [confirm, setConfirm] = useState('');

  const del = useMutation({
    mutationFn: () => api.post(`/api/games/${gid}/storage/delete`, { what, confirm }),
    onSuccess: () => {
      void qc.invalidateQueries();
      setConfirm('');
      if (what === 'everything') nav('/');
    },
  });

  if (storage.isLoading || game.isLoading) return <Loading label="Loading storage" />;
  if (storage.error || !storage.data || !game.data) return <ErrorBox error={storage.error ?? game.error} />;
  const s = storage.data;
  const date = game.data.date;
  const open = game.data.coverage.queueCount;
  const selected = OPTIONS.find((o) => o.what === what)!;

  return (
    <div className="row">
      <div className="stack" style={{ flex: '999 1 520px', minWidth: 0, gap: 16 }}>
        <section className="card">
          <h1 className="title">Storage for this game</h1>
          <p className="muted" style={{ margin: '6px 0 14px' }}>Everything lives on this Mac. Nothing is uploaded or shared.</p>
          <table className="table">
            <tbody>
              {s.usage.map((u) => (
                <tr key={u.name}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{u.name}</div>
                    <div className="muted small">{u.detail}</div>
                  </td>
                  <td>{bytes(u.bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small" style={{ marginTop: 10 }}>Folder: {s.folder}</p>
        </section>

        <section className="card stack" style={{ gap: 14 }}>
          <div>
            <h2 className="title title--sm">Delete footage</h2>
            <p className="muted">Pick what to remove. You can keep the results and still get rid of the children's video.</p>
          </div>
          <div role="radiogroup" aria-label="What to delete" className="stack" style={{ gap: 10 }}>
            {OPTIONS.map((o) => (
              <label key={o.what} className="option" data-checked={what === o.what}>
                <input type="radio" name="what" checked={what === o.what} onChange={() => setWhat(o.what)} />
                <span>
                  <span style={{ display: 'block', fontWeight: 600, color: o.danger ? 'var(--danger)' : undefined }}>{o.title}</span>
                  <span className="muted small" style={{ display: 'block' }}>{o.detail}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="row" style={{ alignItems: 'center', gap: 12, paddingTop: 14, borderTop: '1px solid var(--line)' }}>
            <label htmlFor="confirm" className="muted small">Type the game date ({date}) to confirm</label>
            <input id="confirm" className="input" style={{ width: 170 }} value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={date} autoComplete="off" />
            <button className="btn btn--danger" disabled={confirm.trim() !== date || del.isPending} onClick={() => del.mutate()}>
              {del.isPending ? 'Deleting…' : `Delete: ${selected.title.split(',')[0].toLowerCase()}`}
            </button>
          </div>
          {del.error && <p role="alert" style={{ color: 'var(--danger)', fontWeight: 600 }}>{(del.error as Error).message}</p>}
          {del.isSuccess && what !== 'everything' && <p role="status" style={{ fontWeight: 600 }}>Deleted from this Mac.</p>}
        </section>
      </div>

      <aside className="stack" style={{ flex: '1 1 320px', maxWidth: 420, gap: 16 }}>
        {open > 0 && s.footage.video && (
          <div className="callout">
            <strong>{open} pieces are still open.</strong> Once the video is deleted they cannot be reviewed. Finish them first
            if you want firmer minutes.
            <div style={{ marginTop: 10 }}>
              <Link className="btn btn--amber" to={`/g/${gid}/review`}>Review open pieces first</Link>
            </div>
          </div>
        )}
        <div className="card small muted">
          <strong style={{ color: 'var(--ink)' }}>What deleting does</strong>
          <p style={{ marginTop: 6 }}>
            It removes the files this app holds for the game. Copies you made yourself, for example the original in
            Downloads, are not touched.
          </p>
        </div>
      </aside>
    </div>
  );
}
