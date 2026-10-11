"""Identity test, round 2: VLM top-colour + age attributes, crowd guard, split on colour change.

Usage: python -I identity2.py TRACKS_CSV NUMBER_READS_CSV ATTRS_CSV OUT_JSON

Changes against round 1 (identity.py):
  * non-players (orange/red/pink top = referee, ADULT votes) are removed before naming
  * team = VLM jersey colour vote (WHITE -> light, DARK -> dark) instead of brightness ratio
  * number reads where another person's box covers > 25% of the target box are ignored
  * tracklets are split where the colour flips cleanly (ID swap between the two teams)
"""
import csv
import json
import sys
from collections import Counter, defaultdict

import numpy as np

FPS = 30.0
GAP_MAX = 45
SPEED_H = 3.0
SLACK_H = 0.6
OVERLAP_OK = 6
MIN_SHARE = 0.6
MIN_READS = 2
CROWD_FRAC = 0.25
NONPLAYER_SHARE = 0.5


def main():
    tracks_csv, reads_csv, attrs_csv, out_json = sys.argv[1:5]

    tr = defaultdict(list)
    allbox = defaultdict(list)
    for r in csv.DictReader(open(tracks_csv)):
        x1, y1, x2, y2 = (float(r[k]) for k in ("x1", "y1", "x2", "y2"))
        t, f = int(r["track_id"]), int(r["frame"])
        allbox[f].append((t, x1, y1, x2, y2))
        if r["on_court"] == "1":
            tr[t].append((f, (x1 + x2) / 2, y2, y2 - y1))
    for t in tr:
        tr[t].sort()

    # ---- number reads with crowd guard ----
    box = {(t, f): (x1, y1, x2, y2) for f, lst in allbox.items() for t, x1, y1, x2, y2 in lst}
    reads = defaultdict(list)
    kept = dropped = 0
    for r in csv.DictReader(open(reads_csv)):
        if not r["text"]:
            continue
        t, f = int(r["track_id"]), int(r["frame"])
        b = box.get((t, f))
        crowded = False
        if b:
            area = max((b[2] - b[0]) * (b[3] - b[1]), 1.0)
            for t2, x1, y1, x2, y2 in allbox[f]:
                if t2 == t:
                    continue
                iw = min(b[2], x2) - max(b[0], x1)
                ih = min(b[3], y2) - max(b[1], y1)
                if iw > 0 and ih > 0 and iw * ih / area > CROWD_FRAC:
                    crowded = True
                    break
        if crowded:
            dropped += 1
        else:
            kept += 1
            reads[t].append((f, r["text"]))
    for t in reads:
        reads[t].sort()
    print(f"number reads: kept {kept}, dropped by crowd guard {dropped} ({100 * dropped / max(kept + dropped, 1):.0f}%)")

    # ---- attributes per tracklet ----
    attrs = defaultdict(list)   # tid -> [(frame, age, color)]
    for r in csv.DictReader(open(attrs_csv)):
        attrs[int(r["track_id"])].append((int(r["frame"]), r["age"], r["color"]))
    for t in attrs:
        attrs[t].sort()

    def nonplayer(t):
        a = attrs.get(t, [])
        cols = [c for _, _, c in a if c]
        ages = [g for _, g, _ in a if g]
        if len(cols) >= 3 and sum(1 for c in cols if c == "ORANGE") / len(cols) >= NONPLAYER_SHARE:
            return "referee (orange top)"
        if len(ages) >= 3 and sum(1 for g in ages if g == "ADULT") / len(ages) >= NONPLAYER_SHARE:
            return "adult"
        return None

    def segments(t, dets):
        """Split a tracklet at a clean WHITE/DARK colour change. Returns [(lo, hi, team)] over frames."""
        votes = [(f, c) for f, _, c in attrs.get(t, []) if c in ("WHITE", "DARK")]
        lo, hi = dets[0][0], dets[-1][0]

        def team_of(vs):
            if len(vs) < 2:
                return "unk"
            w = sum(1 for _, c in vs if c == "WHITE")
            return "light" if w > len(vs) - w else "dark"

        if len(votes) >= 6:
            best = None
            for k in range(3, len(votes) - 2):
                left, right = votes[:k], votes[k:]
                for a, b in (("WHITE", "DARK"), ("DARK", "WHITE")):
                    good = sum(1 for _, c in left if c == a) + sum(1 for _, c in right if c == b)
                    pl = sum(1 for _, c in left if c == a) / len(left)
                    pr = sum(1 for _, c in right if c == b) / len(right)
                    if pl >= 0.85 and pr >= 0.85 and (best is None or good > best[0]):
                        best = (good, k)
            if best:
                k = best[1]
                cut = (votes[k - 1][0] + votes[k][0]) / 2
                return [(lo, cut, team_of(votes[:k])), (cut + 1e-6, hi, team_of(votes[k:]))], True
        return [(lo, hi, team_of(votes))], False

    # ---- pieces ----
    pieces = []

    def add(tid, dets, status, team, number=None, note=""):
        if not dets:
            return
        lo, hi = dets[0][0], dets[-1][0]
        agree = sum(1 for f, tx in reads.get(tid, []) if tx == number and lo <= f <= hi) if number else 0
        pieces.append(dict(pid=len(pieces), tid=tid, dets=dets, s=lo, e=hi, team=team, number=number,
                           status=status, note=note, key=None, links=None, agree=agree, dup_of=None))

    n_nonplayer = n_colour_split = n_num_split = n_mixed = 0
    for tid, dets in tr.items():
        why = nonplayer(tid)
        if why:
            add(tid, dets, "nonplayer", "none", note=why)
            n_nonplayer += 1
            continue
        segs, did_split = segments(tid, dets)
        n_colour_split += did_split
        for lo, hi, team in segs:
            sd = [d for d in dets if lo <= d[0] <= hi]
            rd = [(f, t) for f, t in reads.get(tid, []) if lo <= f <= hi]
            c = Counter(t for _, t in rd)
            strong = [n for n, k in c.items() if k >= MIN_READS]
            if not strong:
                add(tid, sd, "unassigned", team)
            elif len(strong) == 1:
                n = strong[0]
                if c[n] / len(rd) >= MIN_SHARE:
                    add(tid, sd, "anchored", team, n)
                else:
                    add(tid, sd, "unassigned", team, note="weak vote")
            elif len(strong) == 2:
                a, b = strong
                fa = [f for f, t in rd if t == a]
                fb = [f for f, t in rd if t == b]
                if max(fa) < min(fb) or max(fb) < min(fa):
                    first, second = (a, b) if max(fa) < min(fb) else (b, a)
                    ff = fa if first == a else fb
                    sf = fb if first == a else fa
                    cut = (max(ff) + min(sf)) / 2
                    add(tid, [d for d in sd if d[0] <= cut], "anchored", team, first, "split")
                    add(tid, [d for d in sd if d[0] > cut], "anchored", team, second, "split")
                    n_num_split += 1
                else:
                    add(tid, sd, "mixed", team, note=f"interleaved {a}/{b}")
                    n_mixed += 1
            else:
                add(tid, sd, "mixed", team, note="3+ numbers")
                n_mixed += 1
    print(f"tracklets: {len(tr)} | non-players removed: {n_nonplayer} | split on colour change: {n_colour_split} "
          f"| split on number change: {n_num_split} | mixed: {n_mixed}")

    for p in pieces:
        if p["status"] == "anchored":
            p["key"] = f"{p['team']}#{p['number']}"

    # ---- conflicts between anchored pieces with the same key ----
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
                    dist = float(np.median([np.hypot(pa[f][1] - pb[f][1], pa[f][2] - pb[f][2]) /
                                            (0.5 * (pa[f][3] + pb[f][3])) for f in shared]))
                    if dist < 0.6:
                        if a["dup_of"] is None and b["dup_of"] is None:
                            b["dup_of"] = a["pid"]
                            stats["duplicate pairs (same person, two boxes)"] += 1
                        continue
                    if a["agree"] == b["agree"]:
                        for x in (a, b):
                            x["status"], x["key"] = "conflict", None
                        stats["demoted (equal evidence)"] += 2
                    else:
                        w = a if a["agree"] < b["agree"] else b
                        w["status"], w["key"] = "conflict", None
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
        if {d[0] for d in u["dets"]} & {d[0] for d in q["dets"]}:
            return True
        return min(u["e"], q["e"]) - max(u["s"], q["s"]) > OVERLAP_OK

    def close(a, b, gap):
        h = 0.5 * (a[3] + b[3])
        return float(np.hypot(a[1] - b[1], a[2] - b[2])) <= (SPEED_H * gap / FPS + SLACK_H) * h

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
    def cnt(pred):
        return sum(len(p["dets"]) for p in pieces if pred(p))
    rows = [("anchored by number", cnt(lambda p: p["status"] == "anchored")),
            ("attached", cnt(lambda p: p["status"] == "attached")),
            ("non-player (ref/adult)", cnt(lambda p: p["status"] == "nonplayer")),
            ("mixed / conflicting", cnt(lambda p: p["status"] in ("mixed", "conflict"))),
            ("unassigned", cnt(lambda p: p["status"] == "unassigned"))]
    print(f"\ndetections in total: {total}")
    for name, v in rows:
        print(f"  {name:<24} {v:>6}  {100 * v / total:5.1f}%")
    players_total = total - rows[2][1]
    named = rows[0][1] + rows[1][1]
    print(f"  named of PLAYER detections: {100 * named / players_total:.1f}%  ({named}/{players_total})")

    def dur(p):
        return (p["e"] - p["s"]) / FPS + 0.1
    for lo, hi, label in ((0, 1, "< 1 s"), (1, 3, "1 to 3 s"), (3, 1e9, ">= 3 s")):
        sel = [p for p in pieces if p["status"] in ("unassigned", "mixed", "conflict") and lo <= dur(p) < hi]
        print(f"  unassigned pieces {label:<9}: {len(sel):>3} pieces, {sum(len(p['dets']) for p in sel):>5} detections "
              f"({100 * sum(len(p['dets']) for p in sel) / total:.1f}%)")
    per_frame = defaultdict(Counter)
    for p in pieces:
        if p["key"] and p["dup_of"] is None:
            for d in p["dets"]:
                per_frame[d[0]][p["key"]] += 1
    print(f"  frames with a player assigned to two different people: {sum(1 for f in per_frame.values() for v in f.values() if v > 1)}")

    print("\nplayers (team#number): named s | anchored s | attached s | pieces | first-last s")
    prow = []
    for key, pids in players.items():
        a = sum(len(pieces[q]["dets"]) for q in pids if pieces[q]["status"] == "anchored")
        b = sum(len(pieces[q]["dets"]) for q in pids if pieces[q]["status"] == "attached")
        prow.append(((a + b) / 10, key, a / 10, b / 10, len(pids),
                     min(pieces[q]["s"] for q in pids) / FPS, max(pieces[q]["e"] for q in pids) / FPS))
    for r in sorted(prow, reverse=True):
        print(f"  {r[1]:<10} {r[0]:6.1f} | {r[2]:6.1f} | {r[3]:6.1f} | {r[4]:>3} | {r[5]:5.0f}-{r[6]:.0f}")

    json.dump([{k: v for k, v in p.items() if k != "dets"} | {"frames": [d[0] for d in p["dets"]], "n": len(p["dets"])}
               for p in pieces], open(out_json, "w"))
    print("\nwrote", out_json)


if __name__ == "__main__":
    main()
