"""Test EasyOCR (digits only) on crops whose number I labelled by eye.
Usage: ocr_test.py PROBE_DIR"""
import sys, time, re
from pathlib import Path
import easyocr

probe = Path(sys.argv[1])
def load(name):
    m = {}
    for line in open(probe / name):
        i, p = line.rstrip("\n").split("\t"); m[int(i)] = p
    return m
A, B = load("sheet_a.txt"), load("sheet_b.txt")
# labels read by eye from the contact sheets (clearly legible only)
POS = {A[2]: "6", A[8]: "20", A[14]: "7", A[15]: "6", A[20]: "40",
       B[8]: "31", B[9]: "8", B[12]: "40", B[14]: "21", B[19]: "8", B[20]: "6", B[30]: "40", B[11]: "22"}
# crops where I see no jersey number (referees, heads, floor, side-on)
NEG = [A[i] for i in (0, 1, 4, 5, 9, 11, 21)] + [B[i] for i in (3, 5, 25, 29, 31, 32, 34, 35)]

try:
    reader = easyocr.Reader(["en"], gpu=True, verbose=False)
except Exception as e:
    print("gpu init failed, using cpu:", e)
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)

def read(path):
    res = reader.readtext(path, allowlist="0123456789", detail=1, text_threshold=0.5, low_text=0.3, width_ths=0.7)
    out = [(t.strip(), float(c)) for _, t, c in res if re.fullmatch(r"\d{1,2}", t.strip())]
    return sorted(out, key=lambda x: -x[1])

t0 = time.time()
ok_top = ok_any = 0
print("POSITIVES (label -> reads)")
for p, lab in POS.items():
    r = read(p)
    top = r[0][0] if r else None
    ok_top += top == lab
    ok_any += any(t == lab for t, _ in r)
    print(f"  {Path(p).name:<18} label={lab:<3} top={top!s:<5} all={[(t, round(c, 2)) for t, c in r][:4]}")
print(f"  exact top-1: {ok_top}/{len(POS)}   label found among reads: {ok_any}/{len(POS)}")
fp = 0
print("NEGATIVES (no number visible)")
for p in NEG:
    r = read(p)
    fp += bool(r)
    print(f"  {Path(p).name:<18} reads={[(t, round(c, 2)) for t, c in r][:4]}")
print(f"  crops with a false number: {fp}/{len(NEG)}")
print(f"time: {time.time() - t0:.0f}s for {len(POS) + len(NEG)} crops")
