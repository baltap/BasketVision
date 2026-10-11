"""Turn pipeline outputs into an app data pack for one game.

A pack is a plain folder the app can serve without any model:

  data/games/<id>/
    game.json         meta, window, pipeline paths
    roster.json       {"light": [...], "dark": [...]}  (editable in the app)
    pieces.json       one entry per stretch of tracked footage, with evidence
    detections.json   boxes over time, for the video overlay and heatmaps
    crops/ thumbs/    pictures shown as evidence
    media/proxy.mp4   1080p copy for playback
    media/original.*  hard link to the source file (what "delete footage" removes)

Usage:  python gamepack.py CONFIG.json [--data-dir DIR] [--no-video]
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2

FPS = 30.0
STEP = 3                    # detections exist on every third source frame
CROP_H = 320
THUMB_W = 960
CROWD_FRAC = 0.25           # same threshold the pipeline uses to ignore reads in crowds


def read_tracks(path):
    box, allbox = {}, defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            t, fr = int(r["track_id"]), int(r["frame"])
            b = (float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"]))
            box[(t, fr)] = b
            allbox[fr].append((t,) + b)
    return box, allbox


def is_crowded(tid, frame, box, allbox):
    b = box.get((tid, frame))
    if not b:
        return False
    area = max((b[2] - b[0]) * (b[3] - b[1]), 1.0)
    for t2, x1, y1, x2, y2 in allbox.get(frame, ()):
        if t2 == tid:
            continue
        iw = min(b[2], x2) - max(b[0], x1)
        ih = min(b[3], y2) - max(b[1], y1)
        if iw > 0 and ih > 0 and iw * ih / area > CROWD_FRAC:
            return True
    return False


def spread(items, k):
    """k items spread evenly across a sorted list."""
    if k <= 0 or not items:
        return []
    if len(items) <= k:
        return list(items)
    return [items[round(i * (len(items) - 1) / max(k - 1, 1))] for i in range(k)]


def pick_frames(frames, reads_in, k=6):
    """Prefer frames where the reader saw something, then fill with evenly spaced ones."""
    frames = sorted(frames)
    chosen = []
    if reads_in:
        top = Counter(t for _, t in reads_in).most_common(1)[0][0]
        top_frames = sorted(f for f, t in reads_in if t == top)
        other_frames = sorted(f for f, t in reads_in if t != top)
        chosen += spread(top_frames, 3)
        chosen += spread(other_frames, 1)
    taken = set(chosen)
    rest = [f for f in frames if f not in taken]
    chosen += spread(rest, k - len(taken))
    return sorted(set(chosen))[:k]


def build(cfg, data_dir, make_video=True, log=print):
    t0 = time.time()
    root = Path(data_dir) / "games" / cfg["id"]
    for sub in ("crops", "thumbs", "media"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    log("reading pipeline outputs")
    box, allbox = read_tracks(cfg["tracks_csv"])
    reads = defaultdict(list)
    with open(cfg["reads_csv"]) as f:
        for r in csv.DictReader(f):
            if r["text"]:
                reads[int(r["track_id"])].append((int(r["frame"]), r["text"]))
    assigned = json.load(open(cfg["assign_json"]))

    cap = cv2.VideoCapture(cfg["video"])
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    pieces, detections, tasks = [], [], defaultdict(list)
    for p in assigned:
        frames = sorted(p["frames"])
        if not frames:
            continue
        tid = p["tid"]
        pid = f"{tid}_{frames[0]}"
        fset = set(frames)
        rin = [(f, t) for f, t in reads[tid] if f in fset]
        crowded = {f for f, _ in rin if is_crowded(tid, f, box, allbox)}
        read_at = {f: t for f, t in rin}
        crop_frames = pick_frames(frames, rin, 6)
        crops = []
        for f in crop_frames:
            name = f"t{tid}_f{f}.jpg"
            kind = "none" if f not in read_at else ("neighbor" if f in crowded else "read")
            crops.append({"file": name, "sec": round(f / FPS, 2), "read": read_at.get(f, ""), "kind": kind})
            if not (root / "crops" / name).exists():
                tasks[f].append(("crop", tid, root / "crops" / name))
        mid = frames[len(frames) // 2]
        thumb_name = f"t{tid}_f{mid}.jpg"
        if not (root / "thumbs" / thumb_name).exists():
            tasks[mid].append(("thumb", tid, root / "thumbs" / thumb_name))
        mb = box.get((tid, mid), (0, 0, 0, 0))
        idx = len(pieces)
        pieces.append({
            "id": pid, "tid": tid, "startFrame": frames[0], "endFrame": frames[-1],
            "startSec": round(frames[0] / FPS, 2), "endSec": round(frames[-1] / FPS + STEP / FPS, 2),
            "n": len(frames), "status": p["status"], "team": p["team"], "number": p["number"], "key": p["key"],
            "agree": p.get("agree", 0), "note": p.get("note", ""),
            "readCounts": dict(Counter(t for _, t in rin)), "crowdedReads": len(crowded), "reads": len(rin),
            "crops": crops,
            "thumb": {"file": thumb_name, "sec": round(mid / FPS, 2),
                      "box": [round(mb[0] / W, 4), round(mb[1] / H, 4), round(mb[2] / W, 4), round(mb[3] / H, 4)]},
        })
        for f in frames:
            b = box.get((tid, f))
            if b:
                detections.append([f // STEP, idx, round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)])

    log(f"{len(pieces)} pieces, {len(detections)} detections; extracting {sum(len(v) for v in tasks.values())} pictures")
    last = max(tasks) if tasks else -1
    idx = 0
    while idx <= last:
        if not cap.grab():
            break
        if idx in tasks:
            ok, img = cap.retrieve()
            if ok:
                for kind, tid, out in tasks[idx]:
                    if kind == "thumb":
                        s = THUMB_W / W
                        cv2.imwrite(str(out), cv2.resize(img, (THUMB_W, int(H * s)), interpolation=cv2.INTER_AREA),
                                    [cv2.IMWRITE_JPEG_QUALITY, 80])
                    else:
                        b = box.get((tid, idx))
                        if not b:
                            continue
                        w, h = b[2] - b[0], b[3] - b[1]
                        c = img[int(max(0, b[1] - 0.05 * h)):int(min(H, b[3] + 0.05 * h)),
                                int(max(0, b[0] - 0.10 * w)):int(min(W, b[2] + 0.10 * w))]
                        if c.size:
                            s = CROP_H / c.shape[0]
                            c = cv2.resize(c, (max(1, int(c.shape[1] * s)), CROP_H), interpolation=cv2.INTER_CUBIC)
                            cv2.imwrite(str(out), c, [cv2.IMWRITE_JPEG_QUALITY, 88])
        idx += 1
    cap.release()

    (root / "pieces.json").write_text(json.dumps(pieces))
    (root / "detections.json").write_text(json.dumps({"step": STEP, "fps": FPS, "items": detections}))
    if not (root / "roster.json").exists():
        shutil.copy(cfg["roster_json"], root / "roster.json")

    # video: proxy for playback, hard link for the original
    proxy = root / "media" / "proxy.mp4"
    if make_video and not proxy.exists():
        log("encoding 1080p proxy")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", cfg["video"], "-vf", "scale=1920:-2", "-c:v", "libx264",
                        "-crf", "27", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
                        str(proxy)], check=True)
    orig = root / "media" / ("original" + Path(cfg["video"]).suffix)
    if not orig.exists() and not orig.is_symlink():
        try:
            os.link(cfg["video"], orig)
        except OSError:
            os.symlink(cfg["video"], orig)

    game = {
        "id": cfg["id"], "title": cfg.get("title", cfg["id"]), "date": cfg.get("date", ""),
        "windowLabel": cfg.get("windowLabel", ""), "offsetSec": cfg.get("offsetSec", 0),
        "teams": cfg.get("teams", {"light": "Team A", "dark": "Team B"}),
        "fps": FPS, "step": STEP, "width": W, "height": H,
        "durationSec": round(total_frames / FPS, 1),
        "pipeline": {k: cfg[k] for k in ("video", "tracks_csv", "assign_json", "reads_csv", "attrs_csv")},
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (root / "game.json").write_text(json.dumps(game, indent=1))
    log(f"done in {time.time() - t0:.0f}s -> {root}")
    return game


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--data-dir", default=str(Path(__file__).resolve().parent.parent / "data"))
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    build(json.load(open(a.config)), a.data_dir, make_video=not a.no_video)
