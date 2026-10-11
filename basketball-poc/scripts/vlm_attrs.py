"""Age group + top colour per body crop with Qwen2.5-VL (mlx).
Usage: vlm_attrs.py BODY_CSV OUT_CSV [--only TID,TID,...]"""
import csv, os, re, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent.parent
os.environ["HF_HOME"] = str(here / "hf")
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
model, processor = load(MODEL); config = load_config(MODEL)
Q = ("This is a photo of one person at a youth basketball game. "
     "Answer with exactly two words in the format: AGE COLOR. "
     "AGE is CHILD (a young player) or ADULT (a grown-up such as a coach, referee, parent or spectator). "
     "COLOR is the main colour of the person's top: WHITE (white or cream), DARK (black, navy, dark green or dark grey), "
     "ORANGE (orange, red or pink), or OTHER. "
     "Example answer: CHILD WHITE")
rows = list(csv.DictReader(open(sys.argv[1])))
if "--only" in sys.argv:
    only = {int(x) for x in sys.argv[sys.argv.index("--only") + 1].split(",")}
    rows = [r for r in rows if int(r["track_id"]) in only]
t0 = time.time(); out = []
for i, r in enumerate(rows):
    prompt = apply_chat_template(processor, config, Q, num_images=1)
    o = generate(model, processor, prompt, image=[r["path"]], max_tokens=8, temperature=0.0, verbose=False)
    s = str(getattr(o, "text", o)).strip().upper()
    role = next((x for x in ("CHILD", "ADULT") if x in s), "")
    col = next((x for x in ("WHITE", "DARK", "ORANGE", "OTHER") if x in s), "")
    out.append((r["track_id"], r["frame"], role, col, s.replace("\n", " ")))
    if (i + 1) % 200 == 0: print(f"{i + 1}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
with open(sys.argv[2], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["track_id", "frame", "age", "color", "raw"]); w.writerows(out)
print("done", len(out), f"{time.time() - t0:.0f}s")
