"""Sheet of random VLM-only reads (EasyOCR found nothing) with the VLM's answer overlaid."""
import csv, random, sys
import cv2, numpy as np
P = sys.argv[1]
ocr = {(r["track_id"], r["frame"]): (r["text"] if r["text"] and float(r["conf"]) >= 0.5 else "") for r in csv.DictReader(open(f"{P}/ocr_reads.csv"))}
vl = [r for r in csv.DictReader(open(f"{P}/vlm_reads.csv")) if r["text"] and not ocr[(r["track_id"], r["frame"])]]
random.Random(5).shuffle(vl); vl = vl[:36]
cw, chh, cols = 240, 220, 6; tiles = []
for i, r in enumerate(vl):
    im = cv2.imread(r["path"]); h, w = im.shape[:2]
    s = min((cw - 6) / w, (chh - 26) / h)
    im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    t = np.full((chh, cw, 3), 40, np.uint8); t[22:22 + im.shape[0], 3:3 + im.shape[1]] = im
    cv2.putText(t, f"#{i} VLM={r['text']}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
    tiles.append(t)
sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, 36, cols)])
cv2.imwrite(f"{P}/vlm_only_check.jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 90]); print(len(vl), "tiles")
