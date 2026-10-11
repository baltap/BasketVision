"""Add-a-game jobs: validate, start the pipeline as a detached process, report progress, cancel, resume."""
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mts"}

# Rough costs measured on the first two 3-minute clips (M-series Mac, 64 GB).
MIN_PER_FOOTAGE_MIN = (8, 15)       # minutes of waiting per minute of footage
GB_PER_FOOTAGE_MIN = 0.2            # crops, pictures, proxy video and results while processing


def config():
    p = PIPELINE / "config.json"
    cfg = json.loads(p.read_text()) if p.exists() else {}
    cfg.setdefault("hf_home", os.environ.get("GAME_REVIEW_HF_HOME",
                   "/Users/peter/Data/Claude/BasketVision/basketball-poc/_work/hf"))
    return cfg


def system_check(data_dir: Path):
    cfg = config()
    hf = Path(cfg["hf_home"]) / "hub" / "models--mlx-community--Qwen2.5-VL-7B-Instruct-4bit"
    snaps = list((hf / "snapshots").glob("*")) if (hf / "snapshots").exists() else []
    free = shutil.disk_usage(data_dir if data_dir.exists() else data_dir.parent).free / 1e9
    checks = [
        {"key": "ffmpeg", "label": "ffmpeg", "ok": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
         "fix": "Install it with: brew install ffmpeg"},
        {"key": "detector", "label": "Person detector", "ok": bool(importlib.util.find_spec("ultralytics"))
         and (PIPELINE / "models" / "yolo11l.pt").exists(), "fix": "Needs the ultralytics package and pipeline/models/yolo11l.pt"},
        {"key": "reader", "label": "Number reader (Qwen2.5-VL, 5.65 GB)", "ok": bool(importlib.util.find_spec("mlx_vlm")) and bool(snaps),
         "fix": f"Needs mlx-vlm and the model in {cfg['hf_home']}"},
        {"key": "cv", "label": "Image tools", "ok": bool(importlib.util.find_spec("cv2")), "fix": "Needs opencv-python-headless"},
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "diskFreeGB": round(free, 1), "hfHome": cfg["hf_home"],
            "minPerFootageMin": MIN_PER_FOOTAGE_MIN, "gbPerFootageMin": GB_PER_FOOTAGE_MIN}


def probe(path: str):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,codec_name,duration:format=duration,size", "-of", "json", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ValueError("Could not read this file as a video.")
    j = json.loads(r.stdout)
    s = j["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"], "fps": round(float(n) / float(d), 2), "codec": s.get("codec_name"),
            "durationSec": round(float(s.get("duration") or j["format"]["duration"]), 1),
            "sizeBytes": int(j["format"].get("size", 0))}


def list_dir(path: str):
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise ValueError("Not a folder")
    entries = []
    try:
        for e in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if e.name.startswith("."):
                continue
            if e.is_dir():
                entries.append({"name": e.name, "kind": "dir"})
            elif e.suffix.lower() in VIDEO_EXT:
                entries.append({"name": e.name, "kind": "video", "size": e.stat().st_size})
    except PermissionError:
        raise ValueError("This folder is not readable. macOS may be asking for permission.")
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "entries": entries}


def frame_jpeg(path: str, t: float, width: int = 1280) -> bytes:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0.0, t)), "-i", path, "-frames:v", "1", "-vf",
                        f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "4", "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise ValueError("Could not read a picture from this video.")
    return r.stdout


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24] or "game"


def new_id(data_dir: Path, title: str, date: str) -> str:
    base = f"{date}-{slug(title)}" if date else slug(title)
    gid, n = base, 2
    while (data_dir / "games" / gid).exists() or (data_dir / "jobs" / gid).exists():
        gid = f"{base}-{n}"
        n += 1
    return gid


def create(data_dir: Path, body: dict) -> dict:
    video = body["video"]
    if not Path(video).is_file():
        raise ValueError("The video file was not found.")
    info = probe(video)
    roster = body["roster"]
    if not roster.get("light") or not roster.get("dark"):
        raise ValueError("List the jersey numbers for both teams first.")
    start, dur = body.get("startSec"), body.get("durSec")
    footage = dur if (start is not None and dur) else info["durationSec"]
    need = footage / 60 * GB_PER_FOOTAGE_MIN
    free = shutil.disk_usage(data_dir).free / 1e9
    if free < need + 2:
        raise ValueError(f"Not enough free disk space: about {need:.1f} GB needed, {free:.1f} GB free.")
    gid = new_id(data_dir, body["title"], body["date"])
    job = data_dir / "jobs" / gid
    (job / "work").mkdir(parents=True)
    cfg = config()
    meta = {
        "id": gid, "title": body["title"], "date": body["date"], "teams": body["teams"],
        "windowLabel": body.get("windowLabel") or "", "video": video, "startSec": start, "durSec": dur,
        "footageSec": footage, "probe": info, "createdAt": time.time(),
        "pipelineDir": str(PIPELINE), "backendDir": str(ROOT / "backend"), "dataDir": str(data_dir), "hfHome": cfg["hf_home"],
    }
    (job / "job.json").write_text(json.dumps(meta, indent=1))
    (job / "work" / "polygon.json").write_text(json.dumps(body["polygon"]))
    (job / "work" / "roster.json").write_text(json.dumps(roster))
    return spawn(data_dir, gid)


def spawn(data_dir: Path, gid: str) -> dict:
    job = data_dir / "jobs" / gid
    log = open(job / "orchestrator.log", "a")
    p = subprocess.Popen([sys.executable, "-u", str(PIPELINE / "run_game.py"), str(job)], stdout=log,
                         stderr=subprocess.STDOUT, cwd=str(PIPELINE), start_new_session=True)
    meta = json.loads((job / "job.json").read_text())
    meta["pid"] = p.pid
    (job / "job.json").write_text(json.dumps(meta, indent=1))
    # a resume starts from a clean "running" status file
    st = job / "status.json"
    if st.exists():
        s = json.loads(st.read_text())
        s.update({"state": "running", "error": None})
        st.write_text(json.dumps(s))
    return status(data_dir, gid)


def alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status(data_dir: Path, gid: str) -> dict:
    job = data_dir / "jobs" / gid
    if not (job / "job.json").exists():
        raise FileNotFoundError(gid)
    meta = json.loads((job / "job.json").read_text())
    st = json.loads((job / "status.json").read_text()) if (job / "status.json").exists() else {
        "state": "starting", "stages": [], "overall": 0.0, "error": None, "startedAt": meta["createdAt"], "updatedAt": time.time()}
    if st["state"] in ("running", "starting") and not alive(meta.get("pid")):
        if st["state"] == "starting" and time.time() - meta["createdAt"] < 5:
            pass
        else:
            st["state"] = "interrupted"
            st["error"] = st.get("error") or "The process stopped before it finished. You can resume it."
    log = ""
    if (job / "log.txt").exists():
        log = "".join((job / "log.txt").read_text(errors="replace").splitlines(True)[-40:])
    return {**st, "id": gid, "title": meta["title"], "date": meta["date"], "footageSec": meta["footageSec"],
            "log": log, "createdAt": meta["createdAt"]}


def list_jobs(data_dir: Path):
    d = data_dir / "jobs"
    if not d.exists():
        return []
    out = []
    for p in sorted(d.iterdir(), key=lambda x: -x.stat().st_mtime):
        if (p / "job.json").exists():
            s = status(data_dir, p.name)
            s.pop("log", None)
            out.append(s)
    return out


def cancel(data_dir: Path, gid: str) -> dict:
    job = data_dir / "jobs" / gid
    meta = json.loads((job / "job.json").read_text())
    pid = meta.get("pid")
    if alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass
    st = job / "status.json"
    s = json.loads(st.read_text()) if st.exists() else {"stages": [], "overall": 0.0}
    s.update({"state": "cancelled", "error": None})
    st.write_text(json.dumps(s))
    return status(data_dir, gid)


def discard(data_dir: Path, gid: str):
    cancel(data_dir, gid)
    shutil.rmtree(data_dir / "jobs" / gid, ignore_errors=True)
