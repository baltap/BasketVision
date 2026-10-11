"""Verification sheets + annotated video for the identity test.

Usage: python -I identity_viz.py VIDEO TRACKS_CSV ASSIGN_JSON OUT_DIR [--video]
Sheets: anchored sample, and EVERY attached piece shown as
  [anchor before] [attached first] [attached last] [anchor after]
"""
import csv
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

video, tracks_csv, assign_json, out_dir = sys.argv[1:5]
make_video = "--video" in sys.argv
out = Path(out_dir)
pieces = json.load(open(assign_json))
byp = {p["pid"]: p for p in pieces}

box = {}
for r in csv.DictReader(open(tracks_csv)):
    if r["on_court"] == "1":
        box[(int(r["track_id"]), int(r["frame"]))] = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))

# ---- what to show ----
rng = random.Random(4)
anch = [p for p in pieces if p["status"] == "anchored" and p["n"] >= 8 and p["dup_of"] is None]
rng.shuffle(anch)
_a, _b = (int(x) for x in os.environ.get('ANCH_SLICE', '0:14').split(':'))
anch = sorted(anch[_a:_b], key=lambda p: p["pid"])
att = sorted((p for p in pieces if p["status"] == "attached"), key=lambda p: p["frames"][0])

need = defaultdict(set)   # frame -> {tid}
def want(tid, fr):
    if (tid, fr) in box:
        need[fr].add(tid)
        return (tid, fr)
    return None

tiles = []   # (title, [(slot_key or None, kind)])
for p in anch:
    fr = p["frames"]
    idx = np.linspace(0, len(fr) - 1, 4).round().astype(int)
    slots = [(want(p["tid"], fr[i]), "anchor") for i in idx]
    tiles.append((f"ANCHORED {p['key']}  t{p['tid']} agree={p['agree']} n={p['n']}  {fr[0] / 30:.0f}-{fr[-1] / 30:.0f}s", slots, "A"))
for p in att:
    slots = []
    before = next((l for l in p["links"] if l[0] == "before"), None)
    after = next((l for l in p["links"] if l[0] == "after"), None)
    qb = byp[before[1]] if before else None
    qa = byp[after[1]] if after else None
    slots.append((want(qb["tid"], qb["frames"][-1]) if qb else None, "anchor" if qb and qb["status"] == "anchored" else "attached"))
    slots.append((want(p["tid"], p["frames"][0]), "attached"))
    slots.append((want(p["tid"], p["frames"][-1]), "attached"))
    slots.append((want(qa["tid"], qa["frames"][0]) if qa else None, "anchor" if qa and qa["status"] == "anchored" else "attached"))
    gap = "/".join(f"{l[0]} {l[2] / 30:.1f}s" for l in p["links"])
    tiles.append((f"ATTACHED -> {p['key']}  t{p['tid']} n={p['n']} {p['frames'][0] / 30:.0f}-{p['frames'][-1] / 30:.0f}s  ({gap})", slots, "B"))

# ---- decode needed frames once ----
crops = {}
CH = 170
cap = cv2.VideoCapture(video)
last = max(need) if need else 0
idx = 0
while idx <= last:
    if not cap.grab():
        break
    if idx in need:
        ok, img = cap.retrieve()
        if ok:
            H, W = img.shape[:2]
            for tid in need[idx]:
                x1, y1, x2, y2 = box[(tid, idx)]
                w, h = x2 - x1, y2 - y1
                cx1, cx2 = int(max(0, x1 - 0.08 * w)), int(min(W, x2 + 0.08 * w))
                cy1, cy2 = int(max(0, y1 - 0.05 * h)), int(min(H, y2 + 0.05 * h))
                c = img[cy1:cy2, cx1:cx2]
                s = CH / c.shape[0]
                crops[(tid, idx)] = cv2.resize(c, (max(1, int(c.shape[1] * s)), CH), interpolation=cv2.INTER_AREA)
    idx += 1
cap.release()

def tile_img(title, slots, kind):
    SW = 118
    row = np.full((CH + 22, SW * 4 + 6, 3), 30, np.uint8)
    cv2.putText(row, title[:78], (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
    for i, (key, role) in enumerate(slots):
        x0 = 3 + i * SW
        if key is None or key not in crops:
            cv2.rectangle(row, (x0, 20), (x0 + SW - 4, 20 + CH), (60, 60, 60), 1)
            continue
        c = crops[key][:, :SW - 4]
        row[20:20 + c.shape[0], x0:x0 + c.shape[1]] = c
        col = (60, 220, 60) if role == "anchor" else (230, 200, 0)
        cv2.rectangle(row, (x0, 20), (x0 + SW - 4, 20 + CH - 1), col, 2)
    return row

def sheet(items, path, cols=2):
    rows = []
    imgs = [tile_img(*t) for t in items]
    while len(imgs) % cols:
        imgs.append(np.full_like(imgs[0], 30))
    for i in range(0, len(imgs), cols):
        rows.append(np.hstack(imgs[i:i + cols]))
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])

A = [t for t in tiles if t[2] == "A"]
B = [t for t in tiles if t[2] == "B"]
sheet(A, out / "verify_anchored.jpg")
half = (len(B) + 1) // 2
sheet(B[:half], out / "verify_attached_1.jpg")
sheet(B[half:], out / "verify_attached_2.jpg")
print(f"sheets: anchored {len(A)}, attached {len(B)}")

if make_video:
    label = {}
    for p in pieces:
        for f in p["frames"]:
            label[(p["tid"], f)] = (p["status"], p["key"])
    cap = cv2.VideoCapture(video)
    wr = None
    idx = 0
    COL = {"anchored": (60, 220, 60), "attached": (230, 200, 0), "unassigned": (150, 150, 150),
           "mixed": (60, 60, 230), "conflict": (60, 60, 230), "nonplayer": (0, 140, 255)}
    while True:
        if not cap.grab():
            break
        if idx % 3 == 0:
            ok, img = cap.retrieve()
            if not ok:
                break
            small = cv2.resize(img, (1600, 900), interpolation=cv2.INTER_AREA)
            sc = 1600 / img.shape[1]
            for (tid, f), b in ((k, v) for k, v in box.items() if k[1] == idx):
                st, key = label.get((tid, f), ("unassigned", None))
                p1, p2 = (int(b[0] * sc), int(b[1] * sc)), (int(b[2] * sc), int(b[3] * sc))
                col = COL.get(st, (150, 150, 150))
                cv2.rectangle(small, p1, p2, col, 2)
                if key:
                    team, num = key.split("#")
                    txt = f"{team[0].upper()}{num}"
                    cv2.putText(small, txt, (p1[0], max(p1[1] - 5, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            cv2.putText(small, f"t={idx / 30:6.1f}s   green=named  cyan=attached  grey=unassigned  orange=non-player  red=conflict",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            if wr is None:
                wr = cv2.VideoWriter(str(out / "identity_raw.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (1600, 900))
            wr.write(small)
        idx += 1
    cap.release()
    if wr:
        wr.release()
    print("video written")
