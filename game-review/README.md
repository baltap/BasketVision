# Game Review

Local-first app for reviewing basketball footage: a computer proposes who is who from jersey numbers,
a person confirms. Everything stays on this computer. No accounts, no uploads, no sharing.

## Run it

```bash
./start.sh            # builds the UI once, then serves everything on http://localhost:8000
```

Development (hot reload): run the backend (`cd backend && python -I -m uvicorn app:app --port 8000`) and
`cd frontend && pnpm dev` (port 5173, proxies `/api` and `/files` to the backend).

The Python used by `start.sh` defaults to the pipeline venv at
`basketball-poc/_work/venv`; override with `GAME_REVIEW_PYTHON`. Needs `fastapi`, `uvicorn`, `numpy`,
`opencv-python-headless` (see `backend/requirements.txt`).

## What is in it

| Screen | What it does |
|---|---|
| Games | Lists games with how much footage has a name, and games being processed |
| Add a game | Roster, choose a video from this Mac, process a short section or the whole video, mark the court, name the game. Checks the machine and disk first |
| Processing | Seven stages with progress and time left. Stop and resume. Keeps going if you leave the page |
| Team (opens first) | Minutes per player, lineups with `?` for unnamed slots, checks: more than five named at once, tiny stretches, roster numbers not seen |
| Review | One piece at a time, longest first. Evidence pictures, suggested number from the reader, roster chips, type a number, not a player, skip, undo, clip playback. Keys: S skip, N not a player, U undo, arrows |
| Timeline | Video with named boxes drawn over it, per-player lanes, click to seek |
| Player | Player rail, minutes, stretches, presence strip (named / confirmed / might be this player), position heat in the camera view, evidence pictures, and **Moments**: watch the player's video and tap 2 pts, 3 pts, free throw, missed shot, assist, rebound, steal, turnover, foul. Points, assists and rebounds come from what you tag |
| Roster | Edit both teams' numbers, see numbers read but not listed, save and recompute names (no model, seconds) |
| Storage | Sizes, delete the video / video and pictures / everything, type the game date to confirm |

## How data flows

```
pipeline (models, hours)  ->  gamepack.py  ->  data/games/<id>/  ->  app
 tracks, reads, attrs         one-off per game    pieces, crops,
 identity7.py                                     proxy video, roster
```

* `backend/gamepack.py CONFIG.json` turns pipeline outputs into a pack (about 1 minute per 3-minute clip).
  Example configs are in `configs/`.
* Your answers live in `data/games/<id>/corrections.json` (append-only; undo pops the last one).
* Saving the roster re-runs `pipeline/identity7.py` over the stored reads and rebuilds the pack's pieces.

## Not built yet

* **Split a piece in two** (the reader sometimes tracks two players as one).
* **A real court map.** The court you mark decides who counts as a player, but distance, speed and a top-down map are
  not computed yet; positions are shown in the camera view.
* Shots, assists and rebounds are **not detected** (no ball tracking); they are tagged by hand on the Player page.
* **Full games are slow and disk-hungry on a laptop**: roughly 8 to 15 minutes of waiting and 0.2 GB per minute of footage
  while processing. Try a short section first. The 5.65 GB reader model and the detector must already be on this Mac
  (the Add a game screen checks).

## Verified

Adding a game: a real 30-second section was processed end to end from the API (all seven stages, 5 minutes),
stopped mid-stage and resumed (finished stages skipped), and opened as a normal game. 
Backend: unchanged recompute is byte-identical; removing a roster number lowers coverage and restoring it
returns the exact original; all three delete options work on a cloned game and the original file outside the
app is untouched. Frontend: typecheck clean, production build served by the backend, video range requests
work, no horizontal overflow at 375 px.
