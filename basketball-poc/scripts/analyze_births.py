"""Where do new track IDs get born, and how many look like cheap re-links of an earlier track?

Usage: python -I analyze_births.py tracks.csv [tracks.csv ...]
Foot point = bottom-centre of the box, in 4K pixels. Only on_court=1 rows are used.
"""
import csv
import sys
from collections import defaultdict

import numpy as np

FPS = 30.0
GAP_S = 2.0       # max time between a track ending and another starting
DIST_PX = 160     # max foot-point distance (4K px) for a candidate re-link
CLUSTER_PX = 220  # another person this close at birth = crowded


def load(path):
    tracks = defaultdict(list)
    by_frame = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["on_court"] != "1":
                continue
            fr, tid = int(r["frame"]), int(r["track_id"])
            x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
            fx, fy = (x1 + x2) / 2, y2
            tracks[tid].append((fr, fx, fy, y2 - y1))
            by_frame[fr].append((tid, fx, fy))
    return tracks, by_frame


def analyze(path):
    tracks, by_frame = load(path)
    info = {}
    for tid, pts in tracks.items():
        pts.sort()
        info[tid] = dict(
            start=pts[0][0], end=pts[-1][0], p0=pts[0][1:3], p1=pts[-1][1:3],
            h0=pts[0][3], n=len(pts),
        )
    ids = sorted(info, key=lambda t: info[t]["start"])
    first_frame = min(i["start"] for i in info.values())

    births = [t for t in ids if info[t]["start"] > first_frame + 15]
    far_end = crowded = relink = 0
    for t in births:
        s = info[t]["start"]
        x, y = info[t]["p0"]
        if x < 1400 and y < 1100:  # far-left end of the court in 4K px
            far_end += 1
        near = [o for o, ox, oy in by_frame.get(s, []) if o != t and np.hypot(ox - x, oy - y) < CLUSTER_PX]
        if near:
            crowded += 1
        for o in ids:
            if o == t:
                continue
            gap = (s - info[o]["end"]) / FPS
            if 0 <= gap <= GAP_S and np.hypot(info[o]["p1"][0] - x, info[o]["p1"][1] - y) < DIST_PX:
                relink += 1
                break
    short = sum(1 for t in info if info[t]["n"] / FPS < 1.0)
    h = np.array([i["h0"] for i in info.values()])
    print(f"\n{path.split('/')[-2]}")
    print(f"  tracks: {len(info)} (born after start: {len(births)}), shorter than 1s of detections: {short}")
    print(f"  births at far-left end of court: {far_end} ({100 * far_end / max(len(births), 1):.0f}%)")
    print(f"  births with another person within {CLUSTER_PX}px: {crowded} ({100 * crowded / max(len(births), 1):.0f}%)")
    print(f"  births that look like a re-link (<= {GAP_S}s, <= {DIST_PX}px from an ended track): {relink} ({100 * relink / max(len(births), 1):.0f}%)")
    print(f"  median box height at birth: {np.median(h):.0f}px (4K)")


for p in sys.argv[1:]:
    analyze(p)
