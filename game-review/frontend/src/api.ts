import { useQuery } from '@tanstack/react-query';


export type Team = 'light' | 'dark';
export type PieceTeam = Team | 'unk' | 'none';

export interface Coverage {
  playerSeconds: number;
  namedPct: number;
  confirmedPct: number;
  openPct: number;
  queueCount: number;
  skippedCount: number;
  queueSeconds: number;
}

export interface Game {
  id: string;
  title: string;
  date: string;
  windowLabel: string;
  offsetSec: number;
  teams: Record<Team, string>;
  durationSec: number;
  width: number;
  height: number;
  step: number;
  fps: number;
  coverage: Coverage;
  footage: { video: boolean; pictures: boolean };
}

export interface Crop {
  file: string;
  sec: number;
  read: string;
  kind: 'read' | 'neighbor' | 'none';
  url: string;
}

export interface Suggestion {
  number: string | null;
  count: number;
  alt: string | null;
  altCount: number;
  reads: number;
  unlisted: Record<string, number>;
}

export interface Piece {
  id: string;
  tid: number;
  startSec: number;
  endSec: number;
  durSec: number;
  n: number;
  team: PieceTeam;
  state: 'named' | 'confirmed' | 'nonplayer' | 'open';
  key: string | null;
  skipped: boolean;
  note: string;
  status: string;
  answered: { kind: string; number: string | null; team: string | null } | null;
  suggestion: Suggestion;
  crops: Crop[];
  thumb: { url: string; sec: number; box: [number, number, number, number] };
  crowdedReads: number;
  reads: number;
}

export type Roster = Record<Team, string[]>;
export interface QueueData {
  items: Piece[];
  done: Piece[];
  coverage: Coverage;
  roster: Roster;
  history: number;
}

export interface PlayerRow {
  key: string;
  number: string;
  seconds: number;
  shifts: number;
  tiny: boolean;
}
export interface TeamData {
  players: Record<Team, PlayerRow[]>;
  lineups: Record<Team, { units: string; seconds: number }[]>;
  overfull: { team: Team; startSec: number; endSec: number; seconds: number; keys: string[] }[];
  notSeen: Record<Team, string[]>;
  tiny: { key: string; seconds: number }[];
  coverage: Coverage;
  roster: Roster;
  windowSec: number;
}

export interface Segment {
  start: number;
  end: number;
  state?: 'named' | 'confirmed';
}
export interface Lane {
  key: string;
  team: Team;
  number: string;
  seconds: number;
  segments: Segment[];
}
export interface TimelineData {
  lanes: Lane[];
  open: Segment[];
  nonplayer: Segment[];
  durationSec: number;
  coverage: Coverage;
}

export interface OverlayData {
  step: number;
  fps: number;
  labels: { state: Piece['state']; key: string | null }[];
  items: [number, number, number, number, number, number][];
}

export type EventType = 'made2' | 'made3' | 'made1' | 'missed' | 'assist' | 'rebound' | 'steal' | 'turnover' | 'foul';
export interface GameEvent {
  id: string;
  key: string;
  type: EventType;
  sec: number;
}
export interface EventStats {
  points: number;
  made: number;
  missed: number;
  assists: number;
  rebounds: number;
  steals: number;
  turnovers: number;
  fouls: number;
  total: number;
}

export interface PlayerData {
  maybe: Segment[];
  events: GameEvent[];
  stats: EventStats;
  key: string;
  seconds: number;
  shifts: number;
  presence: Segment[];
  heat: number[][];
  pieces: Piece[];
  confirmedSeconds: number;
  namedSeconds: number;
  windowSec: number;
  coverage: Coverage;
}

export interface RosterData {
  roster: Roster;
  unlisted: { team: string; number: string; reads: number; pieces: number; elsewhere: boolean }[];
  teams: Record<Team, string>;
}

export interface StorageData {
  folder: string;
  date: string;
  footage: { video: boolean; pictures: boolean };
  usage: { name: string; detail: string; bytes: number }[];
}

export class ApiError extends Error {}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* keep the status text */
    }
    throw new ApiError(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => call<T>('GET', path),
  post: <T>(path: string, body?: unknown) => call<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => call<T>('PUT', path, body),
};

const q = <T,>(key: unknown[], path: string, enabled = true) =>
  useQuery({ queryKey: key, queryFn: () => api.get<T>(path), enabled });

export const useGames = () => q<Game[]>(['games'], '/api/games');
export const useGame = (id: string) => q<Game>(['game', id], `/api/games/${id}`);
export const useQueue = (id: string) => q<QueueData>(['game', id, 'queue'], `/api/games/${id}/queue`);
export const useTeam = (id: string) => q<TeamData>(['game', id, 'team'], `/api/games/${id}/team`);
export const useTimeline = (id: string) => q<TimelineData>(['game', id, 'timeline'], `/api/games/${id}/timeline`);
export const useOverlay = (id: string) => q<OverlayData>(['game', id, 'overlay'], `/api/games/${id}/overlay`);
export const usePlayer = (id: string, key: string) =>
  q<PlayerData>(['game', id, 'player', key], `/api/games/${id}/players/${encodeURIComponent(key)}`);
export const useRoster = (id: string) => q<RosterData>(['game', id, 'roster'], `/api/games/${id}/roster`);
export const useStorage = (id: string) => q<StorageData>(['game', id, 'storage'], `/api/games/${id}/storage`);

// ---- add a game ----
export interface SystemCheck {
  ok: boolean;
  checks: { key: string; label: string; ok: boolean; fix: string }[];
  diskFreeGB: number;
  hfHome: string;
  minPerFootageMin: [number, number];
  gbPerFootageMin: number;
}
export interface FsListing {
  path: string;
  parent: string | null;
  entries: { name: string; kind: 'dir' | 'video'; size?: number }[];
}
export interface VideoInfo {
  width: number;
  height: number;
  fps: number;
  codec: string;
  durationSec: number;
  sizeBytes: number;
}
export interface JobStage {
  key: string;
  label: string;
  pct: number;
  state: 'waiting' | 'running' | 'done';
}
export type JobState = 'starting' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrupted';
export interface Job {
  id: string;
  title: string;
  date: string;
  state: JobState;
  stages: JobStage[];
  overall: number;
  error: string | null;
  startedAt: number;
  updatedAt: number;
  createdAt: number;
  footageSec: number;
  gameId?: string;
  log?: string;
}

export const isActive = (s: JobState) => s === 'starting' || s === 'running';

export const useSystem = () => q<SystemCheck>(['system'], '/api/system');
export const useFs = (path: string) => q<FsListing>(['fs', path], `/api/fs?path=${encodeURIComponent(path)}`);
export const useProbe = (path: string | null) =>
  useQuery({
    queryKey: ['probe', path],
    queryFn: () => api.get<VideoInfo>(`/api/probe?path=${encodeURIComponent(path ?? '')}`),
    enabled: !!path,
    retry: false,
  });
export const useJobs = () =>
  useQuery({
    queryKey: ['jobs'],
    queryFn: () => api.get<Job[]>('/api/jobs'),
    refetchInterval: (query) => (query.state.data?.some((j) => isActive(j.state)) ? 3000 : false),
  });
export const useJob = (id: string) =>
  useQuery({
    queryKey: ['job', id],
    queryFn: () => api.get<Job>(`/api/jobs/${id}`),
    refetchInterval: (query) => (query.state.data && !isActive(query.state.data.state) ? false : 2000),
  });
export const frameUrl = (path: string, t: number) => `/api/frame?path=${encodeURIComponent(path)}&t=${t}`;
