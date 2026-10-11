"""Build a labelled contact sheet from crops.csv. Usage: montage.py CROPS_CSV OUT_JPG N [seed] [min_h] [max_h]"""
import csv, sys, random
import cv2, numpy as np
csv_path, out, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
min_h = float(sys.argv[5]) if len(sys.argv) > 5 else 0
max_h = float(sys.argv[6]) if len(sys.argv) > 6 else 1e9
rows = [r for r in csv.DictReader(open(csv_path)) if min_h <= float(r["box_h"]) <= max_h]
random.Random(seed).shuffle(rows)
rows = rows[:n]
cell_w, cell_h, cols = 240, 220, 6
tiles = []
for i, r in enumerate(rows):
    im = cv2.imread(r["path"])
    h, w = im.shape[:2]
    s = min((cell_w - 6) / w, (cell_h - 26) / h)
    im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    t = np.full((cell_h, cell_w, 3), 40, np.uint8)
    t[22:22 + im.shape[0], 3:3 + im.shape[1]] = im
    cv2.putText(t, f"#{i} t{r['track_id']} h{float(r['box_h']):.0f}", (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    tiles.append(t)
while len(tiles) % cols: tiles.append(np.full((cell_h, cell_w, 3), 40, np.uint8))
sheet = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
cv2.imwrite(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
print(sheet.shape, len(rows))
with open(out.replace(".jpg", ".txt"), "w") as f:
    for i, r in enumerate(rows): f.write(f"{i}\t{r['path']}\n")
