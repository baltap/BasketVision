import { useEffect, useRef } from 'react';

/** Plays one stretch of the proxy video and loops inside it. */
export function ClipPlayer({ src, start, end, autoPlay = true }: { src: string; start: number; end: number; autoPlay?: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const seek = () => {
      v.currentTime = start;
      if (autoPlay) void v.play().catch(() => undefined);
    };
    if (v.readyState >= 1) seek();
    else v.addEventListener('loadedmetadata', seek, { once: true });
    return () => v.removeEventListener('loadedmetadata', seek);
  }, [src, start, autoPlay]);

  return (
    <video
      ref={ref}
      src={src}
      controls
      muted
      playsInline
      preload="metadata"
      style={{ width: '100%', display: 'block', borderRadius: 8, background: '#1b2230' }}
      onTimeUpdate={(e) => {
        const v = e.currentTarget;
        if (v.currentTime >= end) {
          v.currentTime = start;
        }
      }}
    />
  );
}
