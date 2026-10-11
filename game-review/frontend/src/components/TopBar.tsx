import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export function TopBar({ subtitle, children }: { subtitle?: string; children?: ReactNode }) {
  return (
    <header className="topbar">
      <div className="brand">
        <Link to="/" className="brand__name">GAME REVIEW</Link>
        {subtitle && <span className="brand__game">{subtitle}</span>}
      </div>
      {children}
    </header>
  );
}
