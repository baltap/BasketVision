# BasketVision

Local-first tool for reviewing youth basketball footage. A computer proposes which player is which from jersey numbers, a person confirms, and the coach sees minutes, lineups and per-player pages. Everything runs on one machine; nothing is uploaded.

The footage shows children, so this repository contains **code and small text results only**. Video, crops, per-game data and model weights are never committed (see `.gitignore`).

## Layout

| Path | What |
|---|---|
| `game-review/` | The app: FastAPI backend, React/Vite/TypeScript frontend, resumable processing pipeline. `./start.sh`, then http://localhost:8000 |
| `basketball-poc/` | The feasibility probe: scripts for detection, tracking, number reading and identity assignment (rounds 1 to 7), final configuration and verified results |
| `CLAUDE.md` | Working rules and memory protocol for Claude Code sessions |

## Status

Detection and number reading work. Tracking identity does not hold on its own, so naming is anchored on jersey numbers with a closed roster. The final configuration names about 74 to 75 percent of player detections on two 3 minute test clips; the rest goes to a review queue. A full game is not yet practical on a laptop. No ball tracking, court map, distance or shot detection yet.

## Not in this repo

- `game-review/data/`: per-game packs, crops, review answers
- `basketball-poc/_work/`: venv, model cache, clips
- `game-review/pipeline/models/yolo11l.pt`: download the Ultralytics YOLO11l weights and place them there
- The Obsidian vault with project notes and the `claude-obsidian` checkout

## Run

```bash
cd game-review
./start.sh
```

Needs Python 3.11 with the packages in `game-review/backend/requirements.txt`, Node 22 with pnpm, and ffmpeg. `start.sh` expects the pipeline venv at `basketball-poc/_work/venv` unless `GAME_REVIEW_PYTHON` is set.

Paths in `start.sh`, `backend/jobs.py`, `configs/*.json` and the `launch.json` files are specific to the author's Mac and need adjusting elsewhere.
