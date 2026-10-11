"""Identity test: number-anchored assignment of tracklets to players.

Usage: python -I identity.py TRACKS_CSV VLM_READS_CSV COLOR_CSV OUT_JSON

Anchors  : tracklets (or pieces of impure tracklets) with a confident jersey number.
Attach   : unnumbered pieces join a named player only if exactly one candidate player
           fits (team colour, <= 1.5 s gap, physically plausible, not already elsewhere).
Rest     : left unassigned, i.e. the human review workload.
"""
import csv
import json
import sys
from collections import Counter, defaultdict

import numpy as np

FPS = 30.0
GAP_MAX = 45          # frames, 1.5 s
SPEED_H = 3.0         # body heights per second
SLACK_H = 0.6
OVERLAP_OK = 6        # frames of overlap tolerated between two pieces of the same player
MIN_SHARE = 0.6
MIN_READS = 2
WHITE_ONLY = {"6", "8", "20", "21"}
DARK_ONLY = {"26", "31", "40", "99"}
UNK_BAND = 0.07


def main():
    tracks_csv, reads_csv, color_csv, out_json = sys.argv[1:5]

    tr = defaultdict(list)
    for r in csv.DictReader(open(tracks_csv)):
        if r["on_court"] != "1":
            continue
        x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
        tr[int(r["track_id"])].append((int(r["frame"]), (x1 + x2) / 2, y2, y2 - y1))
    for t in tr:
        tr[t].sort()

    reads = defaultdict(list)
    for r in csv.DictReader(open(reads_csv)):
        if r["text"]:
            reads[int(r["track_id"])].append((int(r["frame"]), r["text"]))
    for t in reads:
        reads[t].sort()

    rr = defaultdict(list)
    for r in csv.DictReader(open(color_csv)):
        rr[int(r["track_id"])].append(float(r["L50"]) / float(r["floorL"]))
    ratio = {t: float(np.median(v)) for t, v in rr.items()}

    # ---- confident number per tracklet (for calibration only) ----
    def confident(rd):
        if not rd:
            return None
        c = Counter(t for _, t in rd)
        top, n = c.most_common(1)[0]
        return top if n >= MIN_READS and n / len(rd) >= MIN_SHARE else None

    cal_w = [ratio[t] for t in tr if t in ratio and confident(reads.get(t)) in WHITE_ONLY]
    cal_d = [ratio[t] for t in tr if t in ratio and confident(reads.get(t)) in DARK_ONLY]
    best = min(
        (sum(1 for x in cal_w if x <= T) + sum(1 for x in cal_d if x > T), T)
        for T in np.arange(0.15, 0.95, 0.01)
    )
    T = float(best[1])
    print(f"team colour calibration from numbered tracklets: light-only numbers n={len(cal_w)} "
          f"(median ratio {np.median(cal_w):.2f}), dark-only numbers n={len(cal_d)} (median {np.median(cal_d):.2f})")
    print(f"  threshold {T:.2f}, calibration errors {best[0]}/{len(cal_w) + len(cal_d)}")

    def team_of(t):
        if t not in ratio:
            return "unk"
        if ratio[t] > T + UNK_BAND:
            return "light"
        if ratio[t] < T - UNK_BAND:
            return "dark"
        return "unk"

    # ---- build pieces ----
    pieces = []

    def add(tid, dets, status, number=None, note=""):
        if not dets:
            return
        lo, hi = dets[0][0], dets[-1][0]
        agree = sum(1 for f, t in reads.get(tid, []) if t == number and lo <= f <= hi) if number else 0
        team = team_of(tid)
        if team == "unk" and number:
            team = "light" if number in WHITE_ONLY else "dark" if number in DARK_ONLY else "unk"
        pieces.append(dict(pid=len(pieces), tid=tid, dets=dets, s=dets[0][0], e=dets[-1][0],
                           team=team, number=number, status=status, note=note, key=None, links=None,
                           agree=agree, dup_of=None))

    n_mixed = n_split = 0
    for tid, dets in tr.items():
        rd = reads.get(tid, [])
        c = Counter(t for _, t in rd)
        strong = [n for n, k in c.items() if k >= MIN_READS]
        if not strong:
            add(tid, dets, "unassigned")
        elif len(strong) == 1:
            n = strong[0]
            if c[n] / len(rd) >= MIN_SHARE:
                add(tid, dets, "anchored", n)
            else:
                add(tid, dets, "unassigned", note="weak vote")
        elif len(strong) == 2:
            a, b = strong
            fa = [f for f, t in rd if t == a]
            fb = [f for f, t in rd if t == b]
            if max(fa) < min(fb) or max(fb) < min(fa):
                first, second = (a, b) if max(fa) < min(fb) else (b, a)
                ff = fa if first == a else fb
                sf = fb if first == a else fa
                cut = (max(ff) + min(sf)) / 2
                add(tid, [d for d in dets if d[0] <= cut], "anchored", first, "split")
                add(tid, [d for d in dets if d[0] > cut], "anchored", second, "split")
                n_split += 1
            else:
                add(tid, dets, "mixed", note=f"interleaved {a}/{b}")
                n_mixed += 1
        else:
            add(tid, dets, "mixed", note="3+ numbers")
            n_mixed += 1
    print(f"tracklets: {len(tr)} | split at a number change: {n_split} | mixed (left unassigned): {n_mixed}")

    def key_of(p):
        return f"{p['team']}#{p['number']}"

    for p in pieces:
        if p["status"] == "anchored":
            p["key"] = key_of(p)

    # ---- resolve same-key conflicts between anchored pieces ----
    stats = Counter()
    for _ in range(20):
        changed = False
        groups = defaultdict(list)
        for p in pieces:
            if p["status"] == "anchored":
                groups[p["key"]].append(p)
        for key, ps in groups.items():
            for i in range(len(ps)):
                for j in range(i + 1, len(ps)):
                    a, b = ps[i], ps[j]
                    if a["status"] != "anchored" or b["status"] != "anchored":
                        continue
                    pa = {d[0]: d for d in a["dets"]}
                    pb = {d[0]: d for d in b["dets"]}
                    shared = sorted(set(pa) & set(pb))
                    if not shared:
                        continue
                    dist = float(np.median([
                        np.hypot(pa[f][1] - pb[f][1], pa[f][2] - pb[f][2]) / (0.5 * (pa[f][3] + pb[f][3]))
                        for f in shared]))
                    if dist < 0.6:
                        if a["dup_of"] is None and b["dup_of"] is None:
                            b["dup_of"] = a["pid"]
                            stats["duplicate pairs (same person, two boxes)"] += 1
                        continue
                    # two different people, same (team, number) at the same time
                    ra, rb = ratio.get(a["tid"]), ratio.get(b["tid"])
                    free_team = a["team"] == "unk" or a["number"] not in (WHITE_ONLY | DARK_ONLY)
                    if free_team and ra is not None and rb is not None and abs(ra - rb) >= 0.05:
                        hi, lo = (a, b) if ra > rb else (b, a)
                        hi["team"], lo["team"] = "light", "dark"
                        hi["key"], lo["key"] = key_of(hi), key_of(lo)
                        stats["relabelled by relative colour"] += 1
                    else:
                        weaker = a if (a["agree"], a["n_reads"] if "n_reads" in a else 0) < (b["agree"], 0) else b
                        if a["agree"] == b["agree"]:
                            for x in (a, b):
                                x["status"], x["key"] = "conflict", None
                            stats["demoted (equal evidence)"] += 2
                        else:
                            weaker = a if a["agree"] < b["agree"] else b
                            weaker["status"], weaker["key"] = "conflict", None
                            stats["demoted (weaker evidence)"] += 1
                    changed = True
        if not changed:
            break
    print("conflict resolution:", dict(stats))

    players = defaultdict(list)
    for p in pieces:
        if p["status"] == "anchored":
            players[p["key"]].append(p["pid"])

    def team_ok(a, b):
        return a == b or "unk" in (a, b)

    def overlap(u, q):
        fu = {d[0] for d in u["dets"]}
        fq = {d[0] for d in q["dets"]}
        if fu & fq:
            return True
        return min(u["e"], q["e"]) - max(u["s"], q["s"]) > OVERLAP_OK

    def close(a, b, gap):
        h = 0.5 * (a[3] + b[3])
        d = float(np.hypot(a[1] - b[1], a[2] - b[2]))
        return d <= (SPEED_H * gap / FPS + SLACK_H) * h

    # ---- conservative attachment, repeated until nothing changes ----
    attached = 0
    for _ in range(10):
        changed = False
        todo = sorted((p for p in pieces if p["status"] == "unassigned" and len(p["dets"]) >= 2), key=lambda p: p["s"])
        for u in todo:
            cands = []
            for key, pids in players.items():
                if not team_ok(u["team"], key.split("#")[0]):
                    continue
                if any(overlap(u, pieces[q]) for q in pids):
                    continue
                link = []
                pre = [q for q in pids if pieces[q]["e"] <= u["s"]]
                if pre:
                    q = max(pre, key=lambda x: pieces[x]["e"])
                    g = u["s"] - pieces[q]["e"]
                    if g <= GAP_MAX and close(pieces[q]["dets"][-1], u["dets"][0], g):
                        link.append(("before", q, g))
                suc = [q for q in pids if pieces[q]["s"] >= u["e"]]
                if suc:
                    q = min(suc, key=lambda x: pieces[x]["s"])
                    g = pieces[q]["s"] - u["e"]
                    if g <= GAP_MAX and close(u["dets"][-1], pieces[q]["dets"][0], g):
                        link.append(("after", q, g))
                if link:
                    cands.append((key, link))
            if len(cands) == 1:
                key, link = cands[0]
                u["status"], u["key"], u["links"] = "attached", key, link
                players[key].append(u["pid"])
                attached += 1
                changed = True
        if not changed:
            break
    print(f"attached unnumbered pieces: {attached}")

    # ---- report ----
    total = sum(len(p["dets"]) for p in pieces)
    def secs(n):
        return n / 10.0  # 10 detections per second at stride 3

    def cnt(pred):
        return sum(len(p["dets"]) for p in pieces if pred(p))

    anch = cnt(lambda p: p["status"] == "anchored")
    att = cnt(lambda p: p["status"] == "attached")
    mixed = cnt(lambda p: p["status"] in ("mixed", "conflict"))
    un = cnt(lambda p: p["status"] == "unassigned")
    print(f"\nplayer detections in total: {total} (about {secs(total):.0f} person-seconds)")
    for name, v in (("anchored by number", anch), ("attached", att), ("mixed / conflicting", mixed), ("unassigned", un)):
        print(f"  {name:<20} {v:>6}  {100 * v / total:5.1f}%")
    print(f"  named (anchored + attached): {100 * (anch + att) / total:.1f}%")

    def dur(p):
        return (p["e"] - p["s"]) / FPS + 0.1
    for lo, hi, label in ((0, 1, "< 1 s"), (1, 3, "1 to 3 s"), (3, 1e9, ">= 3 s")):
        sel = [p for p in pieces if p["status"] in ("unassigned", "mixed", "conflict") and lo <= dur(p) < hi]
        print(f"  unassigned/mixed pieces {label:<9}: {len(sel):>3} pieces, {sum(len(p['dets']) for p in sel):>5} detections "
              f"({100 * sum(len(p['dets']) for p in sel) / total:.1f}%)")

    # conflicts: same player on two detections in one frame
    per_frame = defaultdict(Counter)
    for p in pieces:
        if p["key"] and p["dup_of"] is None:
            for d in p["dets"]:
                per_frame[d[0]][p["key"]] += 1
    conflicts = sum(1 for f in per_frame.values() for k, v in f.items() if v > 1)
    print(f"  frames where one player is assigned to two different people (duplicate boxes excluded): {conflicts}")

    print("\nplayers (team#number): seconds named | anchored s | attached s | pieces | first-last s")
    rows = []
    for key, pids in players.items():
        a = sum(len(pieces[q]["dets"]) for q in pids if pieces[q]["status"] == "anchored")
        b = sum(len(pieces[q]["dets"]) for q in pids if pieces[q]["status"] == "attached")
        s = min(pieces[q]["s"] for q in pids) / FPS
        e = max(pieces[q]["e"] for q in pids) / FPS
        rows.append((secs(a + b), key, secs(a), secs(b), len(pids), s, e))
    for r in sorted(rows, reverse=True):
        print(f"  {r[1]:<10} {r[0]:6.1f} | {r[2]:6.1f} | {r[3]:6.1f} | {r[4]:>3} | {r[5]:5.0f}-{r[6]:.0f}")

    json.dump([{k: v for k, v in p.items() if k != "dets"} | {"frames": [d[0] for d in p["dets"]], "n": len(p["dets"])}
               for p in pieces], open(out_json, "w"))
    print("\nwrote", out_json)


if __name__ == "__main__":
    main()
