"""Two labelling sheets of 30 random crops each, global indices 0..59 (+ mapping txt).
Usage: eval_sheets.py CROPS_CSV OUT_PREFIX SEED"""
import csv, random, sys
import cv2, numpy as np
rows = list(csv.DictReader(open(sys.argv[1])))
random.Random(int(sys.argv[3])).shuffle(rows)
rows = rows[:60]
cw, chh, cols = 240, 230, 6
def tile(i, r):
    im = cv2.imread(r["path"]); h, w = im.shape[:2]
    s = min((cw - 6) / w, (chh - 26) / h)
    im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    t = np.full((chh, cw, 3), 40, np.uint8); t[22:22 + im.shape[0], 3:3 + im.shape[1]] = im
    cv2.putText(t, f"#{i}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
    return t
for part in range(2):
    tiles = [tile(i, rows[i]) for i in range(part * 30, part * 30 + 30)]
    sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, 30, cols)])
    cv2.imwrite(f"{sys.argv[2]}_{part}.jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
with open(f"{sys.argv[2]}_map.txt", "w") as f:
    for i, r in enumerate(rows): f.write(f"{i}\t{r['path']}\n")
print("sheets written", len(rows))
