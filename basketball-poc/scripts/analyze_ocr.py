"""Summarise OCR reads and build a precision-check sheet. Usage: analyze_ocr.py OCR_CSV OUT_SHEET_JPG"""
import csv, random, sys
from collections import defaultdict, Counter
import cv2, numpy as np
rows = list(csv.DictReader(open(sys.argv[1])))
N = len(rows)
for thr in (0.0, 0.3, 0.5, 0.8):
    n = sum(1 for r in rows if r["text"] and float(r["conf"]) >= max(thr, 1e-9))
    print(f"crops with a 1-2 digit read, conf >= {thr}: {n}/{N} ({100 * n / N:.0f}%)")

tr = defaultdict(list)
for r in rows: tr[int(r["track_id"])].append(r)
voted = {}
for t, lst in tr.items():
    w = defaultdict(float); c = Counter()
    for r in lst:
        if r["text"] and float(r["conf"]) >= 0.3:
            w[r["text"]] += float(r["conf"]); c[r["text"]] += 1
    if w:
        best = max(w, key=w.get)
        voted[t] = (best, c[best], w[best] / sum(w.values()), len(lst))
print(f"\ntracklets: {len(tr)} | with any read (conf>=0.3): {len(voted)} "
      f"| with >=2 agreeing crops and >=60% of vote weight: "
      f"{sum(1 for b, n, s, L in voted.values() if n >= 2 and s >= 0.6)}")
nums = Counter(b for b, n, s, L in voted.values() if n >= 2 and s >= 0.6)
print("numbers from confident tracklets (number: tracklets):", dict(nums.most_common(20)))
allnums = Counter(r["text"] for r in rows if r["text"] and float(r["conf"]) >= 0.5)
print("all crop reads conf>=0.5 (number: crops):", dict(allnums.most_common(20)))

# precision-check sheet: random crops with a read at conf >= 0.5
cands = [r for r in rows if r["text"] and float(r["conf"]) >= 0.5]
random.Random(3).shuffle(cands); cands = cands[:36]
cw, chh, cols = 240, 220, 6; tiles = []
for i, r in enumerate(cands):
    im = cv2.imread(r["path"]); h, w = im.shape[:2]
    s = min((cw - 6) / w, (chh - 26) / h)
    im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    t = np.full((chh, cw, 3), 40, np.uint8); t[22:22 + im.shape[0], 3:3 + im.shape[1]] = im
    cv2.putText(t, f"#{i} t{r['track_id']} READ={r['text']} ({float(r['conf']):.2f})", (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    tiles.append(t)
while len(tiles) % cols: tiles.append(np.full((chh, cw, 3), 40, np.uint8))
sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
cv2.imwrite(sys.argv[2], sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]); print("sheet", sheet.shape, len(cands))
