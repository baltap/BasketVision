"""Run the roster-constrained VLM prompt over every crop. Usage: vlm_all.py CROPS_CSV OUT_CSV"""
import csv, os, re, sys, time
from pathlib import Path
crops_csv, out_csv = sys.argv[1:3]
os.environ["HF_HOME"] = str(Path(crops_csv).resolve().parent.parent / "hf")
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
model, processor = load(MODEL); config = load_config(MODEL)
ROSTER = [4, 6, 7, 8, 9, 11, 15, 20, 21, 22, 23, 31, 34, 40, 99]
if len(sys.argv) > 3:   # roster_json: {"light": [...], "dark": [...]} -> union goes into the prompt
    import json
    _r = json.load(open(sys.argv[3]))
    ROSTER = sorted({int(n) for v in _r.values() for n in v})
Q = ("This is a cropped photo of a basketball player in a youth game. The possible jersey numbers are: "
     + ", ".join(map(str, ROSTER)) + ". If one of these numbers is clearly readable on the player's shirt "
     "(front or back), reply with only that number. If the number is not clearly readable, reply NONE. Do not guess.")
rows = list(csv.DictReader(open(crops_csv)))
t0 = time.time(); out = []
for i, r in enumerate(rows):
    prompt = apply_chat_template(processor, config, Q, num_images=1)
    o = generate(model, processor, prompt, image=[r["path"]], max_tokens=8, temperature=0.0, verbose=False)
    s = str(getattr(o, "text", o)).strip()
    m = re.search(r"\d{1,2}", s)
    out.append((r["track_id"], r["frame"], r["path"], m.group(0) if m and "NONE" not in s.upper() else "", r["box_h"]))
    if (i + 1) % 200 == 0: print(f"{i + 1}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
with open(out_csv, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "path", "text", "box_h"]); w.writerows(out)
print("done", len(out), f"{time.time() - t0:.0f}s")
