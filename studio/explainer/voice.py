"""Voice every scene (free Edge TTS), time each scene to its narration, make a music bed.
  python voice.py <episode.json> <public_dir> <props_out.json>"""
import json, subprocess, sys, time
from pathlib import Path
ep_file, pub, props = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
ep = json.load(open(ep_file)); (pub / "audio").mkdir(parents=True, exist_ok=True)
FPS = 30
def dur(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True, check=True).stdout)
jobs = [(f"s{i}", s) for i, s in enumerate(ep["scenes"])] + [(f"sh{i}", s) for i, s in enumerate(ep.get("short_scenes", []))]
for key, s in jobs:
    i = key
    f = pub / "audio" / f"{key}.mp3"
    for attempt in range(8):
        v = ep.get("voice", "en-US-AndrewMultilingualNeural") if attempt < 5 else "en-US-GuyNeural"
        r = subprocess.run(["edge-tts", "--voice", v, f"--rate={ep.get('rate', '+4%')}", "--text", s["narration"], "--write-media", str(f)], capture_output=True, text=True)
        if r.returncode == 0 and f.exists() and f.stat().st_size > 2000:
            break
        print("voice retry", i, r.stderr[-150:]); time.sleep(3 * (attempt + 1))
    d = dur(f); s["audio"] = True; s["audio_key"] = key
    s["frames"] = int((d + (0.9 if s["type"] in ("title", "outro") else 0.3)) * FPS)
    print(f"scene {key:5s} {s['type']:9s} {d:5.1f}s")
total = sum(s["frames"] for s in ep["scenes"]) / FPS
json.dump({"ep": ep}, open(props, "w"))
json.dump({"ep": ep, "short": True}, open(props.replace(".json", "_short.json"), "w"))
# dark documentary music bed: slow minor chords over a low drone, with a long echo tail
chords = [[55.0, 82.41, 130.81], [49.0, 73.42, 116.54], [43.65, 65.41, 103.83], [41.2, 61.74, 98.0]]
expr = "+".join(f"0.25*sin(2*PI*{c[k]}*t)*(between(mod(t\\,32)\\,{8*j}\\,{8*j+8}))" for j, c in enumerate(chords) for k in range(3))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc=({expr})+0.12*sin(2*PI*36.7*t):s=48000:d={total + 2}",
                "-af", f"lowpass=f=900,aecho=0.8:0.85:400|900:0.35|0.25,volume=0.5,afade=t=in:d=4,afade=t=out:st={total - 4}:d=4",
                str(pub / "music.wav")], check=True)
print(f"total {total / 60:.1f} min")
