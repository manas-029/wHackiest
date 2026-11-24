# LIFEGRAPH AI — 3-Minute Explainer Video

## Deliverable
`LIFEGRAPH_AI_Explainer.mp4` — a 3:00 (180 s) animated motion-graphics explainer,
1920×1080 @ 30 fps, with AI narration and a subtle ambient soundtrack.
Visuals are composed on a 1280×720 logical canvas and upscaled with Lanczos
filtering, with slow camera drift/push-in for a cinematic feel.

## What it covers (timeline)
| Time | Scene | Content |
|---|---|---|
| 0:00–0:12 | Intro | Logo, tagline, Track 3 positioning |
| 0:12–0:30 | The Problem | Fragmented data across calendar, email, tasks, finance, phone, weather, social |
| 0:30–0:48 | Core Cycle | OBSERVE → UNDERSTAND → ANALYZE → PREDICT → RECOMMEND → EXECUTE |
| 0:48–1:05 | AI Assistant | Conversational + contextual assistant, natural-language queries |
| 1:05–1:33 | Six Domains | Academic, Productivity, Financial, Digital, Environmental, Social |
| 1:33–1:52 | Schedule | Smart schedule, free-time detection, recommended time blocks, user approval |
| 1:52–2:11 | Smart Tasks | PDF extraction, adaptive follow-up questions, priority + workload estimate |
| 2:11–2:29 | Deep Intelligence | Cross-domain relationship graph, what-if sliders, correlation caveat |
| 2:29–2:46 | Control | Learned preferences, three autonomy levels, approval gate, weekly report |
| 2:46–3:00 | Closing | Final vision and tagline |

## Files
- `make_video.py` — full renderer (visuals, narration synthesis, soundtrack, encoding)
- `NARRATION.md` — the complete script with timings
- `preview/` — sample rendered frames (one per scene)
- `audio/` — generated narration audio (created during render)

## Regenerate
```powershell
pip install moviepy edge-tts numpy Pillow
python video/make_video.py            # full MP4 render
python video/make_video.py --frames   # preview frames only
python video/make_video.py --no-audio # visuals only
```

## Notes
- Uses the supplied four-colour palette (deep navy #0A1929, teal #1A6E7A,
  light cyan #A8D8E0, off-white #F6F7F8).
- Includes real 3D-projected animation: a rotating life-graph globe in the
  opening, extruded floating cards in the problem scene, and a rotating
  perspective ring for the OBSERVE→EXECUTE cycle.
- Scene changes use cinematic crossfades; each narration track is synthesized
  to fit its scene and faded in/out so nothing is cut off abruptly.
- All visuals are original programmatic motion graphics — no external stock assets.
- Narration uses a natural online neural voice when available, with an offline
  Windows SAPI fallback. All data shown is synthetic/illustrative.
- The renderer is deterministic: same script → same video.
