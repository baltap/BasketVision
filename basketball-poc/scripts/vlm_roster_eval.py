"""Prompt variants on the 60 labelled crops. Usage: vlm_roster_eval.py PROBE_DIR"""
import json, os, re, sys, time
from pathlib import Path
probe = Path(sys.argv[1]); os.environ["HF_HOME"] = str(probe.parent / "hf")
paths = {int(i): p for i, p in (l.rstrip("\n").split("\t") for l in open(probe / "eval_map.txt"))}
lab = json.load(open(probe / "labels.json"))
truth = {int(k): v for k, v in {**lab["clear"], **lab["medium"]}.items()}
none = set(lab["none"]); unclear = set(lab["unclear"])
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config
MODEL = "mlx-community/Qwen2.5-VL-7B-Instruct-4bit"
model, processor = load(MODEL); config = load_config(MODEL)
# simulated roster: the numbers seen on court plus decoys that never appeared
ROSTER = [4, 6, 7, 8, 9, 11, 15, 20, 21, 22, 23, 31, 34, 40, 99]
LIST = ", ".join(str(n) for n in ROSTER)
PROMPTS = {
 "open": ("This is a cropped photo of a basketball player in a youth game. Read the jersey number printed on the player's "
          "shirt (front or back). Reply with only the digits of the number, or NONE if no number is clearly readable."),
 "roster": (f"This is a cropped photo of a basketball player in a youth game. The possible jersey numbers are: {LIST}. "
            "If one of these numbers is clearly readable on the player's shirt (front or back), reply with only that number. "
            "If the number is not clearly readable, reply NONE. Do not guess."),
}
def ask(q, path):
    prompt = apply_chat_template(processor, config, q, num_images=1)
    out = generate(model, processor, prompt, image=[path], max_tokens=8, temperature=0.0, verbose=False)
    return str(getattr(out, "text", out)).strip()
def norm(s):
    m = re.search(r"\d{1,2}", s)
    return m.group(0) if m and "NONE" not in s.upper() else ""
res = {k: {} for k in PROMPTS}
for k, q in PROMPTS.items():
    for i in range(60): res[k][i] = norm(ask(q, paths[i]))
def score(r):
    pos = [i for i in truth]; ex = sum(1 for i in pos if r[i] == truth[i])
    wrong = sum(1 for i in pos if r[i] and r[i] != truth[i]); miss = sum(1 for i in pos if not r[i])
    fp = sum(1 for i in none if r[i]); unc = sum(1 for i in unclear if r[i])
    reads = ex + wrong + fp
    return ex, wrong, miss, fp, unc, reads
print(f"{'prompt':<8} {'exact/22':>9} {'wrong':>6} {'missed':>7} {'false/25':>9} {'unclear read/13':>16} {'precision':>10}")
for k in PROMPTS:
    ex, wrong, miss, fp, unc, reads = score(res[k])
    print(f"{k:<8} {ex:>6}/22 {wrong:>6} {miss:>7} {fp:>6}/25 {unc:>13}/13 {100 * ex / max(reads, 1):>9.0f}%")
from collections import Counter
print("most common reads, roster prompt:", Counter(v for v in res['roster'].values() if v).most_common(8))
print("most common reads, open prompt:  ", Counter(v for v in res['open'].values() if v).most_common(8))
print("roster-prompt mistakes:", {i: (truth.get(i, 'none' if i in none else 'unclear'), res['roster'][i]) for i in range(60)
      if res['roster'][i] and res['roster'][i] != truth.get(i)})
