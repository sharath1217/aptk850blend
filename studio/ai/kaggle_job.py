"""Send a Python script to Kaggle's free GPU, wait for it, download its output.
  python kaggle_job.py <slug> <script.py> <out_dir> [dataset-slug] [VAR=file ...]
VAR=file embeds a file's text into the script as a Python variable (e.g. SCENE=coast_scene.py)."""
import json, os, subprocess, sys, tempfile, time
slug, script, out = sys.argv[1], sys.argv[2], sys.argv[3]
dataset = sys.argv[4] if len(sys.argv) > 4 and "=" not in sys.argv[4] else ""
embeds = [a for a in sys.argv[4:] if "=" in a]
user = os.environ["KAGGLE_USERNAME"]
d = tempfile.mkdtemp()
code = "".join(f"{k} = {open(v).read()!r}\n" for k, v in (e.split("=", 1) for e in embeds)) + open(script).read()
open(f"{d}/run.py", "w").write(code)
json.dump({"id": f"{user}/{slug}", "title": slug, "code_file": "run.py", "language": "python",
           "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
           "dataset_sources": [f"{user}/{dataset}"] if dataset else [], "competition_sources": [], "kernel_sources": []},
          open(f"{d}/kernel-metadata.json", "w"))
subprocess.run(["kaggle", "kernels", "push", "-p", d], check=True)
time.sleep(60)
start = time.time()
while True:
    s = subprocess.run(["kaggle", "kernels", "status", f"{user}/{slug}"], capture_output=True, text=True).stdout.strip()
    print(time.strftime("%H:%M"), s.split("\n")[-1], flush=True)
    low = s.lower()
    if "complete" in low or "error" in low or "cancel" in low:
        break
    if time.time() - start > 12.5 * 3600:
        sys.exit("Kaggle job took too long")
    time.sleep(120)
os.makedirs(out, exist_ok=True)
subprocess.run(["kaggle", "kernels", "output", f"{user}/{slug}", "-p", out])
log = next((os.path.join(out, f) for f in os.listdir(out) if f.endswith(".log")), None)
if log:  # print the useful lines of the Kaggle log
    for line in open(log).read().split("\\n"):
        if any(w in line for w in ("GPU", "frame ", "render time", "car:", "sky:", "texture", "Error", "error", "done in", "ALL DONE")):
            print("  kaggle:", line[-220:])
if "complete" not in low:
    sys.exit("Kaggle job failed - see the log above")
