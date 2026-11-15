"""Runs ON KAGGLE (free GPU). Makes full songs with vocals using the open-source ACE-Step 1.5 model
(MIT licence: free, also for commercial use, no watermark).
The GitHub workflow embeds two variables above this text: JOB (job.json) and GEN (gen_song.py).
Output: /kaggle/working/song_N.flac + song.json"""
import os, subprocess, sys, time

ACE = "/tmp/ace"                                         # not in /kaggle/working: that folder is the output
SHA = "ca1e85fe9430179831e6bc6be790c332190a3866"         # ACE-Step-1.5, pinned so a run today = a run next month
ENV = dict(os.environ, UV_CACHE_DIR="/tmp/uv-cache", HF_HOME="/tmp/hf", ACESTEP_CHECKPOINTS_DIR=f"{ACE}/checkpoints",
           PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True", TOKENIZERS_PARALLELISM="false")


def sh(cmd, cwd=None):
    t = time.time()
    print("$", cmd, flush=True)
    r = subprocess.run(cmd, shell=True, cwd=cwd, env=ENV)
    if r.returncode:
        sys.exit(f"Error: step failed ({r.returncode}): {cmd}")
    print(f"step done in {time.time() - t:.0f}s", flush=True)


gpu = subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True,
                     capture_output=True, text=True).stdout.strip()
print("GPU:", gpu or "none", flush=True)
if not gpu:
    sys.exit("Error: Kaggle gave no GPU (weekly GPU quota used up, or the phone number is not verified)")
if "P100" in gpu:
    sys.exit("Error: Kaggle gave a P100 GPU, which is too old for this model. Run it again to get a T4.")

sh(f"{sys.executable} -m pip install -q uv")
sh(f"rm -rf {ACE} && git init -q {ACE} && git -C {ACE} remote add origin https://github.com/ace-step/ACE-Step-1.5 "
   f"&& git -C {ACE} fetch -q --depth 1 origin {SHA} && git -C {ACE} checkout -q FETCH_HEAD")
sh(f"{sys.executable} -m uv sync --no-dev", cwd=ACE)     # ACE-Step's own Python + exact package versions
open(f"{ACE}/job.json", "w").write(JOB)                  # noqa: F821 (embedded by kaggle_job.py)
open(f"{ACE}/gen_song.py", "w").write(GEN)               # noqa: F821
sh(f"{sys.executable} -m uv run --no-dev python gen_song.py job.json /kaggle/working", cwd=ACE)
print("ALL DONE", flush=True)
