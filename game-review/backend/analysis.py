"""Everything derived from pieces + corrections: coverage, lanes, minutes, lineups, checks, heat."""
from collections import Counter, defaultdict

DET_HZ = 10.0           # detections per second (every third frame at 30 fps)
GAP_FILL = 15           # a player unseen for up to 1.5 s is treated as still on court
MIN_QUEUE_N = 30        # pieces shorter than 3 s are not asked about
TEAM_SIZE = 5
TINY_SECONDS = 8.0


def _overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def effective_pieces(pieces, answers):
    """Overlay the person's answers (newest wins) on the pipeline's pieces."""
    by_tid = defaultdict(list)
    for a in answers:
        by_tid[a["tid"]].append(a)
    out = []
    for p in pieces:
        e = dict(p)
        base = p["status"]
        e["state"] = "named" if base in ("anchored", "attached") else ("nonplayer" if base == "nonplayer" else "open")
        e["skipped"] = False
        e["answered"] = None
        mine = None
        for a in by_tid.get(p["tid"], ()):
            ov = _overlap(a["startFrame"], a["endFrame"], p["startFrame"], p["endFrame"])
            span = max(1, min(a["endFrame"] - a["startFrame"], p["endFrame"] - p["startFrame"]))
            if ov / span >= 0.5:
                mine = a
        if mine:
            e["answered"] = {"kind": mine["kind"], "number": mine.get("number"), "team": mine.get("team")}
            if mine["kind"] == "number":
                team = mine.get("team") or (p["team"] if p["team"] in ("light", "dark") else None)
                e["state"], e["key"] = "confirmed", f"{team}#{mine['number']}"
            elif mine["kind"] == "ignore":
                e["state"], e["key"] = "nonplayer", None
            elif mine["kind"] == "skip":
                e["skipped"] = True
        out.append(e)
    return out


def roster_numbers(roster, team):
    if team in roster:
        return set(roster[team])
    return set().union(*[set(v) for v in roster.values()]) if roster else set()


def suggestion(piece, roster):
    ok = roster_numbers(roster, piece["team"])
    valid = {n: c for n, c in piece["readCounts"].items() if n in ok}
    unlisted = {n: c for n, c in piece["readCounts"].items() if n not in ok}
    ranked = sorted(valid.items(), key=lambda kv: -kv[1])
    top = ranked[0] if ranked else None
    alt = ranked[1] if len(ranked) > 1 else None
    return {
        "number": top[0] if top else None, "count": top[1] if top else 0,
        "alt": alt[0] if alt else None, "altCount": alt[1] if alt else 0,
        "reads": piece["reads"], "unlisted": unlisted,
    }


def coverage(eff):
    players = [p for p in eff if p["state"] != "nonplayer"]
    tot = sum(p["n"] for p in players) or 1
    named = sum(p["n"] for p in players if p["state"] == "named")
    conf = sum(p["n"] for p in players if p["state"] == "confirmed")
    openn = sum(p["n"] for p in players if p["state"] == "open")
    queue = [p for p in players if p["state"] == "open" and p["n"] >= MIN_QUEUE_N]
    return {
        "playerSeconds": round(tot / DET_HZ, 1),
        "namedPct": round(100 * named / tot, 1), "confirmedPct": round(100 * conf / tot, 1),
        "openPct": round(100 * openn / tot, 1),
        "queueCount": len([p for p in queue if not p["skipped"]]),
        "skippedCount": len([p for p in queue if p["skipped"]]),
        "queueSeconds": round(sum(p["n"] for p in queue) / DET_HZ, 1),
    }


def queue(eff):
    items = [p for p in eff if p["state"] == "open" and p["n"] >= MIN_QUEUE_N]
    items.sort(key=lambda p: (p["skipped"], -p["n"]))
    return items


def _presence(eff, det_items):
    """key -> sorted time indexes present, with short gaps filled."""
    raw = defaultdict(set)
    for t, idx, *_ in det_items:
        p = eff[idx]
        if p["state"] in ("named", "confirmed") and p.get("key"):
            raw[p["key"]].add(t)
    filled = {}
    for key, ts in raw.items():
        ts = sorted(ts)
        out, run_start, prev = set(), ts[0], ts[0]
        for t in ts[1:]:
            if t - prev > GAP_FILL:
                out.update(range(run_start, prev + 1))
                run_start = t
            prev = t
        out.update(range(run_start, prev + 1))
        filled[key] = out
    return raw, filled


def _runs(ts, gap=GAP_FILL):
    ts = sorted(ts)
    if not ts:
        return []
    runs, s, prev = [], ts[0], ts[0]
    for t in ts[1:]:
        if t - prev > gap:
            runs.append((s, prev))
            s = t
        prev = t
    runs.append((s, prev))
    return runs


def _num(key):
    try:
        return int(key.split("#")[1])
    except (IndexError, ValueError):
        return 0


def team_view(eff, det_items, roster):
    raw, filled = _presence(eff, det_items)
    players = {"light": [], "dark": []}
    for key, ts in filled.items():
        team = key.split("#")[0]
        if team not in players:
            continue
        runs = _runs(raw[key])
        players[team].append({
            "key": key, "number": key.split("#")[1],
            "seconds": round(len(ts) / DET_HZ, 1), "shifts": len(runs),
            "tiny": len(ts) / DET_HZ < TINY_SECONDS,
        })
    for team in players:
        players[team].sort(key=lambda r: -r["seconds"])

    per_t = {"light": defaultdict(set), "dark": defaultdict(set)}
    for key, ts in filled.items():
        team = key.split("#")[0]
        if team in per_t:
            for t in ts:
                per_t[team][t].add(key)

    lineups, overfull = {"light": [], "dark": []}, []
    for team, by_t in per_t.items():
        units = Counter()
        over_ts = []
        for t, keys in by_t.items():
            if len(keys) > TEAM_SIZE:
                over_ts.append((t, keys))
                continue
            ordered = sorted(keys, key=_num)
            label = " · ".join([k.split("#")[1] for k in ordered] + ["?"] * (TEAM_SIZE - len(ordered)))
            units[label] += 1
        lineups[team] = [{"units": u, "seconds": round(c / DET_HZ, 1)} for u, c in units.most_common()
                         if c / DET_HZ >= 3.0][:6]
        over_ts.sort()
        group = []
        for t, keys in over_ts:
            if group and t - group[-1][0] > 5:
                overfull.append(_pack_overfull(team, group))
                group = []
            group.append((t, keys))
        if group:
            overfull.append(_pack_overfull(team, group))
    overfull = [o for o in overfull if o["seconds"] >= 1.0]

    seen = {k.split("#")[1] for k in filled}
    seen_by_team = {team: {k.split("#")[1] for k in filled if k.startswith(team + "#")} for team in ("light", "dark")}
    not_seen = {team: [n for n in roster.get(team, []) if n not in seen_by_team[team]] for team in ("light", "dark")}
    return {"players": players, "lineups": lineups, "overfull": overfull, "notSeen": not_seen,
            "tiny": [{"key": r["key"], "seconds": r["seconds"]} for t in players for r in players[t] if r["tiny"]]}


def _pack_overfull(team, group):
    keys = sorted({k for _, ks in group for k in ks}, key=_num)
    return {"team": team, "startSec": round(group[0][0] / DET_HZ, 1), "endSec": round(group[-1][0] / DET_HZ + 0.1, 1),
            "seconds": round((group[-1][0] - group[0][0] + 1) / DET_HZ, 1), "keys": keys}


def timeline(eff, det_items):
    raw, filled = _presence(eff, det_items)
    lanes = []
    for key, ts in filled.items():
        segs = []
        for s, e in _runs(ts, gap=1):
            segs.append([round(s / DET_HZ, 1), round((e + 1) / DET_HZ, 1)])
        # state per segment: confirmed if any confirmed piece covers it, else named
        conf_t = set()
        for t, idx, *_ in det_items:
            p = eff[idx]
            if p.get("key") == key and p["state"] == "confirmed":
                conf_t.add(t)
        seg_out = []
        for s, e in segs:
            s_i, e_i = int(round(s * DET_HZ)), int(round(e * DET_HZ))
            hit = any(t in conf_t for t in range(s_i, e_i))
            seg_out.append({"start": s, "end": e, "state": "confirmed" if hit else "named"})
        lanes.append({"key": key, "team": key.split("#")[0], "number": key.split("#")[1],
                      "seconds": round(len(ts) / DET_HZ, 1), "segments": seg_out})
    lanes.sort(key=lambda l: (l["team"] != "light", -l["seconds"]))

    openset, nonset = set(), set()
    for t, idx, *_ in det_items:
        p = eff[idx]
        if p["state"] == "open":
            openset.add(t)
        elif p["state"] == "nonplayer":
            nonset.add(t)
    to_segs = lambda ts: [{"start": round(s / DET_HZ, 1), "end": round((e + 1) / DET_HZ, 1)} for s, e in _runs(ts, gap=3)]
    return {"lanes": lanes, "open": to_segs(openset), "nonplayer": to_segs(nonset)}


def player_detail(eff, det_items, key, roster=None, grid=(32, 18)):
    raw, filled = _presence(eff, det_items)
    ts = filled.get(key, set())
    gx, gy = grid
    heat = [[0] * gx for _ in range(gy)]
    for t, idx, x1, y1, x2, y2 in det_items:
        p = eff[idx]
        if p.get("key") == key and p["state"] in ("named", "confirmed"):
            cx, fy = (x1 + x2) / 2, y2
            heat[min(gy - 1, max(0, int(fy * gy)))][min(gx - 1, max(0, int(cx * gx)))] += 1
    pieces = [p for p in eff if p.get("key") == key and p["state"] in ("named", "confirmed")]
    pieces.sort(key=lambda p: -p["n"])
    # open pieces whose best suggestion is this number on this team: "might be this player, needs you"
    team, number = key.split("#")
    maybe = []
    for p in eff:
        if p["state"] != "open" or p["n"] < MIN_QUEUE_N or p["team"] not in (team, "unk", "none"):
            continue
        sug = suggestion(p, roster or {team: [number]})
        if sug["number"] == number:
            maybe.append({"start": p["startSec"], "end": p["endSec"]})
    return {
        "maybe": maybe,
        "key": key, "seconds": round(len(ts) / DET_HZ, 1), "shifts": len(_runs(raw.get(key, set()))),
        "presence": [{"start": round(s / DET_HZ, 1), "end": round((e + 1) / DET_HZ, 1)} for s, e in _runs(ts, gap=1)],
        "heat": heat, "pieces": pieces[:6],
        "confirmedSeconds": round(sum(p["n"] for p in pieces if p["state"] == "confirmed") / DET_HZ, 1),
        "namedSeconds": round(sum(p["n"] for p in pieces if p["state"] == "named") / DET_HZ, 1),
    }


def unlisted_numbers(eff, roster, limit=12):
    """Numbers the reader saw that are not on the roster for the piece's team."""
    counts = Counter()
    pieces = defaultdict(int)
    for p in eff:
        if p["state"] == "nonplayer":
            continue
        ok = roster_numbers(roster, p["team"])
        for n, c in p["readCounts"].items():
            if n not in ok:
                counts[(p["team"], n)] += c
                pieces[(p["team"], n)] += 1
    listed_anywhere = set().union(*[set(v) for v in roster.values()]) if roster else set()
    return [{"team": t, "number": n, "reads": c, "pieces": pieces[(t, n)], "elsewhere": n in listed_anywhere}
            for (t, n), c in counts.most_common(limit)]


POINTS = {"made2": 2, "made3": 3, "made1": 1}


def event_stats(events):
    c = Counter(e["type"] for e in events)
    return {
        "points": sum(POINTS.get(t, 0) * n for t, n in c.items()),
        "made": c["made2"] + c["made3"] + c["made1"], "missed": c["missed"],
        "assists": c["assist"], "rebounds": c["rebound"], "steals": c["steal"],
        "turnovers": c["turnover"], "fouls": c["foul"], "total": len(events),
    }
