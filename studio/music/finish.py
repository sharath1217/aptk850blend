"""Music creator - last step (on GitHub). Turns what Kaggle made into things you can play and share.

  python studio/music/finish.py <kaggle_out_dir> <dist_dir> "<title>"

For every song_N.flac: an MP3 (320k, tagged with the title). For the first one also a 720p music video
(moving colours + the sound wave + the title) that plays anywhere. Plus lyrics.txt and summary.md."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

src, dist = Path(sys.argv[1]), Path(sys.argv[2])
info = json.load(open(src / "song.json"))
title = (sys.argv[3] if len(sys.argv) > 3 else "").strip()
if not title:   # no title given: the first words of the idea, without a dangling "about", "of the" ...
    words = re.sub(r"[,.;:!?].*", "", info["prompt"]).split()[:6]
    while len(words) > 1 and words[-1].lower() in ("a", "an", "the", "about", "of", "in", "on", "for", "with", "and", "to", "my"):
        words.pop()
    title = " ".join(words).title()
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "song"
dist.mkdir(parents=True, exist_ok=True)
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]
font = next((f for f in FONTS if os.path.exists(f)), None)


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


songs = sorted(src.glob("song_*.flac"))
if not songs:
    sys.exit("no songs came back from Kaggle")
mp3s = []
for i, flac in enumerate(songs, 1):
    mp3 = dist / (f"{slug}_{i}.mp3" if len(songs) > 1 else f"{slug}.mp3")
    ff("-i", str(flac), "-c:a", "libmp3lame", "-b:a", "320k", "-metadata", f"title={title}",
       "-metadata", "artist=GetYr Studio", "-metadata", f"comment={info['style'][:200]}", str(mp3))
    mp3s.append(mp3)

# music video for the first variation
tmp = Path(tempfile.mkdtemp())
(tmp / "title.txt").write_text(title[:48])
sub = " · ".join(x for x in [f"{info['bpm']} BPM" if info.get("bpm") else "", info.get("key") or "", "made with ACE-Step 1.5"] if x)
(tmp / "sub.txt").write_text(sub)
text = ""
if font and title.isascii():   # the bundled fonts only cover Latin letters; other scripts get a clean video without text
    text = (f",drawtext=fontfile={font}:textfile={tmp / 'title.txt'}:fontcolor=white:fontsize=60:x=(w-text_w)/2:y=170"
            f":shadowcolor=black@0.5:shadowx=2:shadowy=2"
            f",drawtext=fontfile={font}:textfile={tmp / 'sub.txt'}:fontcolor=white@0.8:fontsize=26:x=(w-text_w)/2:y=260")
video = dist / f"{slug}.mp4"
ff("-i", str(mp3s[0]), "-f", "lavfi", "-i",
   "gradients=s=1280x720:r=20:c0=0x1b1035:c1=0x0b3a5b:c2=0xb8336a:c3=0x12263a:n=4:speed=0.008",
   "-filter_complex",
   "[0:a]aformat=channel_layouts=mono,showwaves=s=1280x240:mode=cline:scale=sqrt:rate=20:colors=white:draw=full,"
   "colorkey=black:0.15:0.1[w];"
   f"[1:v][w]overlay=0:400:shortest=1{text},format=yuv420p[v]",
   "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "fast", "-crf", "30", "-c:a", "aac", "-b:a", "192k",
   "-shortest", "-movflags", "+faststart", str(video))

lyrics = info.get("lyrics") or ""
(dist / "lyrics.txt").write_text(f"{title}\n\nStyle: {info['style']}\n\n{lyrics}\n")
meta = " · ".join(x for x in [f"{info['bpm']} BPM" if info.get("bpm") else "", info.get("key") or "",
                              info.get("language") or "", info["model"]] if x)
(dist / "summary.md").write_text(
    f"## 🎵 {title}\n\n**Idea:** {info['prompt']}\n\n**Style:** {info['style']}\n\n{meta}\n\n"
    f"{len(mp3s)} version(s): " + ", ".join(f"`{m.name}`" for m in mp3s) + f" + `{video.name}`\n\n"
    f"### Lyrics\n```\n{lyrics}\n```\n")
(dist / "title.txt").write_text(title)
print("made:", *[p.name for p in sorted(dist.iterdir())])
