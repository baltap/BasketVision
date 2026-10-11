"""Full-body crops (with margin) for the (track, frame) pairs in a reads csv.
Usage: extract_body.py VIDEO TRACKS_CSV PAIRS_CSV OUT_DIR"""
import csv, sys
from collections import defaultdict
from pathlib import Path
import cv2
video, tracks_csv, pairs_csv, out = sys.argv[1:5]
out = Path(out); out.mkdir(parents=True, exist_ok=True)
box = {}
for r in csv.DictReader(open(tracks_csv)):
    box[(int(r["track_id"]), int(r["frame"]))] = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
need = defaultdict(list)
for r in csv.DictReader(open(pairs_csv)):
    k = (int(r["track_id"]), int(r["frame"]))
    if k in box: need[k[1]].append(k[0])
cap = cv2.VideoCapture(video); last = max(need); idx = 0; rows = []
while idx <= last:
    if not cap.grab(): break
    if idx in need:
        ok, img = cap.retrieve(); H, W = img.shape[:2]
        for tid in need[idx]:
            x1, y1, x2, y2 = box[(tid, idx)]; w, h = x2 - x1, y2 - y1
            c = img[int(max(0, y1 - 0.05 * h)):int(min(H, y2 + 0.05 * h)), int(max(0, x1 - 0.10 * w)):int(min(W, x2 + 0.10 * w))]
            if c.size == 0: continue
            s = 320 / c.shape[0]
            c = cv2.resize(c, (max(1, int(c.shape[1] * s)), 320), interpolation=cv2.INTER_CUBIC)
            p = out / f"t{tid}_f{idx}.jpg"; cv2.imwrite(str(p), c, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows.append((tid, idx, str(p), h))
    idx += 1
with open(out / "body.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "path", "box_h"]); w.writerows(rows)
print("body crops", len(rows))
