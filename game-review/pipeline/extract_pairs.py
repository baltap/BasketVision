"""Torso crops (same geometry as extract_crops.py, 3x upscale) for given (track, frame) pairs.
Usage: extract_pairs.py VIDEO TRACKS_CSV PAIRS_CSV OUT_DIR   -> OUT_DIR/crops.csv"""
import csv, sys
from collections import defaultdict
from pathlib import Path
import cv2
video, tracks_csv, pairs_csv, out = sys.argv[1:5]
out = Path(out); (out / "crops").mkdir(parents=True, exist_ok=True)
box = {}
for r in csv.DictReader(open(tracks_csv)):
    box[(int(r["track_id"]), int(r["frame"]))] = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
need = defaultdict(list)
for r in csv.DictReader(open(pairs_csv)):
    need[int(r["frame"])].append(int(r["track_id"]))
cap = cv2.VideoCapture(video); last = max(need); idx = 0; rows = []
while idx <= last:
    if not cap.grab(): break
    if idx in need:
        ok, img = cap.retrieve(); H, W = img.shape[:2]
        for tid in need[idx]:
            x1, y1, x2, y2 = box[(tid, idx)]; w, h = x2 - x1, y2 - y1
            c = img[int(max(0, y1 + 0.10 * h)):int(min(H, y1 + 0.62 * h)), int(max(0, x1 - 0.05 * w)):int(min(W, x2 + 0.05 * w))]
            if c.size == 0: continue
            c = cv2.resize(c, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
            p = out / "crops" / f"t{tid}_f{idx}.png"; cv2.imwrite(str(p), c)
            rows.append((tid, idx, str(p), y2 - y1))
    idx += 1
with open(out / "crops.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "path", "box_h"]); w.writerows(rows)
print("crops", len(rows))
