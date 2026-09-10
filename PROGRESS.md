# Project Setu - Memory & Progress Tracker

## Current Status: ⏸️ Paused (Ready for Phase 12)
We are building the **Setu Prototype** for the Smart India Hackathon (Oil
India Limited problem statement). The project follows a phase-gated
implementation plan (see `SETU_PRD_and_Phased_Plan.md`), now extended to 18
phases, with priorities reset based on domain research findings.

### Completed Phases
- [x] **Phase 1: Data Foundation**
- [x] **Phase 2: Matching Engine (Core IP)**
- [x] **Phase 3: Backend API Core**
- [x] **Phase 4: Real-Time Layer**
- [x] **Phase 5: Supervisor Capture App**
- [x] **Phase 6: Planner Dashboard (Surface 2)**
- [x] **Phase 7: Interactive Schedule Visualization**
- [x] **Phase 8: Analytics & Insights Layer**
- [x] **Phase 9: Legacy System Integration (Export Engine)**
  - Backend endpoint generates a `.csv` dump of `schedule_graph.json`
    overlaid with the latest `event_audit` statuses.
  - "Export to CSV" button on the Planner Dashboard for Primavera P6 / Excel
    import.
  - *Research note: this satisfies the "OIL integration posture"
    differentiator honestly — a bridge to Primavera/Excel — without
    overclaiming direct TIEMCHART/SAP integration, which domain research
    explicitly warns against.*
- [x] **Phase 10 / 11: "What-If" Simulation Engine (Delay Predictor)**
  - Glassmorphic Simulation Control Panel on the Planner DAG.
  - Live Breadth-First Search (BFS) graph traversal visualizing cascading
    delays (orange/red glowing nodes).
  - *This fully covers what was scoped as "Phase 11: Delay Predictor" in the
    PRD — no further action needed there. It also partially covers Phase 17
    (Explainable Delay Propagation Chain) — revisit later to add per-link
    plain-English reasons if time allows.*

## ⚠️ REPRIORITIZATION (based on OIL/Primavera domain research review)

A generic **Auth/RBAC system** and **admin audit log** were previously queued
as the next two phases. These have been **deprioritized** — they are
production-readiness features any competent team will have some version of,
not the differentiators the domain research identifies.

Per the research's own comparison against prior published academic work on
this exact schedule-linking problem, the gaps that separate a winning
submission are:
1. **Evidence-grounded matching with visible reasoning** (not yet built)
2. **Dependency-consistency checking** (not yet built)
3. **Offline-first capture** (not yet built — directly relevant given OIL's
   remote Assam/Arunachal/offshore field sites)

None of these existed in the RBAC/audit-log plan. They are being prioritized
instead.

**A lightweight mock login (3 role buttons — Supervisor / Planner / Admin, no
real backend security, just view-routing) is fine to keep as a cheap demo
nicety if time allows**, but full RBAC/audit-logging is no longer substantive
next-session work.

### Next Session: Phase 12 (build first)
**Phase 12: Multi-Signal Evidence-Grounded Matching**
- **PREREQUISITE — do this first:** the current schedule generator only
  produces activity *names*, no stable Activity IDs or quantity/unit fields.
  Before writing any matching logic:
  1. Extend `generate_schedule.py` to add `activity_id` (e.g. `WELD-1042`
     style) and `planned_quantity` + `unit` to every L5 node.
  2. Regenerate `schedule_graph.json` and `labeled_reports.json`.
  3. Confirm the updated data with the user before proceeding.
- **Goal:** Upgrade the matcher from semantic-similarity-only to a composite
  score combining: exact Activity ID mention (strongest) > semantic
  similarity > WBS/discipline context > location/chainage (if applicable) >
  quantity/unit match > date-window fit.
- **Key feature:** a "match reasoning" panel shown to the planner, listing
  which specific clues contributed to the confidence score. This directly
  answers the research's flagged toughest anticipated judge question: *"Why
  did your system map this report to this specific activity?"*

### Then: Phase 16
**Phase 16: Offline-First Capture + Sync**
- **Goal:** Supervisor app works with zero connectivity.
- **Key features:** local event queue (IndexedDB) on the PWA; automatic
  background retry/sync on reconnect; a visible "queued, not yet synced"
  indicator.
- **Demo beat:** log an entry in airplane mode → reconnect → event appears on
  the planner dashboard automatically, with no manual re-entry.

### After that: Phase 13 (dependency-consistency validation), then stretch
goals 14/15/17 if time remains, 18 only if everything else is solid. See the
PRD for full detail on each.

## Important Directives
1. **Strict Phasing:** Do not write code for the next phase until an
   implementation plan is presented and approved.
2. **Terminal Execution:** The user prefers to run any terminal commands
   themselves to monitor progress. Provide the commands in the chat.
3. **Core Rules Active:** Always adhere strictly to the rules defined in
   `GEMINI.md` (Kinetic UI and Antigravity Principles).
4. **Memory Updates:** Update this memory file at the end of every completed
   phase.
5. **Domain grounding:** Every new phase should stay traceable to a specific
   need identified in the OIL/Primavera research documents — avoid adding
   generic SaaS-dashboard features (auth, admin panels, settings pages) ahead
   of features that demonstrate the actual planning-to-execution bridge
   problem being solved.
