# Explainer Video Production

## Output
`LIFEGRAPH_AI_Explainer.mp4` — 3:00, 1920×1080, 30 fps, H.264 + AAC.

## Pipeline
`video/make_video.py` renders every frame programmatically with Pillow and NumPy, synthesizes narration with a neural TTS voice, adds a generated ambient soundtrack, and encodes with MoviePy/FFmpeg.

```
python video/make_video.py             # full render
python video/make_video.py --frames    # preview frames
python video/make_video.py --no-audio  # silent render
```

## Design system
- Palette: `#0A1929` deep navy, `#1A6E7A` teal, `#A8D8E0` light cyan, `#F6F7F8` off-white.
- Logical canvas 1280×720, upscaled with Lanczos; slow camera drift and push-in.
- Cubic easing, slide entrances, spring overshoot, 0.7 s crossfades, depth particles, vignette.
- 3D: rotating wireframe life-graph globe, extruded floating app cards, perspective cycle ring.

## Audio
Each narration line is synthesized at a scene-specific rate so it fits its scene, then faded in and out. A synthesized ambient pad sits underneath at low volume.

## Scene timeline
| Time | Scene |
|---|---|
| 0:00–0:12 | One AI / your whole life |
| 0:12–0:30 | The real-world problem |
| 0:30–0:48 | Core cycle |
| 0:48–1:05 | Central AI assistant |
| 1:05–1:33 | Six intelligence domains |
| 1:33–1:52 | Schedule + free-time optimizer |
| 1:52–2:11 | Smart tasks / PDF extraction |
| 2:11–2:29 | Cross-domain + what-if |
| 2:29–2:46 | Privacy and control |
| 2:46–3:00 | Closing vision |
