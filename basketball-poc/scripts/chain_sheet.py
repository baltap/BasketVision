"""Contact sheet: one row per stitched chain, one crop per member tracklet.
Usage: chain_sheet.py CHAINS_CSV CROPS_CSV OUT_JPG ROW_START ROW_COUNT"""
import csv, sys
from collections import defaultdict
import cv2, numpy as np
chains_csv, crops_csv, out, r0, rn = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
members = defaultdict(list); meta = {}
for r in csv.DictReader(open(chains_csv)):
    members[int(r["chain_id"])].append((float(r["start_s"]), int(r["track_id"]), int(r["n_det"])))
    meta[int(r["chain_id"])] = r["team"]
crops = defaultdict(list)
for r in csv.DictReader(open(crops_csv)):
    crops[int(r["track_id"])].append(r)
multi = [(c, sorted(m)) for c, m in members.items() if len(m) >= 2]
multi.sort(key=lambda cm: -sum(n for _, _, n in cm[1]))
multi = multi[r0:r0 + rn]
cw, chh, maxc = 150, 170, 8
rows = []
for cid, m in multi:
    tiles = []
    for st, tid, n in m[:maxc]:
        lst = sorted(crops.get(tid, []), key=lambda r: float(r["box_h"]))
        t = np.full((chh, cw, 3), 35, np.uint8)
        if lst:
            r = lst[len(lst) // 2]
            im = cv2.imread(r["path"]); h, w = im.shape[:2]
            s = min((cw - 4) / w, (chh - 18) / h)
            im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
            t[16:16 + im.shape[0], 2:2 + im.shape[1]] = im
        cv2.putText(t, f"t{tid} @{st:.0f}s", (3, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        tiles.append(t)
    while len(tiles) < maxc: tiles.append(np.full((chh, cw, 3), 20, np.uint8))
    lab = np.full((chh, 70, 3), 60, np.uint8)
    cv2.putText(lab, f"chain", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    cv2.putText(lab, f"{cid}", (4, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(lab, meta[cid], (4, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 255, 200), 1)
    cv2.putText(lab, f"{len(m)} parts", (4, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 255), 1)
    rows.append(np.hstack([lab] + tiles))
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88]); print(len(rows), "rows")
