"""Short film - step 3 (editor). Frames + voices -> finished film and a 60 s vertical Short.

  python studio/film/assemble.py <assets_dir> <frames_dir> <out_dir>

* dialogue placed at the exact frame of each line, a generated music bed (genre mood, no
  licensing worries) and ambience (rain, sea, wind, city) mixed under it
* opening title, burned-in subtitles, end credits, film grade (grain, vignette, letterbox)
* the Short: 1080x1920, blurred fill background, the film in the middle, hook caption on top,
  subtitles below - cut from the shots the writer picked
Writes <out>/film.mp4, <out>/short.mp4, <out>/subtitles.srt, <out>/script.txt, <out>/credits.txt."""
import json, shutil, subprocess, sys
from pathlib import Path

FPS = 24
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MUSIC = {  # chord (Hz) and pulse per genre: slow pads for drama, a driving pulse for action...
    "drama": ([110, 164.8, 220, 277.2], 0.07, 0.0),
    "action": ([55, 82.4, 110, 130.8], 0.06, 2.0),
    "scifi": ([65.4, 98, 130.8, 196, 311.1], 0.06, 0.25),
    "comedy": ([261.6, 329.6, 392, 523.3], 0.035, 3.0),
}


def run(*cmd):
    print(" ".join(map(str, cmd))[:400], flush=True); subprocess.run(list(map(str, cmd)), check=True)


def ts(sec):
    h, m = int(sec // 3600), int(sec % 3600 // 60)
    return f"{h:02d}:{m:02d}:{sec % 60:06.3f}".replace(".", ",")


def esc(t):
    return t.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


def main():
    assets, frames, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True); work = out / "work"; work.mkdir(exist_ok=True)
    st = json.load(open(assets / "story.json"))
    total = st["frames"] / FPS
    names = {k: c["name"] for k, c in st["cast"].items()}
    # fill any missing frame (a failed render job) with its neighbour so the edit never breaks
    last = None
    for g in range(st["frames"]):
        f = frames / f"f_{g:05d}.jpg"
        if f.exists():
            last = f
        elif last:
            shutil.copy(last, f)
    first = next(frames / f"f_{g:05d}.jpg" for g in range(st["frames"]) if (frames / f"f_{g:05d}.jpg").exists())
    for g in range(st["frames"]):
        f = frames / f"f_{g:05d}.jpg"
        if not f.exists():
            shutil.copy(first, f)

    # ---- subtitles
    lines = [l for s in st["shots"] for l in s["lines"]]
    srt = []
    for i, l in enumerate(lines, 1):
        a = l["frame"] / FPS; who = "" if l["speaker"] == "narrator" else names[l["speaker"]].upper() + ": "
        srt.append(f"{i}\n{ts(a)} --> {ts(a + l['len'] + 0.2)}\n{who}{l['text']}\n")
    (out / "subtitles.srt").write_text("\n".join(srt))

    # ---- audio: music bed + ambience + dialogue
    chord, vol, pulse = MUSIC.get(st.get("genre"), MUSIC["drama"])
    expr = "+".join(f"sin(2*PI*{f}*t)*(0.6+0.4*sin(2*PI*{0.05 + i * 0.03:.2f}*t))" for i, f in enumerate(chord))
    env = f"*(0.55+0.45*abs(sin(PI*{pulse}*t)))" if pulse else ""
    run("ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc=({expr})/{len(chord)}{env}:s=48000:d={total + 1}",
        "-af", f"lowpass=f=1800,aecho=0.8:0.7:120|240:0.3|0.2,volume={vol * 4},afade=t=in:d=4,afade=t=out:st={total - 5}:d=5",
        work / "music.wav")
    amb = []
    for s in st["shots"]:
        a, b = s["start"] / FPS, (s["start"] + s["frames"]) / FPS
        kind = "rain" if s["weather"] == "rain" else ("sea" if s["set"] == "coast" else
               ("city" if s["set"] == "city" else ("wind" if s["set"] in ("forest", "planet") or s["weather"] == "snow" else None)))
        if kind:
            amb.append((kind, a, b))
    noise = {"rain": ("pink:a=0.5", "highpass=f=900"), "sea": ("brown:a=0.6", "lowpass=f=500,tremolo=f=0.12:d=0.7"),
             "city": ("brown:a=0.4", "lowpass=f=300"), "wind": ("pink:a=0.3", "lowpass=f=700,tremolo=f=0.2:d=0.6")}
    amb_in, amb_mix = [], []
    for k, (src, fx) in noise.items():
        spans = [(a, b) for kk, a, b in amb if kk == k]
        if spans:
            on = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in spans)
            amb_in += ["-f", "lavfi", "-i", f"anoisesrc=c={src}:d={total + 1}:r=48000"]
            amb_mix.append(f"{fx},volume='0.35*({on})':eval=frame")
    inputs = ["-i", work / "music.wav"] + amb_in
    filt, labels = [], ["[0:a]"]
    for i, f in enumerate(amb_mix, 1):
        filt.append(f"[{i}:a]{f}[m{i}]"); labels.append(f"[m{i}]")
    base = len(amb_mix) + 1
    for j, l in enumerate(lines):
        inputs += ["-i", assets / "lines" / l["file"]]
        d = int(l["frame"] / FPS * 1000)
        filt.append(f"[{base + j}:a]aresample=48000,volume=1.6,adelay={d}|{d}[v{j}]"); labels.append(f"[v{j}]")
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,alimiter=limit=0.95[a]")
    (work / "mix.txt").write_text(";\n".join(filt))
    run("ffmpeg", "-y", *inputs, "-filter_complex_script", work / "mix.txt", "-map", "[a]", "-t", total, work / "mix.wav")

    # ---- picture: grade, letterbox, title, subtitles, credits
    title, credits_t = esc(st["title"]), total - 7
    cast = "   ".join(f"{c['name']}" for c in st["cast"].values())
    credit_lines = [st["title"], "", "Starring " + cast, "Story, voices and animation made by AI",
                    "Rendered in Blender", "GetYr Studio"]
    if st.get("credits_model"):
        credit_lines.append(st["credits_model"])
    (out / "credits.txt").write_text("\n".join(credit_lines) + "\n")
    shutil.copy(assets / "script.txt", out / "script.txt")
    vf = ("scale=1920:1080:flags=lanczos,eq=contrast=1.04:saturation=1.05,vignette=PI/5,noise=alls=5:allf=t,"
          "drawbox=y=0:w=iw:h=ih*0.07:color=black:t=fill,drawbox=y=ih*0.93:w=iw:h=ih*0.07:color=black:t=fill,"
          f"drawtext=fontfile={FONT}:text='{title}':fontsize=84:fontcolor=white:x=(w-tw)/2:y=(h-th)/2:"
          f"alpha='if(lt(t,0.6),t/0.6,if(lt(t,3.2),1,max(0,(4-t)/0.8)))':enable='lt(t,4)',"
          f"drawtext=fontfile={FONT}:text='GetYr Studio presents':fontsize=34:fontcolor=white@0.8:x=(w-tw)/2:y=h/2+70:enable='lt(t,3.6)',"
          f"subtitles={out / 'subtitles.srt'}:force_style='FontName=DejaVu Sans,FontSize=20,Outline=2,MarginV=60',"
          f"drawbox=enable='gte(t,{credits_t})':color=black@0.6:t=fill,"
          + ",".join(f"drawtext=fontfile={FONT}:text='{esc(t)}':fontsize={60 if k == 0 else 32}:fontcolor=white:"
                     f"x=(w-tw)/2:y=h*0.3+{k * 62}:enable='gte(t,{credits_t + 0.4 * k})'"
                     for k, t in enumerate(credit_lines) if t)
          + f",fade=t=in:d=1,fade=t=out:st={total - 1.2}:d=1.2")
    run("ffmpeg", "-y", "-framerate", FPS, "-i", frames / "f_%05d.jpg", "-i", work / "mix.wav", "-vf", vf,
        "-c:v", "libx264", "-preset", "slow", "-crf", 18, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", out / "film.mp4")

    # ---- the Short (vertical 1080x1920, <= 60 s)
    sh = st["short"]; a, b = sh["start"] / FPS, sh["end"] / FPS; d = b - a
    sub_short = [x for x in lines if a <= x["frame"] / FPS < b]
    srt2 = [f"{i}\n{ts(x['frame'] / FPS - a)} --> {ts(min(d, x['frame'] / FPS - a + x['len'] + 0.2))}\n{x['text']}\n"
            for i, x in enumerate(sub_short, 1)]
    (work / "short.srt").write_text("\n".join(srt2))
    hook = esc(sh.get("hook") or st["title"])
    vf2 = ("[0:v]split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,eq=brightness=-0.15[bg];"
           "[b]scale=1080:-2,eq=contrast=1.04:saturation=1.08[fg];[bg][fg]overlay=0:(H-h)/2,"
           f"drawtext=fontfile={FONT}:text='{hook}':fontsize=64:fontcolor=white:box=1:boxcolor=black@0.45:boxborderw=20:x=(w-tw)/2:y=300,"
           f"drawtext=fontfile={FONT}:text='{title}':fontsize=40:fontcolor=white@0.85:x=(w-tw)/2:y=h-380,"
           f"drawtext=fontfile={FONT}:text='Full film on GetYr Studio':fontsize=34:fontcolor=yellow:x=(w-tw)/2:y=h-310:enable='gte(t,{d - 6})',"
           f"subtitles={work / 'short.srt'}:original_size=1080x1920:force_style='FontName=DejaVu Sans,FontSize=16,Outline=2,Alignment=2,MarginV=560',"
           f"fade=t=in:d=0.5,fade=t=out:st={d - 0.8}:d=0.8[v]")
    run("ffmpeg", "-y", "-framerate", FPS, "-start_number", sh["start"], "-t", d, "-i", frames / "f_%05d.jpg",
        "-ss", a, "-t", d, "-i", work / "mix.wav", "-filter_complex", vf2, "-map", "[v]", "-map", "1:a",
        "-af", f"afade=t=in:d=0.5,afade=t=out:st={d - 0.8}:d=0.8",
        "-c:v", "libx264", "-preset", "slow", "-crf", 19, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", out / "short.mp4")
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
