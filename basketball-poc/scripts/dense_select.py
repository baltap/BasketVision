"""Pick extra crops for tracklet pieces that are still unassigned.
Usage: dense_select.py ASSIGN_JSON TRACKS_CSV OLD_READS_CSV OUT_PAIRS_CSV [K] [MIN_DET]"""
import csv, json, sys
from collections import defaultdict
import numpy as np
assign, tracks_csv, old_csv, out = sys.argv[1:5]
K = int(sys.argv[5]) if len(sys.argv) > 5 else 60
MIN_DET = int(sys.argv[6]) if len(sys.argv) > 6 else 30
pieces = [p for p in json.load(open(assign)) if p["status"] in ("unassigned", "mixed", "conflict") and p["n"] >= MIN_DET]
have = {(int(r["track_id"]), int(r["frame"])) for r in csv.DictReader(open(old_csv))}
det = defaultdict(dict)
for r in csv.DictReader(open(tracks_csv)):
    if r["on_court"] == "1" and float(r["conf"]) >= 0.5 and float(r["y2"]) - float(r["y1"]) >= 90:
        det[int(r["track_id"])][int(r["frame"])] = float(r["y2"]) - float(r["y1"])
rows = []
for p in pieces:
    fr = sorted(f for f in p["frames"] if f in det[p["tid"]] and (p["tid"], f) not in have)
    if not fr: continue
    idx = np.linspace(0, len(fr) - 1, min(K, len(fr))).round().astype(int)
    for i in sorted(set(idx.tolist())): rows.append((p["tid"], fr[i]))
rows = sorted(set(rows))
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame"]); w.writerows(rows)
print(f"pieces: {len(pieces)} | tracklets: {len({t for t, _ in rows})} | new crops: {len(rows)}")
