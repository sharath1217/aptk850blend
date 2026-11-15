"""Music creator - the part that runs inside ACE-Step's own Python environment (on Kaggle's GPU).

  python gen_song.py <job.json> <out_dir>      (run from the ACE-Step-1.5 folder)

job.json: {"prompt", "lyrics", "language", "instrumental", "duration", "quality", "songs"}
* No lyrics given -> ACE-Step's own language model writes the lyrics, style, tempo and key from the prompt.
* Lyrics given    -> they are sung as written, the prompt is the style.
Writes <out>/song_N.flac (one per variation) and <out>/song.json (title info, lyrics, tempo, key)."""
import json, os, shutil, sys, time

job = json.load(open(sys.argv[1]))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
ROOT = os.getcwd()
log = lambda *a: print(*a, flush=True)

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music, create_sample

# fast = turbo model, 8 steps (seconds per song) / high = SFT model, 50 steps (cleaner sound, a few minutes)
high = job.get("quality") == "high"
model = "acestep-v15-sft" if high else "acestep-v15-turbo"

t = time.time()
dit, llm = AceStepHandler(), LLMHandler()
status, ok = dit.initialize_service(project_root=ROOT, config_path=model, device="cuda", offload_to_cpu=True)
if not ok:
    sys.exit(f"Error: music model failed to load: {status}")
status, ok = llm.initialize(checkpoint_dir=os.path.join(ROOT, "checkpoints"), lm_model_path="acestep-5Hz-lm-1.7B",
                            backend="pt", device="cuda", offload_to_cpu=True)
if not ok:
    sys.exit(f"Error: song-writer model failed to load: {status}")
log(f"models loaded, done in {time.time() - t:.0f}s")

lang = (job.get("language") or "unknown").strip().lower()
instrumental = bool(job.get("instrumental"))
caption, lyrics = job["prompt"].strip(), (job.get("lyrics") or "").strip()
bpm, key, timesig, duration, planned = None, "", "", -1.0, False

if not lyrics:  # let the model plan the whole song from the one-line idea
    s = create_sample(llm_handler=llm, query=caption, instrumental=instrumental,
                      vocal_language=None if lang == "unknown" else lang)
    if s.success:
        caption, lyrics = s.caption or caption, s.lyrics or ""
        bpm, key, timesig = s.bpm, s.keyscale or "", s.timesignature or ""
        duration = float(s.duration or -1)
        lang = s.language or lang
        planned = True
    else:
        log("song plan failed, continuing with the prompt only:", s.error or s.status_message)
if instrumental:
    lyrics = "[Instrumental]"

want = float(job.get("duration") or 0)
if want > 0:
    duration = want
duration = min(duration, 300.0)

params = GenerationParams(
    task_type="text2music", caption=caption, lyrics=lyrics, instrumental=instrumental,
    vocal_language=lang, bpm=bpm, keyscale=key, timesignature=timesig, duration=duration,
    inference_steps=50 if high else 8, guidance_scale=7.0, shift=3.0,
    thinking=True, use_cot_metas=not planned, use_cot_caption=not planned, use_cot_language=not planned,
    use_cot_lyrics=False)
config = GenerationConfig(batch_size=max(1, min(int(job.get("songs") or 2), 4)), use_random_seed=True,
                          audio_format="flac")
t = time.time()
result = generate_music(dit, llm, params, config, save_dir=os.path.join(out, "raw"))
if not result.success:
    sys.exit(f"Error: generation failed: {result.error or result.status_message}")

seeds = []
for i, audio in enumerate(result.audios, 1):
    shutil.copy(audio["path"], os.path.join(out, f"song_{i}.flac"))
    seeds.append(audio.get("params", {}).get("seed"))
shutil.rmtree(os.path.join(out, "raw"), ignore_errors=True)
json.dump({"prompt": job["prompt"], "style": caption, "lyrics": lyrics, "language": lang, "bpm": bpm, "key": key,
           "duration": duration, "model": model, "seeds": seeds, "songs": len(result.audios)},
          open(os.path.join(out, "song.json"), "w"), ensure_ascii=False, indent=1)
log(f"{len(result.audios)} song(s) done in {time.time() - t:.0f}s")
