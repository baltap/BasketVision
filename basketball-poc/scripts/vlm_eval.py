"""Head-to-head on the 60 hand-labelled crops: Qwen2.5-VL-7B (mlx) vs EasyOCR digits.
Usage: vlm_eval.py PROBE_DIR"""
import json, os, re, sys, time
from pathlib import Path
os.environ["HF_HOME"] = str(Path(sys.argv[1]).parent / "hf")
probe = Path(sys.argv[1])
paths = {int(i): p for i, p in (l.rstrip("\n").split("\t") for l in open(probe / "eval_map.txt"))}
lab = json.load(open(probe / "labels.json"))
truth = {int(k): v for k, v in {**lab["clear"], **lab["medium"]}.items()}
none = set(lab["none"]); unclear = set(lab["unclear"])

from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
import easyocr

MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
t0 = time.time(); model, processor = load(MODEL); config = load_config(MODEL)
print(f"model loaded in {time.time() - t0:.0f}s")
QUESTION = ("This is a cropped photo of a basketball player in a youth game. "
            "Read the jersey number printed on the player's shirt (front or back). "
            "Reply with only the digits of the number, or NONE if no number is clearly readable.")
def vlm(path):
    prompt = apply_chat_template(processor, config, QUESTION, num_images=1)
    out = generate(model, processor, prompt, image=[path], max_tokens=8, temperature=0.0, verbose=False)
    text = getattr(out, "text", out)
    return str(text).strip()

reader = easyocr.Reader(["en"], gpu=True, verbose=False)
def eocr(path):
    res = reader.readtext(path, allowlist="0123456789", detail=1, text_threshold=0.5, low_text=0.3, width_ths=0.7)
    r = sorted([(t.strip(), float(c)) for _, t, c in res if re.fullmatch(r"\d{1,2}", t.strip())], key=lambda x: -x[1])
    return r[0][0] if r and r[0][1] >= 0.5 else ""

def norm(s):
    m = re.search(r"\d{1,2}", s)
    return m.group(0) if m and "NONE" not in s.upper() else ""

rows = []; tv = 0
for i in range(60):
    t1 = time.time(); v = norm(vlm(paths[i])); tv += time.time() - t1
    e = eocr(paths[i])
    kind = "clear" if str(i) in lab["clear"] else "medium" if str(i) in lab["medium"] else "unclear" if i in unclear else "none"
    rows.append((i, kind, truth.get(i, ""), v, e))
print(f"VLM time per crop: {tv / 60:.1f}s")
print(f"{'#':>3} {'kind':<8} {'truth':<6} {'VLM':<6} {'EasyOCR':<8}")
for r in rows: print(f"{r[0]:>3} {r[1]:<8} {r[2]:<6} {r[3]:<6} {r[4]:<8}")

def score(idx):
    pos = [r for r in rows if r[1] in ("clear", "medium")]
    neg = [r for r in rows if r[1] == "none"]
    unc = [r for r in rows if r[1] == "unclear"]
    exact = sum(1 for r in pos if r[idx] == r[2])
    wrong_pos = sum(1 for r in pos if r[idx] and r[idx] != r[2])
    fp = sum(1 for r in neg if r[idx])
    unc_read = sum(1 for r in unc if r[idx])
    return exact, len(pos), wrong_pos, fp, len(neg), unc_read, len(unc)
for name, idx in (("Qwen2.5-VL-7B", 3), ("EasyOCR", 4)):
    ex, np_, wp, fp, nn, ur, nu = score(idx)
    print(f"{name:<14} exact {ex}/{np_} | wrong number on readable crops {wp} | false read on no-number crops {fp}/{nn} | read something on unclear crops {ur}/{nu}")
json.dump(rows, open(probe / "eval_results.json", "w"))
