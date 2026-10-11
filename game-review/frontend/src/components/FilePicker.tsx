import { useState } from 'react';
import { useFs } from '../api';
import { bytes } from '../format';
import { ErrorBox, Loading } from './Bits';

const SHORTCUTS = [
  { label: 'Home', path: '~' },
  { label: 'Movies', path: '~/Movies' },
  { label: 'Downloads', path: '~/Downloads' },
  { label: 'Desktop', path: '~/Desktop' },
];

/** Browse this computer's folders and pick one video. The app only ever reads the file you choose. */
export function FilePicker({ start = '~/Movies', onPick, onClose }: { start?: string; onPick: (path: string) => void; onClose: () => void }) {
  const [path, setPath] = useState(start);
  const fs = useFs(path);

  return (
    <div className="card stack" role="dialog" aria-label="Choose a video file">
      <div className="row" style={{ gap: 6 }}>
        {SHORTCUTS.map((s) => (
          <button key={s.path} className="btn btn--quiet" onClick={() => setPath(s.path)}>{s.label}</button>
        ))}
        <span className="spacer" />
        <button className="btn btn--quiet" onClick={onClose}>Close</button>
      </div>
      {fs.isLoading && <Loading label="Loading folder" />}
      {fs.error && <ErrorBox error={fs.error} />}
      {fs.data && (
        <>
          <div className="row" style={{ alignItems: 'center', gap: 10 }}>
            <button className="btn btn--quiet" disabled={!fs.data.parent} onClick={() => fs.data?.parent && setPath(fs.data.parent)}>
              Up one folder
            </button>
            <code className="small" style={{ wordBreak: 'break-all' }}>{fs.data.path}</code>
          </div>
          <ul className="files" aria-label="Folders and videos">
            {fs.data.entries.length === 0 && <li className="muted small">No folders or videos here.</li>}
            {fs.data.entries.map((e) => (
              <li key={e.name}>
                <button
                  className="files__item"
                  onClick={() => (e.kind === 'dir' ? setPath(`${fs.data!.path}/${e.name}`) : onPick(`${fs.data!.path}/${e.name}`))}
                >
                  <span aria-hidden="true">{e.kind === 'dir' ? '▸' : '●'}</span>
                  <span style={{ flex: 1, textAlign: 'left' }}>{e.name}</span>
                  <span className="muted small">{e.kind === 'dir' ? 'folder' : bytes(e.size ?? 0)}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
