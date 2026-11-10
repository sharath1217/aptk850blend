"""Short film - step 1 (writer). A one-line idea -> full film plan, fully automatic.

  python studio/film/writer.py <assets_dir> "<genre>" "<idea>" [minutes]

* NVIDIA LLM writes the story as a shot list (sets, cameras, characters, actions, dialogue)
  using ONLY the building blocks the Blender shot library knows (see VOCAB below).
* Every line of dialogue is voiced with free Edge TTS (one voice per character).
* Shots are timed from the voices, the 60 s Short is picked from the film's best moment.
* Optional: a real 3D vehicle model is fetched with asset_finder (licence + vision checked).
Writes <assets>/story.json + <assets>/lines/*.mp3 and prints frames=<n> for the render jobs."""
import json, math, os, re, subprocess, sys, time
from pathlib import Path
import httpx

FPS = 24
VOCAB = {
    "set": ["coast", "city", "planet", "toytown", "room", "forest"],
    "time": ["day", "dusk", "night"],
    "weather": ["clear", "rain", "snow", "fog"],
    "camera": ["establish", "push_in", "orbit", "track", "closeup", "over_shoulder",
               "low_angle", "crane_up", "handheld", "top_down"],
    "action": ["idle", "talk", "walk", "run", "wave", "look", "jump", "dance", "sad", "fall"],
    "vehicle": ["none", "car_drive", "car_chase", "ship_fly", "ship_land"],
}
VOICES = ["en-US-GuyNeural", "en-US-JennyNeural", "en-GB-RyanNeural", "en-US-AnaNeural",
          "en-GB-SoniaNeural", "en-AU-WilliamNeural", "en-US-DavisNeural", "en-US-AriaNeural"]
NARRATOR = "en-US-ChristopherNeural"
GENRE_HINT = {
    "drama": "an emotional drama (loss, hope, friendship); sets coast, room, forest; slow cameras; warm dusk light",
    "action": "a tense action thriller with a car chase; sets city (night, rain), car_chase vehicles; fast cuts, handheld, low angles",
    "scifi": "a science-fiction adventure; sets planet and a spaceship (ship_fly / ship_land); wonder and danger",
    "comedy": "a light, funny cartoon comedy with physical gags; sets toytown and room; bright day light; jump, dance, fall",
}
log = lambda *a: print(*a, file=sys.stderr, flush=True)


def llm(prompt: str, temperature: float = 0.8) -> str:
    for attempt in range(4):
        try:
            r = httpx.post("https://integrate.api.nvidia.com/v1/chat/completions", timeout=600,
                           headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
                           json={"model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                                 "temperature": temperature, "max_tokens": 12000,
                                 "messages": [{"role": "user", "content": prompt}],
                                 "chat_template_kwargs": {"thinking": False, "enable_thinking": False}})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log("LLM failed:", str(exc)[:300]); time.sleep(10 * (attempt + 1))
    raise SystemExit("LLM unavailable")


def write_story(genre: str, idea: str, minutes: float) -> dict:
    n_shots = int(minutes * 60 / 7.5)
    prompt = f"""You are a film director writing a {minutes:.0f}-minute animated short film.
Genre: {GENRE_HINT.get(genre, genre)}.
Idea: {idea}

The film is made of {n_shots - 4} to {n_shots + 4} shots (each 4-12 seconds) with a clear
beginning, conflict, climax and satisfying ending. All characters are expressive stylised ROBOTS
(no humans, no animals) - give each a name and personality. Max 4 characters, max 2 per shot.
Keep dialogue short, natural and emotional (max 2 lines per shot, max 18 words per line).
Some shots have no dialogue. A "narrator" may speak at the start and the end.

Use ONLY these values:
set: {VOCAB['set']}
time: {VOCAB['time']}
weather: {VOCAB['weather']}
camera: {VOCAB['camera']}
action: {VOCAB['action']}
vehicle: {VOCAB['vehicle']}

Return ONLY JSON, no markdown:
{{"title": "...", "logline": "one sentence",
  "cast": [{{"id": "bolt", "name": "Bolt", "personality": "...", "color": "orange|blue|red|green|yellow|purple|white|pink", "shape": "box|round|tall", "voice": "male|female|child|old"}}],
  "vehicle_model": "short description of the main vehicle, or none",
  "short": {{"from_shot": 0, "to_shot": 0, "hook": "max 8 word caption for the 60 s vertical Short"}},
  "shots": [{{"set": "...", "time": "...", "weather": "...", "camera": "...", "duration": 6,
             "characters": [{{"id": "bolt", "action": "walk"}}], "vehicle": "none",
             "lines": [{{"speaker": "bolt", "text": "..."}}]}}]}}
"short" must be 6-10 consecutive shots forming the most gripping ~50 second moment."""
    for attempt in range(3):
        raw = llm(prompt)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            story = json.loads(m.group(0))
            if len(story.get("shots", [])) >= 8:
                return story
        except Exception as exc:
            log("Bad JSON, retrying:", exc)
    raise SystemExit("The LLM did not return a usable story")


def clean(story: dict) -> dict:
    pick = lambda v, key, d: v if v in VOCAB[key] else d
    cast, vi = {}, 0
    for c in story.get("cast", [])[:4]:
        cid = re.sub(r"\W", "", str(c.get("id") or c.get("name", "bot")).lower())[:16] or f"bot{vi}"
        kind = c.get("voice", "male")
        voice = {"female": ["en-US-JennyNeural", "en-GB-SoniaNeural", "en-US-AriaNeural"],
                 "child": ["en-US-AnaNeural"], "old": ["en-GB-RyanNeural", "en-US-DavisNeural"]
                 }.get(kind, ["en-US-GuyNeural", "en-AU-WilliamNeural", "en-US-DavisNeural"])
        used = {x["voice"] for x in cast.values()}
        voice = next((v for v in voice if v not in used), VOICES[vi % len(VOICES)])
        cast[cid] = {"id": cid, "name": c.get("name", cid.title()), "voice": voice,
                     "color": c.get("color", "orange"), "shape": c.get("shape", "box"),
                     "personality": c.get("personality", ""), "slot": vi}
        vi += 1
    if not cast:
        cast["bolt"] = {"id": "bolt", "name": "Bolt", "voice": "en-US-GuyNeural", "color": "orange",
                        "shape": "box", "personality": "", "slot": 0}
    first = next(iter(cast))
    names = {c["name"].lower(): k for k, c in cast.items()}
    shots = []
    for s in story["shots"]:
        chars = []
        for ch in (s.get("characters") or [])[:2]:
            cid = str(ch.get("id", "")).lower(); cid = cid if cid in cast else names.get(cid)
            if cid and cid not in [c["id"] for c in chars]:
                chars.append({"id": cid, "action": pick(ch.get("action"), "action", "idle")})
        lines = []
        for ln in (s.get("lines") or [])[:2]:
            sp = str(ln.get("speaker", "narrator")).lower()
            sp = "narrator" if sp == "narrator" else (sp if sp in cast else names.get(sp, first))
            text = str(ln.get("text", "")).strip()
            if text:
                lines.append({"speaker": sp, "text": text})
                if sp != "narrator" and sp not in [c["id"] for c in chars] and len(chars) < 2:
                    chars.append({"id": sp, "action": "talk"})
        for c in chars:  # whoever speaks moves their mouth light
            if c["action"] == "idle" and any(l["speaker"] == c["id"] for l in lines):
                c["action"] = "talk"
        shots.append({"set": pick(s.get("set"), "set", "coast"), "time": pick(s.get("time"), "time", "dusk"),
                      "weather": pick(s.get("weather"), "weather", "clear"),
                      "camera": pick(s.get("camera"), "camera", "push_in"),
                      "vehicle": pick(s.get("vehicle"), "vehicle", "none"),
                      "duration": max(3.0, min(12.0, float(s.get("duration") or 6))),
                      "characters": chars, "lines": lines})
    sh = story.get("short") or {}
    return {"title": story.get("title", "Untitled"), "logline": story.get("logline", ""),
            "cast": cast, "vehicle_model": story.get("vehicle_model", "none"), "shots": shots,
            "short": {"from_shot": int(sh.get("from_shot", 0)), "to_shot": int(sh.get("to_shot", 0)),
                      "hook": sh.get("hook", story.get("title", ""))}}


def duration(f: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                 "csv=p=0", str(f)], capture_output=True, text=True, check=True).stdout)


def voice_and_time(story: dict, out: Path, minutes: float) -> None:
    (out / "lines").mkdir(exist_ok=True)
    TITLE = 4.0  # seconds of opening title card (rendered over the first shot)
    t, n = 0.0, 0
    for i, s in enumerate(story["shots"]):
        cursor = 0.5 + (TITLE if i == 0 else 0)
        for ln in s["lines"]:
            voice = NARRATOR if ln["speaker"] == "narrator" else story["cast"][ln["speaker"]]["voice"]
            f = out / "lines" / f"l{n:03d}.mp3"; n += 1
            for attempt in range(4):
                r = subprocess.run(["edge-tts", "--voice", voice, "--text", ln["text"],
                                    "--write-media", str(f)], capture_output=True, text=True)
                if r.returncode == 0 and f.exists():
                    break
                time.sleep(3)
            ln["file"] = f.name; ln["at"] = round(cursor, 3); ln["len"] = round(duration(f), 3)
            cursor += ln["len"] + 0.35
        s["duration"] = max(s["duration"] + (TITLE if i == 0 else 0), cursor + 0.6)
    total = sum(s["duration"] for s in story["shots"])
    if total < minutes * 60 * 0.85:  # too short: let silent moments breathe
        k = minutes * 60 * 0.9 / total
        for s in story["shots"]:
            s["duration"] *= k
    start = 0
    for s in story["shots"]:
        s["frames"] = int(math.ceil(s["duration"] * FPS)); s["start"] = start; start += s["frames"]
        for ln in s["lines"]:
            ln["frame"] = s["start"] + int(ln["at"] * FPS)
    story["frames"] = start
    # The Short: requested shots, grown/shrunk to 45-60 s
    sh, shots = story["short"], story["shots"]
    a = min(max(sh["from_shot"], 0), len(shots) - 1); b = min(max(sh["to_shot"], a), len(shots) - 1)
    secs = lambda a, b: sum(x["frames"] for x in shots[a:b + 1]) / FPS
    while secs(a, b) < 45 and (a > 0 or b < len(shots) - 1):
        b, a = (b + 1, a) if b < len(shots) - 1 else (b, a - 1)
    while secs(a, b) > 60 and b > a:
        b -= 1
    sh.update(from_shot=a, to_shot=b, start=shots[a]["start"],
              end=min(shots[b]["start"] + shots[b]["frames"], shots[a]["start"] + 60 * FPS))
    log(f"Film: {story['title']} - {len(shots)} shots, {story['frames'] / FPS:.0f} s; "
        f"Short: shots {a}-{b} ({(sh['end'] - sh['start']) / FPS:.0f} s)")


def main() -> None:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    genre, idea = sys.argv[2].lower(), sys.argv[3]
    minutes = float(sys.argv[4]) if len(sys.argv) > 4 else 4.5
    story = clean(write_story(genre, idea, minutes))
    story["genre"], story["idea"] = genre, idea
    voice_and_time(story, out, minutes)
    vm = str(story.get("vehicle_model", "none"))
    if any(s["vehicle"] != "none" for s in story["shots"]) and vm.lower() != "none" and os.environ.get("BLENDER"):
        try:  # a real model for the hero vehicle; Blender builds one itself otherwise
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            import asset_finder
            car = any(s["vehicle"].startswith("car") for s in story["shots"])
            kw = ["car", "sports car", "coupe", "sedan"] if car else ["spaceship", "spacecraft", "starship", "shuttle"]
            got = asset_finder.find(out / "model", vm, "stylised animated film", kw)
            if got:
                story["credits_model"] = got["credit"]
        except Exception as exc:
            log("Vehicle model skipped:", exc)
    (out / "story.json").write_text(json.dumps(story, indent=1))
    lines = [f"{story['title']}\n{story['logline']}\n"]
    for i, s in enumerate(story["shots"]):
        who = ", ".join(f"{c['id']} ({c['action']})" for c in s["characters"])
        lines.append(f"[{i:02d}] {s['set']}/{s['time']}/{s['weather']} {s['camera']} {s['vehicle']} - {who}")
        lines += [f"     {l['speaker'].upper()}: {l['text']}" for l in s["lines"]]
    (out / "script.txt").write_text("\n".join(lines) + "\n")
    print(f"frames={story['frames']}")


if __name__ == "__main__":
    main()
