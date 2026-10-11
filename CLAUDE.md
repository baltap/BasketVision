# BasketVision

Local-first tool for reviewing youth basketball footage: a computer proposes which player is which from jersey numbers, a person confirms. Owner: Peter Baltazár. Footage shows U11 children, so everything stays on this Mac.

## Layout

| Path | What |
|---|---|
| `BasketVision/` (vault) | Obsidian knowledge base and project memory, managed by claude-obsidian |
| `game-review/` | The app: FastAPI backend, React/Vite/TS frontend, pipeline. Run `./start.sh`, open http://localhost:8000 |
| `basketball-poc/` | Research pipeline, experiment results, venv and model cache in `_work/` (do not delete) |
| `claude-obsidian/` | Product checkout of claude-obsidian, not a vault. Do not edit |

Symlinks at `/Users/peter/Data/Claude/game-review` and `/Users/peter/Data/Claude/basketball-poc` point here; prefer the real paths.

## Memory protocol

The vault at `BasketVision/BasketVision` is the project memory. `CLAUDE_OBSIDIAN_VAULT` is set in `.claude/settings.json`.

1. **At the start of work**, read `BasketVision/wiki/hot.md` and `BasketVision/wiki/index.md`. Then read only the pages relevant to the task (start with `wiki/entities/BasketVision project.md`).
2. **Before answering "what did we decide / measure / try"**, look it up in the vault (`/claude-obsidian:wiki-query`) instead of guessing. Numbers there cite sources in `wiki/meta/ledgers/`.
3. **After finishing meaningful work**, persist durable findings: `/claude-obsidian:save` for a single insight or decision, `/claude-obsidian:wiki-ingest` for new source files placed in `BasketVision/inbox/`. Add dated rows to `wiki/concepts/Decision log.md` for decisions and update `wiki/hot.md` with active threads.
4. **Never write vault pages with plain file edits.** The product applies changes as recoverable transactions; use its skills or `scripts/claude-obsidian.py` in the product checkout. Run `/claude-obsidian:wiki-lint` after larger changes.
5. Record corrections: if a vault page turns out wrong, supersede the claim rather than silently overwrite.

## Development methodology (superpowers)

The `superpowers` plugin (project scope) is the process layer; `agent-skills` is disabled for this project. Flow: brainstorming, written spec, git worktree, writing-plans, subagent-driven-development or executing-plans with test-driven-development, requesting-code-review, verification-before-completion, finishing-a-development-branch. Bugs go through systematic-debugging. Everything in this section overrides the skills' defaults.

1. **Specs and plans are local only.** Save to `/Users/peter/Data/Claude/BasketVision/docs/superpowers/specs/` and `.../plans/` (the folder is gitignored, never `git add` it). From a worktree, refer to them by absolute path.
2. **Persist decisions.** When a spec or plan is approved, add a dated row to `wiki/concepts/Decision log.md` in the vault with the file path, and keep `wiki/hot.md` active threads current.
3. **Tests use synthetic fixtures only.** Never real footage, crops or `game-review/data/games/*`. Point `GAME_REVIEW_DATA` at a temp dir. Any test or script that could reach real data must checksum `corrections.json` and `events.json` before and after. Backend and pipeline logic: pytest. Frontend gate until a unit runner exists: `pnpm build` (tsc and vite). If no baseline exists yet, say so; do not skip the baseline step silently.
4. **Worktrees** go in `.worktrees/` at the repo root (already ignored). A worktree has no `data/`, no models and no venv: use fixtures, or set `GAME_REVIEW_DATA` and `GAME_REVIEW_PYTHON` to the main checkout's.
5. **Verify UI changes in the real app**: confirm port 8000 is free, run `./start.sh`, check in the browser. Dev servers alone are not proof.
6. **Research rounds are spikes.** Pipeline experiments may be throwaway, but they must be judged against the verified sets (`truth_by_eye.json`, the clip 2 sample) and recorded in `wiki/comparisons/Identity rounds 1 to 7.md`. Code that moves into the app goes through TDD.
7. **Execution mode** (subagent-driven or inline) is Peter's choice per plan; ask.
8. **diagnosing-superpowers** may read session transcripts and package bundles. Never export or attach a transcript from this project, or file an issue with one, without Peter reviewing it first: transcripts reference footage of children.

## Hard rules

- Never modify `game-review/data/games/*/corrections.json` or `events.json`: they hold Peter's real review answers. Checksum them before and after any change near them.
- Git: repo root is this folder, remote `origin` is the **private** `baltap/BaksetVision`. `.gitignore` is a whitelist. Before every commit run `git diff --cached --name-only` and confirm no media, `data/`, `*.pt`, vault or `claude-obsidian` paths. Never `git add -f`. Do not make the repo public without re-checking history.
- Footage and crops of children stay local. No uploads, no third-party compute, no sharing, no images of children in notes or sketches. See `wiki/concepts/Privacy and footage handling.md`.
- Do not promise automatic per-player stats. The design is "CV proposes, human confirms".
- Do not delete `basketball-poc/_work` or touch `~/.cache/huggingface`.
- Test the exact command you hand to Peter (`./start.sh`), not only dev servers; check port 8000 first.
- In zsh do not name a variable `GID`. Run project Python with `-I`.
- No em or en dashes in anything written for Peter, in chat or files. Rewrite the sentence instead.
