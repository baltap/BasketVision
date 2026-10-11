"""Run EasyOCR (digits only) over every crop in crops.csv. Usage: ocr_all.py CROPS_CSV OUT_CSV"""
import csv, re, sys, time
import easyocr
crops_csv, out_csv = sys.argv[1:3]
rows = list(csv.DictReader(open(crops_csv)))
reader = easyocr.Reader(["en"], gpu=True, verbose=False)
t0 = time.time(); out = []
for i, r in enumerate(rows):
    res = reader.readtext(r["path"], allowlist="0123456789", detail=1, text_threshold=0.5, low_text=0.3, width_ths=0.7)
    reads = [(t.strip(), float(c)) for _, t, c in res if re.fullmatch(r"\d{1,2}", t.strip())]
    reads.sort(key=lambda x: -x[1])
    top, conf = reads[0] if reads else ("", 0.0)
    out.append((r["track_id"], r["frame"], r["path"], top, f"{conf:.3f}", r["box_h"]))
    if (i + 1) % 200 == 0:
        print(f"{i + 1}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "path", "text", "conf", "box_h"]); w.writerows(out)
print("done", len(out), f"{time.time() - t0:.0f}s")
