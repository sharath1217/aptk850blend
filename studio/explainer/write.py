"""AI script writer for the explainer studio: a topic in, a complete episode JSON out.
  python write.py "<topic>" <out.json> [style-tag]
Writes the long film AND a separately written Short, using ONLY the scene library below.
Two passes: writer -> editor/fact-checker. Free NVIDIA API (NVIDIA_API_KEY)."""
import json, os, re, sys, time
import httpx

PREFER = ["moonshotai/kimi-k2", "qwen/qwen3-235b", "deepseek-ai/deepseek-v3", "openai/gpt-oss-120b", "meta/llama-4-maverick",
          "nvidia/llama-3.3-nemotron-super", "meta/llama-3.3-70b", "qwen/qwen3", "nvidia/nemotron-3.5-lightning-30b-a3b"]


def pick_models():
    """Ask NVIDIA which models exist right now and use the strongest ones from our preference list."""
    try:
        ids = [m["id"] for m in httpx.get("https://integrate.api.nvidia.com/v1/models", timeout=60,
                                          headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"}).json()["data"]]
    except Exception as exc:
        log("model list failed:", exc); ids = []
    chosen = []
    for p in PREFER:
        hits = sorted([i for i in ids if i.startswith(p) and "base" not in i and "vision" not in i and "embed" not in i], reverse=True)
        if hits and hits[0] not in chosen:
            chosen.append(hits[0])
    chosen = chosen or ["nvidia/nemotron-3.5-lightning-30b-a3b"]
    log("models available, in order of preference:", chosen[:5])
    return chosen


MODELS = [m for m in os.environ.get("LLM_MODELS", "").split(",") if m] or pick_models()
SCENES = {  # scene type -> fields the AI must fill (the visual building blocks we have)
    "title": "kicker (short caps tag), title (1-3 words), subtitle (short line)",
    "counter": "value (integer), label (what is counted), sub (context line)",
    "bars": "title, items: 2-4 of {label, value (number), prefix?, suffix?} to compare sizes",
    "facts": "title, items: exactly 3 short bullet strings",
    "timeline": "events: 3-5 of {time (year or HH:MM), label (2-5 words)}",
    "quote": "text (a real, well-known quote OR a one-line takeaway), by (who said it, or 'the key idea')",
    "clock": "time (HH:MM), label (short caps phrase)",
    "depth": "depth (integer metres/units), compare (one comparison line)",
    "valve": "labels: 3 strings [input, control, output] (water-tap analogy for control/amplification)",
    "silicon": "(no fields) animated silicon crystal with phosphorus/boron doping",
    "mosfet": "state: 'off' or 'on' (animated MOSFET cross-section: source, drain, gate, channel)",
    "circuit": "(no fields) battery + LED + transistor switching the light on/off",
    "binary": "(no fields) 8 switches spelling 01001000, ON=1 OFF=0",
    "outro": "title (1-2 words), lines: 3 short strings",
    "diagram": ("title (2-5 words), svg: a COMPLETE simple SVG diagram you draw yourself that explains exactly what the narration "
                "says (e.g. server racks, airflow arrows, a chip, a pipeline). Use viewBox=\"0 0 1000 560\", only rect/circle/line/"
                "path/polyline/polygon/text, stroke=\"#d6aa5c\" or \"#9fd3ff\" or \"#ecebe6\", fill=\"none\" or dark fills "
                "like \"#13202e\", stroke-width 3-5, text fill=\"#ecebe6\" font-size 26-34, 4-12 labelled parts, no scripts/images/"
                "styles. Use it for every 'how it works' moment that the other scenes cannot show."),
    "photo": "query (2-5 words to search a real photo, e.g. 'data center server room'), label (2-5 words shown on the photo)",
}
log = lambda *a: print(*a, file=sys.stderr, flush=True)


def llm(prompt, temperature=0.7):
    for attempt in range(6):
        model = MODELS[min(attempt, len(MODELS) - 1)]
        try:
            r = httpx.post("https://integrate.api.nvidia.com/v1/chat/completions", timeout=600,
                           headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
                           json={"model": model, "temperature": temperature, "max_tokens": 8000,
                                 "messages": [{"role": "user", "content": prompt}],
                                 "chat_template_kwargs": {"thinking": False, "enable_thinking": False}})
            r.raise_for_status(); log("model:", model); return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log("LLM retry:", model, str(exc)[:200]); time.sleep(5 * (attempt + 1))
    raise SystemExit("LLM unavailable")


def ask_json(prompt, temperature=0.7):
    for _ in range(4):
        m = re.search(r"\{.*\}", llm(prompt, temperature), re.S)
        try:
            return json.loads(m.group(0))
        except Exception as exc:
            log("bad JSON, retrying:", exc)
    raise SystemExit("no JSON from the LLM")


ELECTRONIC = {"valve", "silicon", "mosfet", "circuit", "binary"}
ELECTRONIC_WORDS = ("transistor", "mosfet", "semiconductor", "chip", "circuit", "diode", "silicon", "binary", "logic gate", "electronic")
LIB = "\n".join(f'- "{k}": {v}' for k, v in SCENES.items())


def library(topic):
    on_topic = any(w in topic.lower() for w in ELECTRONIC_WORDS)
    return "\n".join(f'- "{k}": {v}' for k, v in SCENES.items() if on_topic or k not in ELECTRONIC)
VOICE_RULES = """NARRATION STYLE (most important): it must sound like a smart friend talking, not a textbook.
Short sentences. Contractions (it's, you'll, here's). Questions to the viewer. Little reactions ("Wait.", "Here's the trick.").
Concrete analogies from daily life. No filler, no "In this video we will". Every scene's narration is 1-4 sentences.
ACCURACY: only well-established facts. If a number is approximate say "about". Never invent quotes, names or numbers."""


def research(topic):
    """Facts come from sources, not from the model's memory: Wikipedia search -> top articles' text."""
    H = {"User-Agent": "GetYrStudioExplainer/1.0 (open-source educational video tool; python-httpx)", "Accept": "application/json"}
    try:
        r0 = httpx.get("https://en.wikipedia.org/w/api.php", headers=H, timeout=30, params={
            "action": "query", "list": "search", "srsearch": topic, "format": "json", "srlimit": 3})
        if r0.status_code != 200 or not r0.text.startswith("{"):
            log("wikipedia said:", r0.status_code, r0.text[:200])
        q = r0.json()
        titles = [h["title"] for h in q["query"]["search"]]
        text = []
        for t in titles:
            p = httpx.get("https://en.wikipedia.org/w/api.php", headers=H, timeout=30, params={
                "action": "query", "prop": "extracts", "explaintext": 1, "titles": t, "format": "json"}).json()
            page = next(iter(p["query"]["pages"].values())).get("extract", "")
            text.append(f"### {t} (Wikipedia)\n{page[:9000]}")
        log("research:", titles)
        return "\n\n".join(text)
    except Exception as exc:
        log("research failed:", exc); return ""


def write(topic, tag):
    global LIB
    LIB = library(topic)
    src = research(topic)
    if len(src) < 2000:
        raise SystemExit("No research sources found - refusing to write a script from memory")
    prompt = f"""You write narration + visual plans for a premium animated explainer channel ("GetYr Studio").
TOPIC: {topic}

SOURCE MATERIAL (use ONLY facts, numbers and dates found here; if something is not here, do not state it as fact):
{src or "(no sources found - use only very well-established facts)"}

{VOICE_RULES}

STRUCTURE of the long film (3.5-5 minutes, 550-750 words of narration, 16-24 scenes):
1. Hook in the first scene: a surprising fact or question. 2. Why it matters. 3. Background/history.
4. The core mechanism explained step by step with an analogy. 5. A deeper detail. 6. Real-world scale/impact.
7. Recap in one line + "Follow GetYr Studio for more".
Every scene must have a visual that SHOWS what the narration says. Vary scene types; never 3 "facts" in a row.
Aim for about 30% "diagram" scenes (your own drawings of the specific thing explained), 15-25% "photo" scenes (real things
the viewer should see), and the rest from the library. Use "facts" at most 3 times in the whole film.
VISUAL RULES: "counter" only for a real, specific number from the sources. "depth" only for a real depth/height/length.
"bars" only to compare real numbers. "timeline" only with real dates. Mechanism scenes (valve, silicon, mosfet,
circuit, binary) only when the narration describes exactly that. "clock" only for a real time of day.

ALSO write a SEPARATE Short/Reel (vertical, 30-50 seconds, 80-130 words, 5-7 scenes): its own punchy script,
hook in the first sentence, fast, ends with a line that loops back to the start. Not a copy of the film's lines.

SCENE LIBRARY (use ONLY these types and fields):
{LIB}

Return ONLY JSON:
{{"title": "...", "tag": "{tag}", "short_hook": "...",
  "scenes": [{{"type": "title", "kicker": "...", "title": "...", "subtitle": "...", "narration": "..."}}, ...],
  "short_scenes": [{{"type": "...", ..., "narration": "..."}}, ...]}}"""
    ep = ask_json(prompt, 0.8)
    words = lambda e: sum(len(str(x.get("narration", "")).split()) for x in e.get("scenes", []))
    log("draft:", len(ep.get("scenes", [])), "scenes,", words(ep), "words")
    for attempt in range(3):  # too short / thin -> send it back to be expanded
        if words(ep) >= 520 and len(ep.get("scenes", [])) >= 15:
            break
        ep2 = ask_json(f"""This explainer script is too short ({words(ep)} words, {len(ep.get('scenes', []))} scenes).
Expand it to 600-750 words and 16-24 scenes WITHOUT padding: add the missing parts of the structure
(hook, why it matters, history with real dates, step-by-step mechanism, a deeper detail, real-world scale with real numbers, recap).
Keep the same style rules, scene library and JSON format. Keep the separate Short (80-130 words).

{VOICE_RULES}

SOURCE MATERIAL:
{src[:12000]}

ALLOWED SCENES:
{LIB}

EPISODE:
{json.dumps(ep, ensure_ascii=False)}

Return ONLY the expanded JSON.""", 0.6)
        log("expanded:", len(ep2.get("scenes", [])), "scenes,", words(ep2), "words")
        if words(ep2) > words(ep):
            ep = ep2
    review = f"""You are the editor and fact-checker of an explainer channel. Improve this episode JSON for the topic "{topic}".
Check every fact and number AGAINST THE SOURCES below; fix or remove anything wrong, not in the sources, or uncertain (prefer "about").
Also check: counters show a real number, the mechanism is described correctly (e.g. switching is not amplification), and the
Short has real substance (80-130 words) with a strong first line.

SOURCES:
{src[:12000]} Make the narration sound more
human and natural (see rules), cut filler, keep the first sentence a strong hook. Make sure each scene's visual matches
its narration and uses only the allowed scene types/fields. Keep the same JSON format.

{VOICE_RULES}

ALLOWED SCENES:
{LIB}

EPISODE:
{json.dumps(ep, ensure_ascii=False)}

Return ONLY the corrected JSON."""
    def unsourced(e):
        flat = re.sub(r"[,\s]", "", src.lower()); bad = []
        for x in e.get("scenes", []) + e.get("short_scenes", []):
            for n in re.findall(r"\d[\d,.]*\d|\d", x.get("narration", "")):
                n2 = n.replace(",", "").rstrip(".")
                if len(n2) >= 2 and n2 not in flat:
                    bad.append(f'"{n}" in: {x["narration"]}')
        return bad
    bad = unsourced(ep)
    if bad:
        log("numbers not found in the sources:", len(bad))
        review += "\n\nTHESE NUMBERS ARE NOT IN THE SOURCES - correct them from the sources or remove them:\n" + "\n".join(bad[:30])
    try:
        ep2 = ask_json(review, 0.3)
        if len(ep2.get("scenes", [])) >= 0.85 * len(ep.get("scenes", [])) and words(ep2) >= 0.85 * words(ep):
            ep = ep2
    except SystemExit:
        log("editor pass failed, keeping the draft")
    return ep


def clean_scene(s):
    t = s.get("type")
    if t not in SCENES:
        t = "facts"; s = {"type": "facts", "title": s.get("title", ""), "items": s.get("items") or [], "narration": s.get("narration", "")}
    s["type"] = t
    s["narration"] = re.sub(r"\s+", " ", str(s.get("narration", ""))).strip()
    if t == "facts":
        s["items"] = [str(x) for x in (s.get("items") or [])][:3] or [s.get("title", "")]
        s.setdefault("title", "")
    if t == "counter":
        try: s["value"] = int(float(str(s.get("value", 0)).replace(",", "")))
        except Exception: s["value"] = 0
        s.setdefault("label", ""); s.setdefault("sub", "")
    if t == "bars":
        items = []
        for it in (s.get("items") or [])[:4]:
            try: items.append({**it, "value": float(str(it.get("value", 0)).replace(",", "")), "label": str(it.get("label", ""))})
            except Exception: pass
        s["items"] = items or [{"label": "", "value": 1}]; s.setdefault("title", "")
    if t == "timeline":
        s["events"] = [{"time": str(e.get("time", "")), "label": str(e.get("label", ""))} for e in (s.get("events") or [])][:5] or [{"time": "", "label": ""}]
    if t == "valve":
        s["labels"] = (list(s.get("labels") or []) + ["in", "control", "out"])[:3]
    if t == "outro":
        s["lines"] = (list(s.get("lines") or []))[:3]; s.setdefault("title", "")
    if t == "title":
        for k in ("kicker", "title", "subtitle"): s.setdefault(k, "")
    if t == "quote":
        s.setdefault("text", ""); s.setdefault("by", "")
    if t == "clock":
        s["time"] = str(s.get("time", "00:00"))[:5]; s.setdefault("label", "")
    if t == "diagram":
        svg = str(s.get("svg", ""))
        svg = re.sub(r"<\s*(script|image|foreignObject|style)[^>]*>.*?<\s*/\s*\1\s*>", "", svg, flags=re.S | re.I)
        svg = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", svg)
        ok = svg.strip().startswith("<svg") and svg.strip().endswith("</svg>") and len(re.findall(r"<(rect|circle|line|path|polyline|polygon)", svg)) >= 3
        if not ok:  # broken drawing -> safe fallback, never an empty frame
            return {"type": "facts", "title": s.get("title", ""), "items": [s.get("title", "")], "narration": s["narration"]}
        if "viewBox" not in svg:
            svg = svg.replace("<svg", '<svg viewBox="0 0 1000 560"', 1)
        s["svg"] = svg; s.setdefault("title", "")
    if t == "photo":
        s.setdefault("query", s.get("label", "")); s.setdefault("label", "")
    if t == "depth":
        try: s["depth"] = int(float(s.get("depth", 0)))
        except Exception: s["depth"] = 0
        s.setdefault("compare", "")
    return s


OK_LICENCES = ("cc0", "public domain", "pd", "cc by", "cc-by")  # commercial use allowed (credit given)


def fetch_photo(query, dest):
    H = {"User-Agent": "GetYrStudioExplainer/1.0 (open-source educational video tool; python-httpx)", "Accept": "application/json"}
    try:
        rr = httpx.get("https://commons.wikimedia.org/w/api.php", headers=H, timeout=30, params={
            "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12,
            "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1920, "format": "json"})
        if rr.status_code != 200 or not rr.text.startswith("{"):
            log("commons said:", rr.status_code, rr.text[:200])
        r = rr.json()
        pages = sorted(r.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        for p in pages:
            ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "").lower()
            if not any(lic.startswith(x) or x in lic for x in OK_LICENCES) or "nc" in lic or "nd" in lic:
                continue
            if ii.get("width", 0) < 1000:
                continue
            img = httpx.get(ii.get("thumburl") or ii["url"], headers=H, timeout=60, follow_redirects=True)
            open(dest, "wb").write(img.content)
            artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value", "unknown"))[:60]
            return f"Photo: {artist} / Wikimedia Commons ({md.get('LicenseShortName', {}).get('value', '')})"
    except Exception as exc:
        log("photo search failed:", query, exc)
    return None


def attach_photos(ep, public_dir="public"):
    os.makedirs(f"{public_dir}/img", exist_ok=True); credits = []
    for group in ("scenes", "short_scenes"):
        for i, s in enumerate(ep.get(group, [])):
            if s["type"] != "photo":
                continue
            name = f"img/{group[0]}{i}.jpg"; c = fetch_photo(s.get("query", ""), f"{public_dir}/{name}")
            if c:
                s["file"] = name; s["credit"] = c; credits.append(c); log("photo:", s.get("query"), "->", c)
            else:  # no free photo -> keep the scene meaningful as a fact card
                s.update({"type": "facts", "title": s.get("label", ""), "items": [s.get("label", "")]})
    ep["credits"] = sorted(set(credits))


def main():
    topic, out = sys.argv[1], sys.argv[2]
    tag = sys.argv[3] if len(sys.argv) > 3 else "GETYR STUDIO"
    ep = write(topic, tag)
    ep["scenes"] = [clean_scene(s) for s in ep.get("scenes", []) if s.get("narration")]
    ep["short_scenes"] = [clean_scene(s) for s in ep.get("short_scenes", []) if s.get("narration")]
    ep.setdefault("title", topic); ep["tag"] = ep.get("tag") or tag
    attach_photos(ep)
    ep["voice"] = "en-US-AndrewMultilingualNeural"; ep["rate"] = "+4%"; ep["short"] = []
    words = sum(len(s["narration"].split()) for s in ep["scenes"])
    log(f"final: {len(ep['scenes'])} scenes, {words} words; short {len(ep['short_scenes'])} scenes")
    json.dump(ep, open(out, "w"), indent=1, ensure_ascii=False)
    with open(out.replace(".json", ".txt"), "w") as f:  # readable script for review
        f.write(f"{ep['title']}\n\n")
        for i, s in enumerate(ep["scenes"]):
            f.write(f"[{i:02d} {s['type']}] {s['narration']}\n")
        f.write("\n--- SHORT ---\n")
        for s in ep["short_scenes"]:
            f.write(f"[{s['type']}] {s['narration']}\n")


if __name__ == "__main__":
    main()
