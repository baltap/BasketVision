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

## Hard rules

- Never modify `game-review/data/games/*/corrections.json` or `events.json`: they hold Peter's real review answers. Checksum them before and after any change near them.
- Git: repo root is this folder, remote `origin` is the **private** `baltap/BaksetVision`. `.gitignore` is a whitelist. Before every commit run `git diff --cached --name-only` and confirm no media, `data/`, `*.pt`, vault or `claude-obsidian` paths. Never `git add -f`. Do not make the repo public without re-checking history.
- Footage and crops of children stay local. No uploads, no third-party compute, no sharing, no images of children in notes or sketches. See `wiki/concepts/Privacy and footage handling.md`.
- Do not promise automatic per-player stats. The design is "CV proposes, human confirms".
- Do not delete `basketball-poc/_work` or touch `~/.cache/huggingface`.
- Test the exact command you hand to Peter (`./start.sh`), not only dev servers; check port 8000 first.
- In zsh do not name a variable `GID`. Run project Python with `-I`.
- No em or en dashes in anything written for Peter, in chat or files. Rewrite the sentence instead.
