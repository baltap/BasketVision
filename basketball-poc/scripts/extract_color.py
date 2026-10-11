"""Per-crop shirt colour normalised by the floor next to the player's feet.
Usage: extract_color.py VIDEO TRACKS_CSV CROPS_CSV OUT_CSV"""
import csv, sys
from collections import defaultdict
import cv2, numpy as np
video, tracks_csv, crops_csv, out_csv = sys.argv[1:5]
box = {}
with open(tracks_csv) as f:
    for r in csv.DictReader(f):
        box[(int(r["track_id"]), int(r["frame"]))] = tuple(float(r[k]) for k in ("x1", "y1", "x2", "y2"))
need = defaultdict(list)
with open(crops_csv) as f:
    for r in csv.DictReader(f):
        k = (int(r["track_id"]), int(r["frame"]))
        if k in box: need[k[1]].append(k[0])
cap = cv2.VideoCapture(video); last = max(need); idx = 0; out = []
while idx <= last:
    if not cap.grab(): break
    if idx in need:
        ok, img = cap.retrieve(); H, W = img.shape[:2]
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        for tid in need[idx]:
            x1, y1, x2, y2 = box[(tid, idx)]; w, h = x2 - x1, y2 - y1
            cx1, cx2 = int(x1 + 0.30 * w), int(x1 + 0.70 * w)
            cy1, cy2 = int(y1 + 0.22 * h), int(y1 + 0.50 * h)
            fx1, fx2 = int(max(0, x1 - 0.3 * w)), int(min(W, x2 + 0.3 * w))
            fy1, fy2 = int(min(H - 2, y2 + 0.02 * h)), int(min(H - 1, y2 + 0.14 * h))
            ch = lab[cy1:cy2, cx1:cx2].reshape(-1, 3).astype(float)
            fl = lab[fy1:fy2, fx1:fx2].reshape(-1, 3).astype(float)
            if len(ch) < 20 or len(fl) < 20: continue
            floorL = np.median(fl[:, 0]) + 1e-6
            out.append((tid, idx, np.median(ch[:, 0]), np.percentile(ch[:, 0], 80), np.percentile(ch[:, 0], 20),
                        ch[:, 1].mean(), ch[:, 2].mean(), floorL))
    idx += 1
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "L50", "L80", "L20", "a", "b", "floorL"]); w.writerows(out)
print("rows", len(out))
