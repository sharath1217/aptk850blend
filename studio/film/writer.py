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
COLORS_HINT = ["orange", "blue", "red", "green", "yellow", "purple", "white", "pink"]
VOCAB = {
    "set": ["racetrack", "garage", "coast", "city", "planet", "toytown", "room", "forest"],
    "time": ["day", "dusk", "night"],
    "weather": ["clear", "rain", "snow", "fog"],
    "camera": ["establish", "push_in", "orbit", "track", "closeup", "over_shoulder",
               "low_angle", "crane_up", "handheld", "top_down"],
    "action": ["idle", "talk", "walk", "run", "wave", "look", "jump", "dance", "sad", "fall"],
    "vehicle": ["none", "race_start", "race", "overtake", "crash", "finish", "car_drive", "car_chase", "ship_fly", "ship_land"],
}
VOICES = ["en-US-GuyNeural", "en-US-JennyNeural", "en-GB-RyanNeural", "en-US-AnaNeural",
          "en-GB-SoniaNeural", "en-AU-WilliamNeural", "en-US-DavisNeural", "en-US-AriaNeural"]
NARRATOR = "en-US-ChristopherNeural"
GENRE_HINT = {
    "racing": ("a motorsport drama: rivalry, team spirit, comebacks; sets racetrack (race_start, race, overtake, crash, "
               "finish - the race cars are driven by the characters) and garage (team talks, repairs, pressure); "
               "on-track cameras: track (chase cam), handheld (onboard), low_angle (bumper cam), push_in (TV trackside "
               "long lens), establish (helicopter), closeup (driver), orbit"),
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


CONTEXT = ""  # series mode: the bible + "previously on" summaries


def treatment(genre: str, idea: str, minutes: float) -> str:
    """Pass 1: a proper story (structure, character arcs, set pieces) before any camera talk."""
    return llm(f"""You are an award-winning animation screenwriter (think Pixar shorts).
Write the story treatment for a {minutes:.0f}-minute animated short. Genre: {GENRE_HINT.get(genre, genre)}.
Idea: {idea}
{CONTEXT}
All characters are expressive stylised robots (2-4 of them), each with a name, a want, a flaw and a
distinct way of talking. Places available: coast with a lighthouse, night city, alien planet,
cartoon toytown, a cosy room, a forest (day, dusk or night; rain, snow or fog).
Structure it in 8 beats, 2-4 sentences each:
1 HOOK (an intriguing first image)  2 SETUP (who, where, what they want)  3 INCITING INCIDENT
4 RISING ACTION (obstacles, a funny or touching moment)  5 MIDPOINT TWIST  6 LOWEST POINT
7 CLIMAX (the big visual set piece)  8 RESOLUTION (an emotional final image that echoes the hook).
Show, don't tell: favour actions and visuals over talk. Make the ending land emotionally.
Return the treatment only.""", temperature=0.9)


def write_story(genre: str, idea: str, minutes: float) -> dict:
    n_shots = int(minutes * 60 / 7.5)
    story_text = treatment(genre, idea, minutes)
    log("TREATMENT (draft):\n" + story_text)
    # Story editor pass: a tough script doctor critiques the draft and rewrites it stronger
    story_text = llm(f"""You are a demanding story editor at an animation studio.
{CONTEXT}
DRAFT TREATMENT:
{story_text}

First, silently check it: Is the hook intriguing in the first 10 seconds? Does the hero want something
specific, and is there a real obstacle? Are the stakes clear and personal? Is there a surprising but fair
twist? Does the climax come from the characters' choices (not luck)? Does the ending pay off the opening
emotionally? Are characters consistent with the series bible and previous episodes (if any)? Is every
beat something that can be SHOWN with the available sets and actions?
Then rewrite the treatment fixing every weakness, keeping the same 8-beat format.
Return ONLY the improved treatment.""", temperature=0.7)
    log("TREATMENT (edited):\n" + story_text)
    prompt = f"""You are a film director and cinematographer turning this treatment into a {minutes:.0f}-minute
animated short film. Genre: {GENRE_HINT.get(genre, genre)}.

TREATMENT:
{story_text}
{CONTEXT}

DIRECTING RULES (follow them, they make the film look professional):
- Open every new location or time of day with an "establish" or "crane_up" shot.
- Dialogue between two characters: alternate "over_shoulder" and "closeup" (shot / reverse shot).
- Emotional moments (sad, surprise, decisions): "closeup" or "push_in".
- Movement (walk, run, chases, flying): "track", "handheld" or "low_angle".
- Heroic or big reveal moments: "low_angle" or "orbit". Endings: "crane_up" or "establish".
- Never use the same camera twice in a row. Vary shot lengths: quick 3-4 s shots in action, 6-9 s in calm moments.
- Use weather and time of day for mood (rain/night for danger, dusk for emotion, day for joy).
- Let images speak: about a third of the shots have no dialogue.

The film MUST have AT LEAST {n_shots} shots (each 4-10 seconds, numbered in your head 1..{n_shots}) - a short
list is useless; write every shot with a clear
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
    best = None
    for attempt in range(5):
        raw = llm(prompt)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            story = json.loads(m.group(0))
        except Exception as exc:
            log("Bad JSON, retrying:", exc); continue
        got = len(story.get("shots", []))
        log(f"Attempt {attempt + 1}: {got} shots (need {int(n_shots * 0.75)}+)")
        if not best or got > len(best["shots"]):
            best = story
        if got >= n_shots * 0.75:
            return story
    if best and len(best["shots"]) >= 8:
        return best
    raise SystemExit("The LLM did not return a usable story")


def clean(story: dict, fixed_cast: dict | None = None) -> dict:
    pick = lambda v, key, d: v if v in VOCAB[key] else d
    cast, vi = {}, 0
    for c in ([] if fixed_cast else story.get("cast", [])[:4]):
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
    if fixed_cast:
        cast = {k: dict(v) for k, v in fixed_cast.items()}
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


def direct(story: dict) -> None:
    """Director's pass in code: fixes the camera grammar the LLM sometimes forgets."""
    prev = None
    for i, s in enumerate(story["shots"]):
        new_place = prev is None or (s["set"], s["time"]) != (prev["set"], prev["time"])
        speakers = {l["speaker"] for l in s["lines"]} - {"narrator"}
        acts = {c["action"] for c in s["characters"]}
        if new_place and s["vehicle"] == "none" and s["camera"] not in ("establish", "crane_up"):
            s["camera"] = "establish"
        elif s["vehicle"] in ("car_chase", "car_drive") and s["camera"] in ("closeup", "over_shoulder", "top_down"):
            s["camera"] = "track"
        elif len(s["characters"]) == 2 and speakers and s["camera"] in ("establish", "top_down", "crane_up") and not new_place:
            s["camera"] = "over_shoulder"
        elif acts & {"sad", "fall"} and s["camera"] in ("establish", "top_down"):
            s["camera"] = "closeup"
        if prev and s["camera"] == prev["camera"]:  # never the same camera twice in a row
            alt = {"over_shoulder": "closeup", "closeup": "over_shoulder" if len(s["characters"]) == 2 else "push_in",
                   "track": "handheld", "handheld": "low_angle", "establish": "push_in"}
            s["camera"] = alt.get(s["camera"], "push_in" if s["camera"] != "push_in" else "orbit")
        if s["camera"] == "over_shoulder" and len(s["characters"]) < 2:
            s["camera"] = "closeup"
        prev = s
    last = story["shots"][-1]
    if last["camera"] not in ("crane_up", "establish"):
        last["camera"] = "crane_up"


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
        k = min(1.5, minutes * 60 * 0.9 / total)
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


def invent(genre: str) -> tuple[str, str]:
    """Fully automatic mode: pick a genre (rotating by day) and let the AI invent a fresh idea."""
    if genre in ("", "auto"):
        genre = list(GENRE_HINT)[int(time.time() // 86400) % len(GENRE_HINT)]
    idea = llm(f"Invent ONE original, surprising idea for a 4-minute animated short film about robots. "
               f"Genre: {GENRE_HINT[genre]}. Strong emotion, a clear goal and a twist ending. "
               f"Reply with one sentence only.", temperature=1.0).strip().strip('"')
    return genre, idea


# ------------------------------------------------------------------ series mode
SERIES = Path(os.environ.get("SERIES_DIR", "series"))


def ask_json(prompt: str) -> dict:
    for _ in range(4):
        m = re.search(r"\{.*\}", llm(prompt, temperature=0.9), re.S)
        try:
            return json.loads(m.group(0))
        except Exception as exc:
            log("Bad JSON, retrying:", exc)
    raise SystemExit("LLM gave no JSON")


THEME = os.environ.get("SERIES_THEME", "a robot motor-racing championship: a young underdog robot racing driver, "
                       "their small family team, and a fierce rival team - every episode builds to a race")


LIBRARY = Path(__file__).with_name("characters.json")


def library() -> dict:
    """The permanent cast (characters.json): same looks, voices and personalities in every series."""
    chars = json.loads(LIBRARY.read_text())["characters"]
    return {c["id"]: dict(c, slot=i) for i, c in enumerate(chars)}


def series_bible() -> dict:
    """Created once by the AI, then kept forever. The cast always comes from characters.json."""
    f = SERIES / "bible.json"
    lib = library()
    if f.exists():
        b = json.loads(f.read_text())
    else:
        roster = "\n".join(f"- {c['id']}: {c['name']}, {c['role']}, {c['personality']}" for c in lib.values())
        b = ask_json(f"""Create an original animated web SERIES (heart, humour, rivalry and thrilling action,
family friendly). Theme: {THEME}.
You MUST use characters from this permanent cast (pick the 4-6 that fit best; do not invent new ones):
{roster}
Return ONLY JSON:
{{"series_title": "...", "premise": "2 sentences", "world": "where they live, 2 sentences",
  "home_set": one of {VOCAB['set']}, "tone": "...", "cast_ids": ["turbo", "..."],
  "season_arc": "the big story that unfolds over the first 10 episodes"}}""")
        if b.get("home_set") not in VOCAB["set"]:
            b["home_set"] = "racetrack"
        SERIES.mkdir(parents=True, exist_ok=True)
    ids = [i for i in b.get("cast_ids", []) if i in lib] or list(lib)[:5]
    b["cast_ids"] = ids
    b["cast"] = {i: lib[i] for i in ids}  # always fresh from the library (edits apply everywhere)
    f.write_text(json.dumps({k: v for k, v in b.items() if k != "cast"}, indent=1))
    log("SERIES:", b.get("series_title"), "| cast:", ", ".join(ids))
    return b


def episodes() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((SERIES / "episodes").glob("ep*.json"))]


def series_episode() -> tuple[str, str, dict, int]:
    global CONTEXT
    b, hist = series_bible(), episodes()
    n = len(hist) + 1
    cast_txt = "\n".join(f"- {c['name']} (id {c['id']}, {c['color']} {c['shape']} robot, {c['role']}): {c['personality']}. "
                         f"Wants: {c.get('want', '')}. Flaw: {c.get('flaw', '')}. Catchphrase: \"{c.get('catchphrase', '')}\""
                         for c in b["cast"].values())
    prev = "\n".join(f"Episode {e['n']} \"{e['title']}\": {e['summary']}" for e in hist[-6:]) or "(this is the pilot)"
    CONTEXT = (f"\nTHIS IS EPISODE {n} OF THE SERIES \"{b['series_title']}\". {b['premise']} World: {b['world']}\n"
               f"Home location: {b['home_set']}. Tone: {b.get('tone', '')}. Season arc: {b.get('season_arc', '')}\n"
               f"MAIN CAST (use ONLY these characters, with these exact ids):\n{cast_txt}\n"
               f"PREVIOUSLY:\n{prev}\n"
               "Keep characters consistent with earlier episodes, call back to past events, move the season arc\n"
               "forward a little, and end with a small hook for the next episode.\n")
    e = ask_json(f"""{CONTEXT}
Pitch episode {n}: its genre (one of {list(GENRE_HINT)}; for a racing series mostly "racing") and a
one-sentence idea (a race or a challenge on track, plus a personal story off track).
Return ONLY JSON: {{"genre": "...", "idea": "..."}}""")
    genre = e.get("genre") if e.get("genre") in GENRE_HINT else "racing"
    return genre, e.get("idea", "A new adventure"), b, n


def main() -> None:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    genre, idea = sys.argv[2].lower(), sys.argv[3].strip()
    minutes = float(sys.argv[4]) if len(sys.argv) > 4 else 4.5
    bible, ep = None, 0
    if os.environ.get("SERIES_MODE") == "1":
        genre, idea, bible, ep = series_episode()
    elif genre in ("", "auto") or not idea:
        genre, idea = invent(genre)
    log("Genre:", genre, "| Idea:", idea)
    story = clean(write_story(genre, idea, minutes), bible["cast"] if bible else None)
    direct(story)
    story["genre"], story["idea"] = genre, idea
    if bible:
        story["series"], story["episode"] = bible["series_title"], ep
        story["title"] = f"{bible['series_title']} - Episode {ep}: {story['title']}"
        summary = llm(f"Summarise this episode in 3 sentences for a 'previously on' recap, naming the "
                      f"characters and what changed:\n{json.dumps([l['text'] for s in story['shots'] for l in s['lines']])}\n"
                      f"Idea: {idea}", temperature=0.3).strip()
        d = out / "series" / "episodes"; d.mkdir(parents=True, exist_ok=True)
        (out / "series" / "bible.json").write_text(json.dumps({k: v for k, v in bible.items() if k != "cast"}, indent=1))
        (d / f"ep{ep:03d}.json").write_text(json.dumps({"n": ep, "title": story["title"], "idea": idea,
                                                         "summary": summary}, indent=1))
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
