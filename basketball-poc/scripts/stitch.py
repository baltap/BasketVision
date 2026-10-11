"""Offline tracklet stitching on top of tracker output.

Usage: python -I stitch.py TRACKS_CSV CROPS_CSV OUT_CSV
 1. team colour per tracklet: chest brightness / floor brightness at the feet (color2.csv)
 2. drop flicker tracklets (very short)
 3. greedy linking of tracklets: same colour cluster, gap <= GAP_S, plausible running speed,
    no overlap in time with anything already in the chain
Writes OUT_CSV: track_id, chain_id, team, n_det, start_s, end_s, mean_h
"""
import csv
import sys
from collections import defaultdict

import cv2
import numpy as np

FPS = 30.0
GAP_S = 3.0          # max gap between end of one tracklet and start of the next
SPEED_H_PER_S = 3.0  # max running speed in body heights per second
SLACK_H = 0.6        # extra allowance in body heights (box jitter)
MIN_DET = 6          # drop tracklets with fewer detections than this (flicker)
MIN_SEC = 0.4
DARK_MAX = 0.42     # chest/floor brightness below this = dark jersey
LIGHT_MIN = 0.55    # above this = light jersey; in between = unknown (links to either)


def main():
    tracks_csv, crops_csv, out_csv = sys.argv[1:4]
    pts = defaultdict(list)
    with open(tracks_csv) as f:
        for r in csv.DictReader(f):
            if r["on_court"] != "1":
                continue
            x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
            pts[int(r["track_id"])].append((int(r["frame"]), (x1 + x2) / 2, y2, y2 - y1))
    for t in pts:
        pts[t].sort()

    # ---- team colour: chest brightness / floor brightness next to the feet ----
    ratios = defaultdict(list)
    with open(crops_csv) as f:   # color2.csv from extract_color.py
        for r in csv.DictReader(f):
            ratios[int(r["track_id"])].append(float(r["L50"]) / float(r["floorL"]))
    team = {}
    for t, v in ratios.items():
        m = float(np.median(v))
        team[t] = "dark" if m < DARK_MAX else ("light" if m > LIGHT_MIN else "unk")
    print("team by floor-normalised brightness:", {k: sum(1 for v in team.values() if v == k) for k in ("dark", "light", "unk")})

    # ---- filter flicker ----
    keep, dropped = [], []
    for t, p in pts.items():
        dur = (p[-1][0] - p[0][0]) / FPS
        (keep if (len(p) >= MIN_DET and dur >= MIN_SEC and t in team) else dropped).append(t)
    print(f"tracklets: {len(pts)}  kept: {len(keep)}  dropped (flicker / no crops): {len(dropped)}")

    info = {}
    for t in keep:
        p = pts[t]
        info[t] = dict(
            start=p[0][0], end=p[-1][0], p0=p[0][1:3], p1=p[-1][1:3],
            h0=np.median([q[3] for q in p[:5]]), h1=np.median([q[3] for q in p[-5:]]),
            frames=set(q[0] for q in p),
        )

    # ---- greedy stitching ----
    parent = {t: t for t in keep}
    chain_frames = {t: set(info[t]["frames"]) for t in keep}
    chain_team = {t: team[t] for t in keep}

    def compat(x, y):
        return x == y or "unk" in (x, y)

    def find(t):
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    cands = []
    for a in keep:
        for b in keep:
            if a == b:
                continue
            gap = (info[b]["start"] - info[a]["end"]) / FPS
            if not (0 < gap <= GAP_S) or not compat(team[a], team[b]):
                continue
            h = 0.5 * (info[a]["h1"] + info[b]["h0"])
            d = float(np.hypot(info[a]["p1"][0] - info[b]["p0"][0], info[a]["p1"][1] - info[b]["p0"][1]))
            allow = (SPEED_H_PER_S * gap + SLACK_H) * h
            if d > allow:
                continue
            cands.append((d / h + 0.4 * gap, a, b))
    cands.sort()
    merges = 0
    for cost, a, b in cands:
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        # chain-level colour must stay consistent (unknown bridges must not join dark and light)
        if not compat(chain_team[ra], chain_team[rb]):
            continue
        # no temporal overlap between chains
        if chain_frames[ra] & chain_frames[rb]:
            continue
        # a must be the last tracklet of its chain and b the first of its chain
        if max(chain_frames[ra]) > info[a]["end"] or min(chain_frames[rb]) < info[b]["start"]:
            continue
        parent[rb] = ra
        if chain_team[ra] == "unk":
            chain_team[ra] = chain_team[rb]
        chain_frames[ra] |= chain_frames[rb]
        merges += 1
    print(f"candidate links: {len(cands)}  merges applied: {merges}")

    chains = defaultdict(list)
    for t in keep:
        chains[find(t)].append(t)

    def stats(label, groups):
        durs = []
        for g in groups:
            fr = set()
            for t in g:
                fr |= info[t]["frames"]
            durs.append((max(fr) - min(fr)) / FPS)
        durs = np.array(durs)
        print(f"{label}: {len(groups)} | >=5s: {(durs >= 5).sum()} | >=10s: {(durs >= 10).sum()} "
              f"| >=20s: {(durs >= 20).sum()} | >=60s: {(durs >= 60).sum()} | median {np.median(durs):.1f}s")

    print()
    stats("before (kept tracklets)", [[t] for t in keep])
    stats("after stitching       ", list(chains.values()))
    # concurrency
    conc = defaultdict(int)
    for g in chains.values():
        fr = set()
        for t in g:
            fr |= info[t]["frames"]
        for f_ in fr:
            conc[f_] += 1
    c = np.array(list(conc.values()))
    print(f"chains active per frame: median {np.median(c):.0f}, p90 {np.percentile(c, 90):.0f}, max {c.max()}")
    by_team = defaultdict(int)
    for root, g in chains.items():
        by_team[chain_team[root]] += 1
    print("chains by colour cluster:", dict(by_team))

    cid = {}
    for n, (root, g) in enumerate(sorted(chains.items(), key=lambda kv: min(info[t]["start"] for t in kv[1]))):
        for t in g:
            cid[t] = n
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["track_id", "chain_id", "team", "n_det", "start_s", "end_s", "mean_h"])
        for t in keep:
            p = pts[t]
            w.writerow([t, cid[t], chain_team[find(t)], len(p), p[0][0] / FPS, p[-1][0] / FPS, float(np.mean([q[3] for q in p]))])
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
