"""Concatenate two reads CSVs. Usage: merge_reads.py A.csv B.csv OUT.csv"""
import csv, sys
rows = []
for p in sys.argv[1:3]:
    rows += list(csv.DictReader(open(p)))
with open(sys.argv[3], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "path", "text", "box_h"])
    for r in rows: w.writerow([r["track_id"], r["frame"], r["path"], r["text"], r["box_h"]])
print("merged", len(rows))
