"""Local API for the game review app. Everything stays on this machine."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import analysis
import gamepack
import jobs

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("GAME_REVIEW_DATA", ROOT / "data"))
GAMES = DATA / "games"
PIPELINE = ROOT / "pipeline"

GAMES.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Game review")
_cache = {}


# ---------- storage helpers ----------
def gdir(gid: str) -> Path:
    d = GAMES / gid
    if not (d / "game.json").exists():
        raise HTTPException(404, f"No game {gid}")
    return d


def cached(path: Path, default=None):
    if not path.exists():
        return default
    m = path.stat().st_mtime_ns
    hit = _cache.get(path)
    if hit and hit[0] == m:
        return hit[1]
    val = json.loads(path.read_text())
    _cache[path] = (m, val)
    return val


def write_json(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(path)


def load(gid: str):
    d = gdir(gid)
    game = cached(d / "game.json")
    pieces = cached(d / "pieces.json", [])
    roster = cached(d / "roster.json", {"light": [], "dark": []})
    answers = cached(d / "corrections.json", {"answers": []})["answers"]
    dets = cached(d / "detections.json", {"items": []})["items"]
    return d, game, pieces, roster, answers, dets


def footage_state(d: Path):
    media = d / "media"
    video = (media / "proxy.mp4").exists()
    pics = (d / "crops").exists() and any((d / "crops").iterdir())
    return {"video": video, "pictures": pics}


def piece_out(gid, p, roster):
    return {
        "id": p["id"], "tid": p["tid"], "startSec": p["startSec"], "endSec": p["endSec"],
        "durSec": round(p["n"] / analysis.DET_HZ, 1), "n": p["n"], "team": p["team"], "state": p["state"],
        "key": p.get("key"), "skipped": p["skipped"], "note": p["note"], "status": p["status"],
        "answered": p["answered"], "suggestion": analysis.suggestion(p, roster),
        "crops": [{**c, "url": f"/files/{gid}/crops/{c['file']}"} for c in p["crops"]],
        "thumb": {**p["thumb"], "url": f"/files/{gid}/thumbs/{p['thumb']['file']}"},
        "crowdedReads": p["crowdedReads"], "reads": p["reads"],
    }


# ---------- games ----------
def game_card(gid):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    return {**game, "coverage": analysis.coverage(eff), "footage": footage_state(d)}


@app.get("/api/games")
def list_games():
    if not GAMES.exists():
        return []
    return [game_card(p.name) for p in sorted(GAMES.iterdir()) if (p / "game.json").exists()]


@app.get("/api/games/{gid}")
def get_game(gid: str):
    return game_card(gid)


# ---------- review ----------
class AnswerIn(BaseModel):
    pieceId: str
    kind: Literal["number", "ignore", "skip"]
    number: Optional[str] = None
    team: Optional[Literal["light", "dark"]] = None


@app.get("/api/games/{gid}/queue")
def get_queue(gid: str):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    items = [piece_out(gid, p, roster) for p in analysis.queue(eff)]
    # pieces answered this session stay reachable so the person can look back at them
    done = [piece_out(gid, p, roster) for p in eff if p["answered"] and p["answered"]["kind"] != "skip"]
    return {"items": items, "done": done, "coverage": analysis.coverage(eff), "roster": roster,
            "history": len(answers)}


@app.post("/api/games/{gid}/answers")
def post_answer(gid: str, a: AnswerIn):
    d, game, pieces, roster, answers, dets = load(gid)
    piece = next((p for p in pieces if p["id"] == a.pieceId), None)
    if not piece:
        raise HTTPException(404, "No such piece")
    if a.kind == "number":
        if not a.number or not a.number.isdigit():
            raise HTTPException(422, "A number is required")
        team = a.team or (piece["team"] if piece["team"] in ("light", "dark") else None)
        if team is None:
            raise HTTPException(422, "Pick which team this player is on")
        if a.number not in roster.get(team, []):
            raise HTTPException(422, f"#{a.number} is not on the {team} roster. Add it in Roster first.")
        a.team = team
    entry = {"pieceId": a.pieceId, "tid": piece["tid"], "startFrame": piece["startFrame"], "endFrame": piece["endFrame"],
             "kind": a.kind, "number": a.number, "team": a.team, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if a.kind == "skip" and answers and answers[-1]["kind"] == "skip" and answers[-1]["pieceId"] == a.pieceId:
        return {"ok": True, "history": len(answers)}      # skipping the same piece again changes nothing
    new = list(answers) + [entry]
    write_json(d / "corrections.json", {"answers": new})
    return {"ok": True, "history": len(new)}


@app.post("/api/games/{gid}/undo")
def undo(gid: str):
    d, game, pieces, roster, answers, dets = load(gid)
    if not answers:
        return {"ok": False, "history": 0}
    last = answers[-1]
    write_json(d / "corrections.json", {"answers": list(answers[:-1])})
    return {"ok": True, "undone": last, "history": len(answers) - 1}


# ---------- views ----------
@app.get("/api/games/{gid}/team")
def get_team(gid: str):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    view = analysis.team_view(eff, dets, roster)
    return {**view, "coverage": analysis.coverage(eff), "roster": roster, "windowSec": game["durationSec"]}


@app.get("/api/games/{gid}/timeline")
def get_timeline(gid: str):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    return {**analysis.timeline(eff, dets), "durationSec": game["durationSec"], "coverage": analysis.coverage(eff)}


@app.get("/api/games/{gid}/overlay")
def get_overlay(gid: str):
    """Boxes over time with the name each one currently carries."""
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    labels = []
    for p in eff:
        labels.append({"state": p["state"], "key": p.get("key")})
    return {"step": game["step"], "fps": game["fps"], "labels": labels, "items": dets}


@app.get("/api/games/{gid}/players/{key:path}")
def get_player(gid: str, key: str):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    detail = analysis.player_detail(eff, dets, key, roster)
    if not detail["seconds"]:
        raise HTTPException(404, f"No footage named {key}")
    detail["pieces"] = [piece_out(gid, p, roster) for p in detail["pieces"]]
    evs = [e for e in cached(d / "events.json", {"events": []})["events"] if e["key"] == key]
    evs.sort(key=lambda e: e["sec"])
    return {**detail, "events": evs, "stats": analysis.event_stats(evs),
            "windowSec": game["durationSec"], "coverage": analysis.coverage(eff)}


# ---------- roster ----------
class RosterIn(BaseModel):
    light: list[str]
    dark: list[str]


def clean_numbers(xs):
    out = []
    for x in xs:
        x = str(x).strip().lstrip("#")
        if x.isdigit() and 0 <= int(x) <= 99 and x not in out:
            out.append(str(int(x)))
    return sorted(out, key=int)


@app.get("/api/games/{gid}/roster")
def get_roster(gid: str):
    d, game, pieces, roster, answers, dets = load(gid)
    eff = analysis.effective_pieces(pieces, answers)
    return {"roster": roster, "unlisted": analysis.unlisted_numbers(eff, roster), "teams": game["teams"]}


@app.put("/api/games/{gid}/roster")
def put_roster(gid: str, r: RosterIn):
    d = gdir(gid)
    write_json(d / "roster.json", {"light": clean_numbers(r.light), "dark": clean_numbers(r.dark)})
    return get_roster(gid)


@app.post("/api/games/{gid}/recompute")
def recompute(gid: str):
    """Re-run the cheap naming step with the current roster. No model is involved."""
    d, game, pieces, roster, answers, dets = load(gid)
    p = game["pipeline"]
    out = d / "pipeline_assign.json"
    cmd = [sys.executable, str(PIPELINE / "identity7.py"), p["tracks_csv"], p["reads_csv"], p["attrs_csv"], str(out),
           "--roster", str(d / "roster.json"), "--trim", "--evidence", "count", "--no-attach"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise HTTPException(500, "Naming step failed: " + res.stderr[-400:])
    media = d / "media"
    original = next((f for f in media.iterdir() if f.name.startswith("original")), None) if media.exists() else None
    if original is None or not original.exists():
        raise HTTPException(409, "The original video was deleted, so names cannot be recomputed.")
    cfg = {"id": game["id"], "title": game["title"], "date": game["date"], "windowLabel": game["windowLabel"],
           "offsetSec": game["offsetSec"], "teams": game["teams"], **p, "assign_json": str(out),
           "roster_json": str(d / "roster.json"), "video": str(original)}
    gamepack.build(cfg, DATA, make_video=False, log=lambda *_: None)
    return {"ok": True, "coverage": game_card(gid)["coverage"]}


# ---------- storage ----------
def dir_size(path: Path):
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


@app.get("/api/games/{gid}/storage")
def get_storage(gid: str):
    d = gdir(gid)
    media = d / "media"
    orig = next((f for f in media.iterdir() if f.name.startswith("original")), None) if media.exists() else None
    results = sum(dir_size(d / n) for n in ("pieces.json", "detections.json", "game.json", "roster.json",
                                             "corrections.json", "pipeline_assign.json"))
    game = cached(d / "game.json")
    return {
        "folder": str(d), "date": game.get("date"), "footage": footage_state(d),
        "usage": [
            {"name": "Game video (playback copy)", "detail": "1080p copy used for playback", "bytes": dir_size(media / "proxy.mp4")},
            {"name": "Game video (original)", "detail": orig.name if orig else "removed", "bytes": dir_size(orig) if orig else 0},
            {"name": "Working pictures", "detail": "Cropped players and frames shown as evidence",
             "bytes": dir_size(d / "crops") + dir_size(d / "thumbs")},
            {"name": "Results", "detail": "Names, minutes, lineups and your corrections", "bytes": results},
        ],
    }


class DeleteIn(BaseModel):
    what: Literal["video", "video_and_pictures", "everything"]
    confirm: str


@app.post("/api/games/{gid}/storage/delete")
def delete_footage(gid: str, body: DeleteIn):
    d = gdir(gid)
    game = cached(d / "game.json")
    if body.confirm.strip() not in (game.get("date"), game["id"]):
        raise HTTPException(422, "Type the game date to confirm.")
    media = d / "media"
    if body.what == "everything":
        shutil.rmtree(d)
        return {"ok": True, "deleted": "everything"}
    for f in list(media.iterdir()) if media.exists() else []:
        f.unlink()
    if body.what == "video_and_pictures":
        for sub in ("crops", "thumbs"):
            if (d / sub).exists():
                shutil.rmtree(d / sub)
                (d / sub).mkdir()
    return {"ok": True, "deleted": body.what, **get_storage(gid)}


# ---------- moments a person tags (shots, assists, rebounds...) ----------
EVENT_TYPES = ("made2", "made3", "made1", "missed", "assist", "rebound", "steal", "turnover", "foul")


class EventIn(BaseModel):
    key: str
    type: Literal["made2", "made3", "made1", "missed", "assist", "rebound", "steal", "turnover", "foul"]
    sec: float


@app.post("/api/games/{gid}/events")
def add_event(gid: str, e: EventIn):
    d = gdir(gid)
    events = list(cached(d / "events.json", {"events": []})["events"])
    ev = {"id": f"e{int(time.time() * 1000)}", "key": e.key, "type": e.type, "sec": round(e.sec, 1),
          "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    events.append(ev)
    write_json(d / "events.json", {"events": events})
    return ev


@app.delete("/api/games/{gid}/events/{eid}")
def delete_event(gid: str, eid: str):
    d = gdir(gid)
    events = [e for e in cached(d / "events.json", {"events": []})["events"] if e["id"] != eid]
    write_json(d / "events.json", {"events": events})
    return {"ok": True}


# ---------- add a game ----------
def _mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


@app.get("/api/system")
def system():
    return jobs.system_check(DATA)


@app.get("/api/fs")
def fs_list(path: str = "~"):
    try:
        return jobs.list_dir(path)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/probe")
def probe(path: str):
    try:
        return jobs.probe(path)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/frame")
def frame(path: str, t: float = 5.0):
    try:
        return Response(jobs.frame_jpeg(path, t), media_type="image/jpeg")
    except ValueError as e:
        raise HTTPException(400, str(e))


class JobIn(BaseModel):
    video: str
    title: str
    date: str
    teams: dict[str, str]
    roster: RosterIn
    polygon: list[list[float]]
    startSec: Optional[float] = None
    durSec: Optional[float] = None


@app.post("/api/jobs")
def create_job(b: JobIn):
    if len(b.polygon) < 4:
        raise HTTPException(422, "Mark at least four corners of the court.")
    body = b.model_dump()
    body["roster"] = {"light": clean_numbers(b.roster.light), "dark": clean_numbers(b.roster.dark)}
    body["windowLabel"] = (f"{_mmss(b.startSec)} to {_mmss(b.startSec + b.durSec)}"
                           if b.startSec is not None and b.durSec else "whole video")
    try:
        return jobs.create(DATA, body)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/jobs")
def list_jobs():
    return jobs.list_jobs(DATA)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    try:
        return jobs.status(DATA, jid)
    except FileNotFoundError:
        raise HTTPException(404, "No such job")


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    return jobs.cancel(DATA, jid)


@app.post("/api/jobs/{jid}/resume")
def resume_job(jid: str):
    return jobs.spawn(DATA, jid)


@app.delete("/api/jobs/{jid}")
def delete_job(jid: str):
    jobs.discard(DATA, jid)
    return {"ok": True}


# ---------- files and the built frontend ----------
app.mount("/files", StaticFiles(directory=str(GAMES)), name="files")
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="ui")
else:
    from fastapi.responses import HTMLResponse

    @app.get("/", response_class=HTMLResponse)
    def ui_not_built():
        return ("<h1>Game Review</h1><p>The interface is not built yet. Stop this server and run "
                "<code>./start.sh</code> from the game-review folder, or <code>pnpm build</code> in "
                "<code>frontend/</code> and restart.</p>")
