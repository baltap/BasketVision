"""Extract torso crops (for team colour + number reading) for each tracklet.

Usage: python -I extract_crops.py VIDEO TRACKS_CSV OUT_DIR [--per-track 14]
Writes OUT_DIR/crops/t{track}_f{frame}.png (3x upscaled torso, for OCR) and OUT_DIR/crops.csv
with median Lab colour of the shirt area (computed on the original pixels).
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

MIN_H = 90      # px in 4K, skip tiny boxes
MIN_CONF = 0.5
UPSCALE = 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("tracks_csv")
    ap.add_argument("out_dir")
    ap.add_argument("--per-track", type=int, default=14)
    args = ap.parse_args()

    out = Path(args.out_dir)
    (out / "crops").mkdir(parents=True, exist_ok=True)

    rows = defaultdict(list)
    with open(args.tracks_csv) as f:
        for r in csv.DictReader(f):
            if r["on_court"] != "1":
                continue
            x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
            if float(r["conf"]) < MIN_CONF or (y2 - y1) < MIN_H:
                continue
            rows[int(r["track_id"])].append((int(r["frame"]), x1, y1, x2, y2, float(r["conf"])))

    needed = defaultdict(list)  # frame -> [(track, box...)]
    for tid, lst in rows.items():
        lst.sort()
        k = min(args.per_track, len(lst))
        picks = np.linspace(0, len(lst) - 1, k).round().astype(int)
        for i in sorted(set(picks.tolist())):
            fr, x1, y1, x2, y2, c = lst[i]
            needed[fr].append((tid, x1, y1, x2, y2, c))
    print(f"tracks with usable detections: {len(rows)}, crops to extract: {sum(len(v) for v in needed.values())}")

    cap = cv2.VideoCapture(args.video)
    last = max(needed)
    out_rows = []
    idx = 0
    while idx <= last:
        if not cap.grab():
            break
        if idx in needed:
            ok, img = cap.retrieve()
            if ok:
                H, W = img.shape[:2]
                for tid, x1, y1, x2, y2, c in needed[idx]:
                    h = y2 - y1
                    w = x2 - x1
                    cx1 = int(max(0, x1 - 0.05 * w))
                    cx2 = int(min(W, x2 + 0.05 * w))
                    cy1 = int(max(0, y1 + 0.10 * h))
                    cy2 = int(min(H, y1 + 0.62 * h))
                    crop = img[cy1:cy2, cx1:cx2]
                    if crop.size == 0:
                        continue
                    # shirt colour: central columns, upper part of torso
                    ch, cw = crop.shape[:2]
                    core = crop[int(0.0 * ch):int(0.55 * ch), int(0.25 * cw):int(0.75 * cw)]
                    lab = cv2.cvtColor(core, cv2.COLOR_BGR2LAB).reshape(-1, 3)
                    L, a, b = np.median(lab, axis=0)
                    up = cv2.resize(crop, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_LANCZOS4)
                    p = out / "crops" / f"t{tid}_f{idx}.png"
                    cv2.imwrite(str(p), up)
                    out_rows.append((tid, idx, str(p), float(L), float(a), float(b), h, c))
        idx += 1
    cap.release()

    with open(out / "crops.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["track_id", "frame", "path", "L", "a", "b", "box_h", "conf"])
        w.writerows(out_rows)
    print(f"wrote {len(out_rows)} crops from {len(set(r[0] for r in out_rows))} tracks")


if __name__ == "__main__":
    main()
