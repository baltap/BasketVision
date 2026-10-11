import type { PieceTeam, Team } from './api';

export function mmss(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export function range(start: number, end: number): string {
  return `${mmss(start)} to ${mmss(end)}`;
}

export function teamName(team: PieceTeam): string {
  return team === 'light' ? 'Light' : team === 'dark' ? 'Dark' : 'Unknown team';
}

export function keyLabel(key: string | null): string {
  if (!key) return '?';
  const [team, num] = key.split('#');
  return `${team === 'light' ? 'L' : 'D'}${num}`;
}

export function keyParts(key: string): { team: Team; number: string } {
  const [team, number] = key.split('#');
  return { team: team as Team, number };
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB'];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`;
}

export const playerPath = (gid: string, key: string) => `/g/${gid}/players/${key.replace('#', '-')}`;
export const playerKey = (slug: string) => slug.replace('-', '#');
