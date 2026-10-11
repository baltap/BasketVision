"""Compare EasyOCR vs VLM reads at crop and tracklet level. Usage: analyze_compare.py PROBE TRACKS_CSV"""
import csv, sys
from collections import Counter, defaultdict
P, TRACKS = sys.argv[1], sys.argv[2]
ndet = Counter(); 
for r in csv.DictReader(open(TRACKS)):
    if r["on_court"] == "1": ndet[int(r["track_id"])] += 1
def load(name, conf_min=None):
    d = {}
    for r in csv.DictReader(open(f"{P}/{name}")):
        t = r["text"]
        if conf_min is not None and t and float(r["conf"]) < conf_min: t = ""
        d[(int(r["track_id"]), int(r["frame"]))] = t
    return d
readers = {"EasyOCR (conf>=0.5)": load("ocr_reads.csv", 0.5), "Qwen2.5-VL roster prompt": load("vlm_reads.csv")}
tracks = sorted({k[0] for k in readers["EasyOCR (conf>=0.5)"]})
N = len(readers["EasyOCR (conf>=0.5)"])
total_det = sum(ndet[t] for t in tracks)
DECOYS = {"4", "9", "11", "15", "23", "34"}
print(f"crops: {N} | tracklets: {len(tracks)} | player detections in those tracklets: {total_det}\n")
summary = {}
for name, reads in readers.items():
    by = defaultdict(list)
    for (t, f), txt in reads.items():
        if txt: by[t].append(txt)
    n_reads = sum(len(v) for v in by.values())
    conf_tr, conflict = {}, []
    for t, lst in by.items():
        c = Counter(lst); top, n = c.most_common(1)[0]
        if n >= 2 and n / len(lst) >= 0.6: conf_tr[t] = top
        strong = [k for k, v in c.items() if v >= 2]
        if len(strong) >= 2: conflict.append((t, dict(c)))
    cov = sum(ndet[t] for t in conf_tr)
    nums = Counter(conf_tr.values())
    print(f"== {name}")
    print(f"  crops with a read: {n_reads}/{N} ({100 * n_reads / N:.0f}%)")
    print(f"  tracklets with any read: {len(by)}/{len(tracks)} | confident (>=2 agreeing, >=60% share): {len(conf_tr)}/{len(tracks)}")
    print(f"  share of player detections in confident tracklets: {100 * cov / total_det:.0f}%")
    print(f"  tracklets with >=2 different numbers each read >=2 times (likely ID swap inside tracklet): {len(conflict)}")
    print(f"  numbers among confident tracklets: {dict(nums.most_common())}")
    print(f"  decoy-number reads (4,9,11,15,23,34): {sum(1 for v in by.values() for x in v if x in DECOYS)} of {n_reads}")
    summary[name] = (by, conf_tr)
a, b = (readers[k] for k in readers)
both = [(k, a[k], b[k]) for k in a if a[k] and b[k]]
agree = sum(1 for _, x, y in both if x == y)
print(f"\ncrops read by BOTH: {len(both)} | agree: {agree} ({100 * agree / max(len(both), 1):.0f}%)")
only_e = sum(1 for k in a if a[k] and not b[k]); only_v = sum(1 for k in a if b[k] and not a[k])
print(f"read only by EasyOCR: {only_e} | read only by VLM: {only_v}")
ct_e, ct_v = summary["EasyOCR (conf>=0.5)"][1], summary["Qwen2.5-VL roster prompt"][1]
both_t = set(ct_e) & set(ct_v)
print(f"confident tracklets by both: {len(both_t)} | same number: {sum(1 for t in both_t if ct_e[t] == ct_v[t])}")
print(f"tracklets per confident number (VLM): {dict(Counter(ct_v.values()).most_common())}")
