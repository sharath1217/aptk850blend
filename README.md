# GetYr_Studio – AI short films in Blender

Type a one-line idea, pick a genre, and GitHub Actions makes a **4–5 minute animated short film
(16:9, 1080p)** plus a **60-second vertical Short (9:16)** cut from its best moment. The pipeline
writes the story, voices it, renders it in Blender, and edits it.

## Fully automatic
Every day at 20:17 UTC a new film is made with no input: the AI picks the genre, invents the idea, and
the finished film + Short are published under **Releases** (kept forever).

## How to make a film by hand
Actions → **Short film** → *Run workflow*:

| input | what it does |
|---|---|
| `genre` | `auto` (rotates daily), `drama`, `action`, `scifi`, `comedy` |
| `idea` | leave empty and the AI invents one (or type your own) |
| `minutes` | 4–5 |
| `quality` | `stills` = one picture per shot (about 15 min, to check the story first) · `draft` = 540p · `final` = 1080p |

Download **short-film** from the run's Artifacts: `film.mp4`, `short.mp4`, `subtitles.srt`,
`script.txt`, `credits.txt`. The shot-by-shot script also appears on the run's summary page.

## How it works (`studio/film/`)
1. **`writer.py`**: the NVIDIA LLM writes the film as a shot list. It can only use building blocks the
   renderer knows, and everything it returns is validated. Edge TTS voices every line, with one voice
   per character. Each shot is timed to its dialogue, and the writer picks the best 45–60 s stretch for
   the Short. When the story has a vehicle, `asset_finder.py` looks for a real licensed model.
2. **`shots.py`** (Blender 4.2, Cycles): everything is built in code.
   * **sets**: coast with a lighthouse, night city, alien planet, toytown, room, forest. Each can be day, dusk or night, with rain, snow or fog.
   * **actors**: stylised robots (box, round or tall; 8 colours). They can walk, run, talk, wave, look, jump, dance, act sad or fall. Their mouths light up while their line is spoken, and they blink.
   * **vehicles**: car drive, police car chase, spaceship flight and spaceship landing.
   * **cameras**: establish, push-in, orbit, track, close-up, over-the-shoulder, low angle, crane, handheld, top-down. Shots use depth of field, motion blur and mist.
   * 20 machines render in parallel. Frames are dealt out round-robin, so every machine gets the same mix of heavy and light shots.
3. **`assemble.py`**: places the dialogue on the exact frame, mixes in a generated music bed and
   ambience (rain, sea, wind, city), and adds the title card, subtitles, end credits and the film grade.
   It then cuts the vertical Short: blurred fill background, a hook caption and subtitles.

Secrets: `NVIDIA_API_KEY`.

