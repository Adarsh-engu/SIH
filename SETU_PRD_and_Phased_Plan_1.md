# SETU — Product Requirements Document & Phased Implementation Plan
**Sponsoring PSU: Oil India Limited (OIL) — Department: Oil India Limited, Category: Software, Theme: Smart Automation**
**For: Gemini Antigravity (agentic build assistant)**
**Project type: Hackathon prototype (Smart India Hackathon internal round → national round)**
**Timeline: 6 days to a working, demoable prototype**

---

## HOW TO USE THIS DOCUMENT (read this first, Antigravity)

You are building this project in **strict phase-gated mode**. Follow these rules
for the entire engagement, with no exceptions:

1. This document defines **10 phases**, in order, in the "PHASED IMPLEMENTATION PLAN"
   section below.
2. Work on **exactly one phase at a time**, starting with Phase 1.
3. Before writing, editing, or generating **any code, file, or config** for a phase,
   you must first output a **written implementation plan for that phase only** —
   what you're about to build, the specific files you'll create/modify, key design
   decisions, and any open questions or assumptions you're making. Keep it concise
   and concrete, not generic.
4. After presenting that plan, **STOP and wait**. Do not write, generate, or scaffold
   any code. Do not proceed. Ask: *"Ready for me to build Phase N? Reply 'ok' to proceed,
   or tell me what to change."*
5. Only after the user explicitly replies "ok" (or clearly equivalent affirmative)
   do you begin implementation of that phase.
6. Once a phase's implementation is complete, summarize what was built, list what
   was mocked/simplified vs. fully real, and state clearly what the next phase
   (N+1) will cover — then stop again and wait for the user to say "ok" before
   writing the Phase N+1 plan.
7. Never combine two phases into one build step, even if it seems more efficient.
   Never skip ahead. Never silently expand scope beyond what a phase specifies.
8. If a phase's acceptance criteria can't be met in the time available, say so
   explicitly and propose a scoped-down version rather than quietly cutting corners
   without flagging it.
9. Treat this PRD as the source of truth for scope. If the user's live instructions
   conflict with this document, ask which should take precedence rather than guessing.

---

## 1. PROBLEM STATEMENT (context, for your own grounding — not a build target itself)

This problem statement is sponsored by **Oil India Limited (OIL)**, a Navratna
PSU whose core business is upstream oil & gas exploration and production
(mainly in Assam/Upper Assam/Arunachal Pradesh, plus offshore acreage), a
1157 km crude oil trunk pipeline feeding refineries at Numaligarh, Guwahati,
Bongaigaon and Barauni, gas processing, LPG production, and City Gas
Distribution expansion. Their infrastructure projects are **oilfield and
pipeline projects**: well pad construction, drilling sites, Group Gathering
Stations (GGS), flowline/pipeline tie-ins, and gas processing facilities —
NOT refinery unit construction. Keep all example data, terminology, and demo
framing grounded in this domain, not a generic EPC/refinery scenario.

Infrastructure project schedules (Primavera P6 / MS Project) cascade from macro
milestones (L1) to micro executable activities (L5/L6) across disciplines (Civil,
Piping, Electrical, Instrumentation, HSE). Actual field progress is reported back
via free-text daily reports, spreadsheets, and verbal updates — disconnected from
the plan's activity IDs, inconsistently worded across disciplines (e.g. a
supervisor saying "wellhead installed" vs. the plan's "Wellhead / Christmas Tree
Installation at Well Pad WP-14"), and slow to reconcile. This causes fragmented,
delayed, low-quality data that undermines downstream analytics, and loses
institutional knowledge once a project closes.

## 2. PRODUCT VISION

**Setu** ("bridge") is a real-time planning-to-execution bridge: supervisors log
progress by voice/text like a voice memo; an AI matching engine links messy field
language to the correct L5/L6 schedule activity, even across discipline-specific
terminology and granularity mismatches; planners get a live, consumer-grade
dashboard to review, confirm, and forecast; and every resolved event permanently
feeds an institutional-memory layer so execution knowledge outlives the project.

## 3. USERS

- **Site Supervisor** (primary data source): logs activity start/end via voice or
  text on a phone, at a well pad, GGS, or pipeline right-of-way, sometimes with
  poor connectivity in remote Assam/Arunachal field locations. Not necessarily
  tech-savvy. Wants near-zero friction.
- **Planner / Scheduler** (primary decision-maker): reviews ambiguous matches,
  monitors live progress against baseline, runs what-if scenarios, queries past
  project patterns. Works at a desk, wants clarity and trust in the data.
- **Judge / Evaluator** (hackathon-specific "user"): needs to understand the whole
  system's value and technical depth within a 3-minute demo, without a technical
  explanation of the internals.

## 4. FUNCTIONAL REQUIREMENTS (mapped directly to the PS's stated asks)

| # | Requirement | Feature |
|---|---|---|
| FR1 | Ingest heterogeneous inputs (free text, spreadsheet, voice) | Voice/text capture app + CSV upload endpoint |
| FR2 | Extract activity-level actual start/end events | LLM structured extraction |
| FR3 | Fuzzy-match field descriptions to correct L5/L6 node, handling terminology/granularity mismatch | GraphSAGE + text dual-encoder matcher |
| FR4 | Flag unmatched/new activities for planner review rather than silently dropping | "Needs Review" queue with Confirm/Reject |
| FR5 | Auto-update actual dates in near real time, with confidence score + audit trail per entry | Confidence-branched write path + audit log table |
| FR6 | Produce structured, discipline-tagged actual-progress dataset | Postgres/SQLite schema, exportable |
| FR7 | Support live performance analytics / forecasting | What-if slider panel + re-forecast engine |
| FR8 | Build institutional memory of real execution patterns queryable by future projects | "Ask the Project" memory graph + search |

## 5. NON-FUNCTIONAL REQUIREMENTS

- **Consumer-grade UI**: no raw JSON, no exposed confidence math, no developer
  jargon anywhere in the supervisor or planner-facing surfaces. React + Tailwind,
  clean and animated, not a dev dashboard.
- **Offline tolerance**: voice capture should degrade gracefully with poor
  connectivity (local transcription fallback, queued sync).
- **Auditability**: every schedule update must be traceable to its source entry,
  confidence score, and timestamp — never a silent overwrite.
- **Cost**: entire prototype must run on free-tier tools (see cost section below);
  no required paid dependency.
- **Explainability**: any AI-driven decision shown to a planner must come with a
  plain-English reason, not just a number.

## 6. OUT OF SCOPE FOR THIS PROTOTYPE (explicitly mocked/simplified — do not build for real)

- Real Primavera P6 / MS Project XER/XML read-write integration — mock as a
  "Synced to P6 ✅" stub call.
- Production-grade OCR or ASR — Web Speech API / local Whisper is sufficient
  (explicitly allowed by the PS).
- Multi-tenant auth, RBAC, enterprise security — single-demo-user is fine.
- Full Monte-Carlo-grade probabilistic forecasting — a deterministic/simplified
  critical-path re-forecast reacting to slider input is enough for Phase 7; true
  Monte Carlo is a stretch goal only if time remains.
- Real contractor/reporter trust modeling across many historical projects —
  seed 3 scripted reporter personas with pre-built histories instead.

## 7. SUCCESS CRITERIA FOR THE PROTOTYPE

By the end of Phase 10, a single continuous demo must be walkable in under 3
minutes, using OIL-relevant language throughout (e.g. "wellhead installed at
Well Pad 14", "GGS tank foundation poured", "flowline tied in"): speak/type a
messy report → confirmation card → planner dashboard Needs Review queue updates
live → planner confirms → timeline updates → drag a what-if slider → timeline +
forecast date react instantly → query "Ask the Project" → get a plain-English
answer from seeded institutional memory.

## 8. WHAT COSTS MONEY (and what doesn't)

| Item | Cost | Notes |
|---|---|---|
| Sentence-transformer embeddings | **Free** | Open-source, runs locally (`all-MiniLM-L6-v2`) |
| GraphSAGE / PyTorch Geometric | **Free** | Open-source, local training/inference |
| LLM for extraction + narration | **Free** (recommended: Gemini API free tier, or Groq free tier) | Paid Claude/OpenAI optional, ~$5-20 total if preferred for reliability |
| Voice input | **Free** | Web Speech API (browser-native) or local Whisper |
| Institutional memory store | **Free** | Chroma (local) or Neo4j Community Edition (local/free tier) |
| Hosting for demo | **Free** | Vercel/Render/Railway free tiers are sufficient |
| Total required spend | **$0** | Everything above has a genuinely free path |

Do not introduce a paid dependency at any phase without flagging it to the user
first and confirming it's acceptable.

---

## PHASED IMPLEMENTATION PLAN

### PHASE 1 — Data Foundation
**Goal:** Generate the synthetic schedule graph and labeled field-report dataset
that everything else depends on. **Domain: upstream oil & gas E&P/pipeline
projects (well pads, GGS, flowline tie-ins) modeled on Oil India Limited's
actual operations — not a generic refinery/EPC scenario.**
**Deliverables:**
- `data/schedule_graph.json` — L1→L6 schedule graph for a synthetic "Upper
  Assam Oilfield Development & Pipeline Augmentation Project", 5 disciplines
  (Civil, Piping, Electrical, Instrumentation, HSE), WBS-parent + predecessor/
  successor edges including cross-discipline dependencies. Units include well
  pads, a Group Gathering Station, a crude pipeline extension, a gas processing
  unit, and a City Gas Distribution network segment.
- `data/labeled_reports.json` — synthetic supervisor-jargon phrases labeled with
  true L5 node IDs, using realistic oilfield site language (e.g. "wellhead
  installed", "flowline tied in", "H2S drill done") deliberately different from
  the plan's own formal activity names.
- `data/train_test_split.json` — node-disjoint train/val/test split.
**Acceptance criteria:** Graph has 300+ L5 activities; each activity has 3-5
labeled phrase variants using realistic oilfield site jargon, not paraphrased
plan text.
**[NOTE: this phase is already complete — the data/ folder and generator
scripts (generate_schedule.py, generate_reports.py) are provided alongside this
document. Verify the files exist and inspect a sample before regenerating
anything.]**

### PHASE 2 — Matching Engine (Core IP)
**Goal:** Train and validate the GraphSAGE + text dual-encoder contrastive
matcher.
**Deliverables:**
- `scripts/train_gnn.py` — two-tower model (graph tower via GraphSAGE, text
  tower via sentence-transformer), InfoNCE contrastive loss with same-discipline
  hard negatives.
- `scripts/match_phrase.py` — inference function returning top-k matches +
  confidence.
- Trained checkpoint saved to `data/setu_matcher.pt`.
**Acceptance criteria:** Test-set (unseen activities) top-3 accuracy meaningfully
above random baseline; confidence threshold correctly routes low-confidence
matches to "needs review" in a manual spot-check of 10 example phrases.

### PHASE 3 — Backend API Core
**Goal:** Wrap the matcher behind a real API with the extraction + confidence-
branch logic and persistence.
**Deliverables:**
- FastAPI app with endpoints: `POST /report` (raw text/voice transcript in →
  extracted + matched + persisted event out), `GET /events`, `GET /needs-review`,
  `POST /events/{id}/confirm`, `POST /events/{id}/reject`.
- LLM extraction step (raw phrase → structured JSON: activity_phrase, discipline,
  action, timestamp) in front of the matcher.
- DB schema (SQLite for prototype) with an audit-trail table: every event stores
  raw input, extracted JSON, matched node_id, confidence, decision
  (auto-updated/needs-review), timestamp, and reviewer action if any.
**Acceptance criteria:** A `curl` POST of a raw phrase produces a correctly
matched, confidence-scored, audit-logged DB row end-to-end.

### PHASE 4 — Real-Time Layer
**Goal:** Make the backend push live updates instead of requiring polling.
**Deliverables:** WebSocket endpoint broadcasting new events/state changes to
connected clients; basic connection handling for the two frontend surfaces
(supervisor app, planner dashboard).
**Acceptance criteria:** Two browser tabs open against the backend — an event
posted via one shows up live in the other without a page refresh.

### PHASE 5 — Supervisor Capture App (Consumer UI, Surface 1)
**Goal:** Build the voice/text logging PWA.
**Deliverables:** React + Tailwind mobile-first single screen — mic button,
waveform, editable transcript bubble, plain-English confirmation card after
submit. No AI/technical vocabulary exposed anywhere on this screen.
**Acceptance criteria:** A non-technical person can log an entry without
instructions, entirely by tapping the mic and speaking.

### PHASE 6 — Planner Dashboard: Needs Review (Consumer UI, Surface 2a)
**Goal:** Build the review queue.
**Deliverables:** Clean card-based queue UI showing ambiguous matches with
plain-language description, Confirm/Reject buttons, live-updating via the
WebSocket from Phase 4.
**Acceptance criteria:** Confirming/rejecting an entry updates the DB and
removes it from the queue live, without a refresh.

### PHASE 7 — Planner Dashboard: Live Timeline + What-If Sliders (Consumer UI, Surface 2b)
**Goal:** Build the visual centerpiece — a Gantt-style timeline that recolors
as data lands, with slider-driven re-forecasting.
**Deliverables:** Horizontal timeline strip grouped by discipline; 2-3 sliders
(e.g. "piping delay days", "crew productivity"); a simplified critical-path
re-forecast function triggered on slider change; one-sentence LLM-generated
plain-English explanation of why the forecast date moved.
**Acceptance criteria:** Dragging a slider visibly recolors the timeline and
updates the forecast date and explanation sentence within ~1 second.

### PHASE 8 — Institutional Memory ("Ask the Project")
**Goal:** Build the searchable memory layer.
**Deliverables:** Seed 10-15 hand-written past-project pattern records (activity,
duration, deviation-cause, discipline) into a local vector store (Chroma) or
graph store; a search bar UI; retrieval + LLM-generated plain-English answer
with source tags.
**Acceptance criteria:** A natural-language query about a discipline/delay
pattern returns a genuinely relevant, cited answer from the seeded records.

### PHASE 9 — Trust Layer + Consumer-Grade Polish Pass
**Goal:** Add the reporter-trust dimension and do a full UI polish pass across
all screens.
**Deliverables:** Simple Beta-distribution trust score per (scripted) reporter
persona, shown only as a 3-icon confidence badge (green/amber/red), never as
raw numbers; animation pass (Framer Motion) on timeline recoloring and card
transitions; consistent design system across both frontends.
**Acceptance criteria:** All screens feel like one coherent product, not
prototyped fragments; no raw ML output (embeddings, similarity scores, model
names) is ever visible to an end user.

### PHASE 10 — Demo Hardening
**Goal:** Make the exact 3-minute demo path bulletproof.
**Deliverables:** Scripted demo dataset seeded so the walkthrough always
produces the intended result live; a fallback pre-recorded video/backup path
in case of live-demo failure; final rehearsal checklist.
**Acceptance criteria:** The full demo path (voice log → confirmation queue →
timeline update → slider drag → memory-bank query) runs cleanly 3 times in a
row without manual intervention.

### PHASE 11 — Authentication & Role-Based Access Control (RBAC)
**Goal:** Implement a login system to route different stakeholders to their specific views.
**Deliverables:**
- Mock login page for the Hackathon (Supervisor, Planner, Admin).
- Route protection (Supervisors only see capture, Planners see graph, Admins see analytics).
**Acceptance criteria:** Users are correctly redirected to their designated dashboard based on their role upon login.

### PHASE 12 — Global Audit Logging & Admin Dashboard
**Goal:** Track every system action and present it in a secure Admin view for accountability.
**Deliverables:**
- Extended database schema to track `user_id` and `user_name` for every action.
- A chronological system activity feed (Audit Log Dashboard) for transparency.
**Acceptance criteria:** The Admin dashboard displays a real-time, tamper-evident log of who submitted, confirmed, or rejected a report.

---

**End of document. Antigravity: begin by producing the Phase 1 implementation
plan now, then stop and wait for "ok."**
