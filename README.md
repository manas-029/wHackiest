# LIFEGRAPH AI

**Your Life. Your Intelligence. Your AI.**

An AI-powered Personal Intelligence Operating System that understands, organizes, optimizes and assists in managing every aspect of a person's life — with the user always in control.

**Ideathon Track 3 — Know Thyself: Your Data. Your Intelligence.**

---

## 1. The Problem

Information about a person's life is scattered across calendars, email, task apps, finance apps, phones and social platforms. People manually maintain schedules, remember deadlines, decide what to do with free time, track spending and make everyday decisions from fragmented information. Existing apps solve isolated problems; they rarely build a unified understanding of an individual.

## 2. The Idea

LIFEGRAPH AI automatically gathers information from **authorized** sources and builds a continuously evolving understanding of the user's responsibilities, preferences, habits, goals and available time. It then organizes schedules, manages tasks, recommends activities, predicts problems and executes approved actions.

**Core operating cycle**

```
OBSERVE  →  UNDERSTAND  →  ANALYZE  →  PREDICT  →  RECOMMEND  →  EXECUTE
```

**Zero-input intelligence** does not mean unrestricted access. Data is collected only with authorization; missing information is inferred from connected sources and documents first, and the user is asked only for what actually affects planning.

## 3. The Six Intelligence Domains

| Domain | Purpose |
|---|---|
| **Academic** | Timetables, assignments, deadlines, attendance, study patterns, performance trends, automatic study sessions |
| **Productivity** | Time allocation, completion tracking, peak-hour detection, deadline risk, workload balancing, reports |
| **Financial** | Expense/income tracking, categorization, budgets, subscriptions, savings, unusual expense detection, what-if simulations |
| **Digital** | Screen time, app/social usage, notification patterns, distraction detection, late-night usage |
| **Environmental** | Weather, air quality, noise, commute, workspace conditions, location-based routines |
| **Social** | Events, commitments, conflict detection, work-life balance, relationship reminders |

The **Cross-Domain Engine** builds a personal relationship graph across these domains, with evidence, confidence and provenance. It reports associations, never claims causation.

## 4. Central AI Assistant (permission-based)

- **Conversational intelligence** — natural voice/text questions answered from real user data.
- **Contextual awareness** — schedules, tasks, deadlines, preferences, finances, goals, history.
- **Autonomous execution** — create tasks/events, organize documents, draft emails, schedule reminders, always with approval for sensitive actions.
- **Predictive intelligence** — deadline risk, overload, insufficient preparation, budget overruns, conflicts.
- **Proactive assistance** — relevant, configurable, non-intrusive suggestions.

Autonomy levels: **1 Observe → 2 Recommend → 3 Execute**.

## 5. Key Modules

- **Smart Schedule Manager** — recurring/one-time events, college/office hours, travel, meals, sleep, availability, conflict detection.
- **Intelligent To-Do Manager** — natural-language, voice, PDF/email extraction, subtasks, priority, workload estimates, dependencies, rescheduling.
- **Adaptive Information Collection Engine** — extract from documents and connected data, ask only genuinely missing questions.
- **Free-Time Optimizer** — finds gaps and proposes realistic plans with breaks; user can accept, reject or modify.
- **Preference & Interest Intelligence** — learns likes/dislikes behaviourally and conversationally; user-controlled memory.
- **Personal Decision Intelligence** — evidence-based pros/cons using real personal context.
- **What-If Simulation Engine** — statistical simulations (not LLM-invented numbers) with assumptions and uncertainty.
- **Stress & Emotional Pattern Intelligence** — confidence-aware pattern detection, no emotion diagnosis.
- **Weekly Life Report, Smart Notifications, Personal Memory, Activity Recommendations**.

## 6. Architecture

```
Layer 1  Data Ingestion        authorized APIs, documents, device data
Layer 2  Data Processing       clean, normalize, categorize, synchronize
Layer 3  Personal Context      schedules, preferences, responsibilities, history
Layer 4  Intelligence Engine   patterns, relationships, predictions
Layer 5  AI Agent Engine       intent, context retrieval, multi-step workflows, approvals
Layer 6  Scheduling & Sim       feasible schedules, optimization, what-if models
Layer 7  Execution Engine       approved actions through connected services
Layer 8  User Interface         dashboard, chat, calendar, reports, What-If Lab
```

**Recommended stack:** React + Chart.js · Django + DRF · PostgreSQL · Gemini API · LangGraph · Pandas/NumPy/Scikit-learn · NetworkX · SciPy · speech APIs · Google/Microsoft calendars, Gmail, weather APIs · Vercel + Render.

## 7. Privacy & Control

Explicit per-source permission, encryption in transit and at rest, domain-scoped access, data export/deletion, retention controls, no unnecessary collection, no sharing without consent, approval for sensitive external actions, and clear separation of measured data vs AI estimates. The prototype uses **synthetic data only** and degrades gracefully when integrations are unavailable — it never fabricates missing information.

## 8. 24-Hour Hackathon Scope

**P0 (must):** conversational assistant, smart schedule, intelligent to-do, natural-language task creation, adaptive follow-ups, PDF deadline/workload extraction, free-time detection, prioritization, personalized recommendations, approval-based execution.

**P1 (if time):** preference profile, six-domain dashboard, cross-domain insights, what-if simulation, weekly report.

**P2 (future):** full integrations, background sync, advanced predictive models, wearables, advanced agent workflows.

**Ideal demo:** upload assignment PDF → extract details → ask only missing info → create task → find free time → recommend sessions → answer "what should I do this evening?" → user approves → create calendar events/reminders → update intelligence.

## 9. Repository Contents

```
.
├── docs/
│   ├── product-brief.md            vision, domains, MVP scope
│   ├── architecture.md             eight layers, trust boundaries, stack
│   ├── demo-script.md              ideal 10-step pitch demonstration
│   └── video-production.md         renderer pipeline and design system
├── video/
│   ├── make_video.py               deterministic video renderer
│   ├── NARRATION.md                timed script for the video
│   ├── README.md                   video-specific notes
│   ├── preview/                    one sample frame per scene
│   └── audio/                      generated narration tracks
├── LIFEGRAPH_AI_Explainer.mp4       3-minute animated pitch video (1080p, 30 fps)
├── README.md                       this document
├── CHANGELOG.md                    version history
├── LICENSE                         MIT license
├── start.bat                       open the explainer video on Windows
└── .editorconfig / .gitattributes / .gitignore
```

Download the complete folder as `LIFEGRAPH_AI_Project.zip` (see the root folder or Desktop copy).

Further reading: [Product brief](docs/product-brief.md) · [Architecture](docs/architecture.md) · [Demo script](docs/demo-script.md) · [Video production](docs/video-production.md)

### The explainer video

- **Runtime:** 3:00 · **Resolution:** 1920×1080 · **Frame rate:** 30 fps
- **Format:** H.264 video + AAC stereo narration and ambient soundtrack
- **Visual style:** your four-colour palette — `#0A1929`, `#1A6E7A`, `#A8D8E0`, `#F6F7F8`
- **3D elements:** rotating life-graph globe, extruded floating cards, perspective cycle ring
- **Motion:** cubic easing, sliding entrances, camera drift/push-in, crossfades, depth particles
- **Content:** problem → zero-input cycle → AI assistant → six domains → schedule + free time → smart tasks → cross-domain/what-if → control + privacy → closing vision

Regenerate it:

```powershell
pip install moviepy edge-tts numpy Pillow
python video/make_video.py             # full MP4
python video/make_video.py --frames    # preview frames only
python video/make_video.py --no-audio  # visuals only
```

All video visuals are original programmatic motion graphics; no stock assets are used.

---

**Final vision:** an intelligent system that understands your responsibilities, remembers your preferences, manages your time, recommends meaningful activities, anticipates problems and performs approved actions — while keeping you in control.
