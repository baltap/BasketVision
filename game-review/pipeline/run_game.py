"""Run the whole pipeline for one game, stage by stage. Resumable: finished stages are skipped.

Usage: run_game.py JOB_DIR      (JOB_DIR/job.json describes the game; progress goes to status.json)
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

JOB = Path(sys.argv[1]).resolve()
CFG = json.loads((JOB / "job.json").read_text())
PIPE = Path(CFG["pipelineDir"])
BACKEND = Path(CFG["backendDir"])
DATA = Path(CFG["dataDir"])
WORK = JOB / "work"
WORK.mkdir(exist_ok=True)
LOG = open(JOB / "log.txt", "a", buffering=1)
PY = sys.executable
ENV = {**os.environ, "HF_HOME": CFG["hfHome"], "PYTHONUNBUFFERED": "1"}

# key, label shown to the person, share of the total time (from measured runs)
STAGES = [
    ("prepare", "Prepare the video", 2),
    ("follow", "Find and follow every person", 14),
    ("cutouts", "Cut out each player", 3),
    ("numbers", "Read jersey numbers", 32),
    ("colours", "Read shirt colours", 20),
    ("closer", "Look closer at unclear pieces", 26),
    ("build", "Name players and build the game", 3),
]
TOTAL_W = sum(w for _, _, w in STAGES)
state = {
    "state": "running", "startedAt": time.time(), "updatedAt": time.time(), "error": None, "gameId": CFG["id"],
    "stages": [{"key": k, "label": l, "pct": 0.0, "state": "waiting"} for k, l, _ in STAGES],
    "overall": 0.0, "note": "",
}


def save():
    done = sum(w * (1.0 if s["state"] == "done" else s["pct"]) for (_, _, w), s in zip(STAGES, state["stages"]))
    state["overall"] = round(done / TOTAL_W, 4)
    state["updatedAt"] = time.time()
    tmp = JOB / "status.json.tmp"
    tmp.write_text(json.dumps(state))
    tmp.replace(JOB / "status.json")


def set_stage(i, st, pct=None):
    state["stages"][i]["state"] = st
    if pct is not None:
        state["stages"][i]["pct"] = max(0.0, min(1.0, pct))
    save()


class Failed(Exception):
    pass


def run(cmd, i, parse=None):
    LOG.write("$ " + " ".join(str(c) for c in cmd) + "\n")
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         bufsize=1, env=ENV, cwd=str(PIPE))
    last = 0.0
    out = []
    for line in p.stdout:
        LOG.write(line)
        out.append(line)
        if parse:
            pct = parse(line)
            if pct is not None and time.time() - last > 1.0:
                last = time.time()
                set_stage(i, "running", pct)
    rc = p.wait()
    if rc != 0:
        tail = "".join(out[-12:]).strip()
        raise Failed(f"{Path(str(cmd[1])).name if len(cmd) > 1 else cmd[0]} stopped with code {rc}. {tail[-500:]}")
    return "".join(out)


def counter(line):
    m = re.match(r"\s*(\d+)/(\d+)\b", line)
    return int(m.group(1)) / max(1, int(m.group(2))) if m else None


def ffmpeg_progress(total_sec):
    def parse(line):
        m = re.match(r"out_time_us=(\d+)", line)
        return int(m.group(1)) / 1e6 / max(total_sec, 0.1) if m else None
    return parse


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,duration:format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    n, d = s["r_frame_rate"].split("/")
    return {"fps": float(n) / float(d), "width": s["width"], "height": s["height"],
            "duration": float(s.get("duration") or j["format"]["duration"])}


def marker(key):
    return WORK / f".done_{key}"


# ---- stages ----
def prepare(i):
    src = CFG["video"]
    info = probe(src)
    start, dur = CFG.get("startSec"), CFG.get("durSec")
    cut = start is not None and dur
    needs_fps = abs(info["fps"] - 30) >= 0.5
    if not cut and not needs_fps:
        (WORK / "video.txt").write_text(src)
        return
    out = WORK / "clip.mkv"
    cmd = ["ffmpeg", "-y", "-v", "error", "-nostats", "-progress", "pipe:1"]
    if cut:
        cmd += ["-ss", str(start)]
    cmd += ["-i", src]
    if cut:
        cmd += ["-t", str(dur)]
    if needs_fps:
        cmd += ["-r", "30", "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-an", str(out)]
    run(cmd, i, parse=ffmpeg_progress(dur if cut else info["duration"]))
    (WORK / "video.txt").write_text(str(out))


def video():
    return (WORK / "video.txt").read_text().strip()


def follow(i):
    run([PY, "-u", PIPE / "track.py", video(), WORK / "tracks.csv", "--polygon", WORK / "polygon.json",
         "--stride", "3", "--model", PIPE / "models" / "yolo11l.pt"], i, parse=counter)


def cutouts(i):
    (WORK / "c").mkdir(exist_ok=True)
    run([PY, PIPE / "extract_crops.py", video(), WORK / "tracks.csv", WORK / "c"], i)
    set_stage(i, "running", 0.5)
    run([PY, PIPE / "extract_body.py", video(), WORK / "tracks.csv", WORK / "c" / "crops.csv", WORK / "body"], i)


def numbers(i):
    run([PY, "-u", PIPE / "vlm_all.py", WORK / "c" / "crops.csv", WORK / "reads_pass1.csv", WORK / "roster.json"],
        i, parse=counter)


def colours(i):
    run([PY, "-u", PIPE / "vlm_attrs.py", WORK / "body" / "body.csv", WORK / "attrs.csv"], i, parse=counter)


def identity(reads, out):
    run([PY, PIPE / "identity7.py", WORK / "tracks.csv", reads, WORK / "attrs.csv", out, "--roster",
         WORK / "roster.json", "--trim", "--evidence", "count", "--no-attach"], 0)


def closer(i):
    identity(WORK / "reads_pass1.csv", WORK / "assign_pass1.json")
    set_stage(i, "running", 0.05)
    (WORK / "dense").mkdir(exist_ok=True)
    out = run([PY, PIPE / "dense_select.py", WORK / "assign_pass1.json", WORK / "tracks.csv", WORK / "reads_pass1.csv",
               WORK / "dense" / "pairs.csv", "60", "30"], i)
    m = re.search(r"new crops: (\d+)", out)
    if not m or int(m.group(1)) == 0:
        shutil.copy(WORK / "reads_pass1.csv", WORK / "reads_merged.csv")
        return
    run([PY, PIPE / "extract_pairs.py", video(), WORK / "tracks.csv", WORK / "dense" / "pairs.csv", WORK / "dense"], i)
    set_stage(i, "running", 0.1)
    run([PY, "-u", PIPE / "vlm_all.py", WORK / "dense" / "crops.csv", WORK / "reads_dense.csv", WORK / "roster.json"],
        i, parse=lambda l: (0.1 + 0.9 * counter(l)) if counter(l) is not None else None)
    run([PY, PIPE / "merge_reads.py", WORK / "reads_pass1.csv", WORK / "reads_dense.csv", WORK / "reads_merged.csv"], i)


def build(i):
    identity(WORK / "reads_merged.csv", WORK / "assign_final.json")
    set_stage(i, "running", 0.3)
    game_dir = DATA / "games" / CFG["id"]
    inputs = game_dir / "pipeline_inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    for name in ("tracks.csv", "attrs.csv"):
        shutil.copy(WORK / name, inputs / name)
    shutil.copy(WORK / "reads_merged.csv", inputs / "reads.csv")
    shutil.copy(WORK / "assign_final.json", inputs / "assign.json")
    cfg = {
        "id": CFG["id"], "title": CFG["title"], "date": CFG["date"], "windowLabel": CFG["windowLabel"],
        "offsetSec": CFG.get("startSec") or 0, "teams": CFG["teams"], "video": video(),
        "tracks_csv": str(inputs / "tracks.csv"), "assign_json": str(inputs / "assign.json"),
        "reads_csv": str(inputs / "reads.csv"), "attrs_csv": str(inputs / "attrs.csv"),
        "roster_json": str(WORK / "roster.json"),
    }
    (JOB / "gamepack_cfg.json").write_text(json.dumps(cfg, indent=1))
    run([PY, "-u", BACKEND / "gamepack.py", JOB / "gamepack_cfg.json", "--data-dir", DATA], i)
    # the big intermediates are not needed once the pack exists
    for d in ("c", "body", "dense"):
        shutil.rmtree(WORK / d, ignore_errors=True)
    if (WORK / "clip.mkv").exists():
        (WORK / "clip.mkv").unlink()


FUNCS = {"prepare": prepare, "follow": follow, "cutouts": cutouts, "numbers": numbers, "colours": colours,
         "closer": closer, "build": build}


def main():
    try:
        for i, (key, _label, _w) in enumerate(STAGES):
            if marker(key).exists():
                set_stage(i, "done", 1.0)
                continue
            set_stage(i, "running", 0.0)
            FUNCS[key](i)
            marker(key).write_text("ok")
            set_stage(i, "done", 1.0)
        state["state"] = "done"
        save()
    except Failed as e:
        state["state"], state["error"] = "failed", str(e)
        LOG.write(f"FAILED: {e}\n")
        save()
        sys.exit(1)
    except Exception:  # noqa: BLE001
        state["state"], state["error"] = "failed", traceback.format_exc()[-800:]
        LOG.write(state["error"])
        save()
        sys.exit(1)


if __name__ == "__main__":
    main()
