import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { EventType, PlayerData } from '../api';
import { mmss, range } from '../format';

export const EVENT_LABEL: Record<EventType, string> = {
  made2: '2 pts', made3: '3 pts', made1: 'Free throw', missed: 'Missed shot',
  assist: 'Assist', rebound: 'Rebound', steal: 'Steal', turnover: 'Turnover', foul: 'Foul',
};
const ORDER: EventType[] = ['made2', 'made3', 'made1', 'missed', 'assist', 'rebound', 'steal', 'turnover', 'foul'];

/** Tag what happened while watching this player. Nothing here is guessed by the computer. */
export function Moments({ gid, data, hasVideo }: { gid: string; data: PlayerData; hasVideo: boolean }) {
  const qc = useQueryClient();
  const video = useRef<HTMLVideoElement>(null);
  const [seg, setSeg] = useState(0);
  const [note, setNote] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['game', gid, 'player', data.key] });

  useEffect(() => {
    const v = video.current;
    const s = data.presence[seg];
    if (v && s) v.currentTime = s.start;
  }, [seg, data.presence]);

  const add = useMutation({
    mutationFn: (type: EventType) => api.post(`/api/games/${gid}/events`, { key: data.key, type, sec: video.current?.currentTime ?? 0 }),
    onSuccess: (_r, type) => {
      setNote(`${EVENT_LABEL[type]} recorded at ${mmss(video.current?.currentTime ?? 0)}`);
      void refresh();
    },
  });
  const del = useMutation({
    mutationFn: (id: string) => fetch(`/api/games/${gid}/events/${id}`, { method: 'DELETE' }),
    onSuccess: () => void refresh(),
  });

  return (
    <section className="card stack" aria-label="Moments to tag">
      <div>
        <h2 className="title title--sm">Moments</h2>
        <p className="muted small">
          Watch this player and tap what happened. The computer cannot see the ball, so it does not guess shots or assists.
        </p>
      </div>

      {hasVideo ? (
        <>
          <label className="field">
            Jump to a stretch
            <select className="input" style={{ fontSize: 15 }} value={seg} onChange={(e) => setSeg(Number(e.target.value))}>
              {data.presence.map((s, i) => (
                <option key={i} value={i}>{range(s.start, s.end)}</option>
              ))}
            </select>
          </label>
          <video ref={video} src={`/files/${gid}/media/proxy.mp4`} controls muted playsInline preload="auto"
                 style={{ width: '100%', borderRadius: 8, background: '#1b2230' }} />
          <div className="row" style={{ gap: 6 }} role="group" aria-label="Tag the current moment">
            {ORDER.map((t) => (
              <button key={t} className={`btn ${t.startsWith('made') ? 'btn--primary' : 'btn--quiet'}`} disabled={add.isPending}
                      onClick={() => add.mutate(t)}>
                {EVENT_LABEL[t]}
              </button>
            ))}
          </div>
          <div role="status" className="muted small" style={{ minHeight: 20 }}>{note ?? 'Pause on the moment, then tap what it was.'}</div>
        </>
      ) : (
        <div className="callout">The video was deleted from this Mac, so moments cannot be tagged any more.</div>
      )}

      <div className="stack" style={{ gap: 8 }}>
        {data.events.length === 0 && <p className="muted small">Nothing tagged for this player yet.</p>}
        {data.events.map((e) => (
          <div key={e.id} className="unit">
            <span><strong>{mmss(e.sec)}</strong> · {EVENT_LABEL[e.type]}</span>
            <button className="btn btn--quiet" onClick={() => del.mutate(e.id)} aria-label={`Remove ${EVENT_LABEL[e.type]} at ${mmss(e.sec)}`}>
              Remove
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
