# Project Memory: Tel-Setu Handover Document

**Last Updated:** Phase 14 (In Progress)

This document serves as the absolute brain-dump of the current state of the Tel-Setu project. If you are a new agent taking over this workspace, read this entire file carefully to understand the exact context, architecture, constraints, and immediate next steps.

---

## 1. Core Architecture & Philosophy
- **Domain Context:** This is an AI-augmented daily reporting system built for Oil India Limited (OIL) infrastructure projects (well pads, flowlines, GGS).
- **Core Philosophy:** *"AI recommends; humans verify consequential updates."* We **never** auto-approve high-stakes schedule changes (like sequence conflicts).
- **Name Policy:** Never use the names "SiteSync" or "Team CoDelulu".
- **Reference Docs:** We strictly adhered to the domain constraints mapped out in the research documents provided by the user (`OIL_SIH_Project_Research_Document.docx`, `Primavera_P6_Research.docx`, `SIH26122_Master_Research_Compendium_v2 (1).docx`). These dictated our WBS structure, terminologies, and the exact constraints of Primavera P6 environments.
- **The Roadmap:** We follow `SETU_PRD_and_Phased_Plan.md` strictly. We are currently implementing **Phase 14**.

---

## 2. What is Already Built (Phases 1-13)
The system is fundamentally operational as an end-to-end prototype:
- **`generate_schedule.py`**: Generates `data/schedule_graph.json`, which acts as the source-of-truth DAG of the project. Nodes have `planned_quantity`, `unit`, and `predecessor` edges.
- **`database.py`**: A SQLite/SQLModel setup (`setu.db`). Stores the `EventAudit` table which records every submitted report.
- **`llm_extractor.py`**: Uses `gemini-3.6-flash` (we had to upgrade from `2.5-flash` due to a 404 error) to parse raw, messy text reports from the field into structured JSON (activity, discipline, quantity, unit, etc). It includes a deterministic mock fallback if the API key fails.
- **`matcher_service.py`**: A fuzzy semantic matching engine using `sentence-transformers/all-MiniLM-L6-v2`. It compares the LLM's extracted activity phrase against the L5 nodes in the schedule graph.
- **Phase 13 (Dependency Validation)**: In `matcher_service.py`, we implemented `check_dependencies(matched_node_id, completed_node_ids)`. In `main.py`'s `POST /report` flow, if a successor task is reported before its predecessors are completed, it throws a "Sequence Conflict", downgrades the match to `needs-review`, and the UI explicitly renders this red warning in the Planner Dashboard.

---

## 3. Current State: Phase 14 (Quantity-Based Progress)
The goal of Phase 14 is to move from binary (Pending/Complete) status to **cumulative, quantity-based percent-complete tracking** (e.g. reporting 3 km of a 10 km flowline = 30%).

### What was just completed in the final session:
1. Updated `database.py`: Added `actual_quantity` and `percent_complete` to the `EventAudit` model.
2. We wiped/deleted `setu.db` using PowerShell so that `init_db()` will recreate the database with the new schema columns on the next startup.
3. Updated `main.py`: Modified the `submit_report` endpoint to handle cumulative progress. It loops over all previously confirmed events for the matched node, sums their `actual_quantity`, adds the newly reported quantity, calculates `percent_complete = (cumulative / planned) * 100`, and passes it to `insert_event`.
4. Updated `main.py`: Modified `/schedule-graph` to attach the highest confirmed `percent_complete` to the node payload so the frontend can render it.

### Immediate Next Steps for the Next Agent:
You are picking up exactly where I left off in Phase 14. 
The backend is ready, but the frontend needs to be wired to display these new `percent_complete` numbers. 

**Your immediate tasks:**
1. **Start the servers**: Run `npm run dev` (in `frontend/`) and `uvicorn main:app --reload` (in `backend/`).
2. **Update `frontend/src/app/planner/page.tsx`**: Update the `SetuEvent` TypeScript interface to include `percent_complete?: number`. Render a "Progress: X%" badge on the Needs Review card if this value is present.
3. **Update `frontend/src/components/ScheduleGraph.tsx`**: Update the node components to visually represent partial progress (e.g., a progress bar or text showing the percentage) rather than just a binary color change.
4. **Update `frontend/src/app/page.tsx`**: Update the Supervisor App's success card to display the computed progress percentage to the reporter.
5. **Verify**: Submit a report with a partial quantity (e.g. "welded 25 joints"), confirm it calculates the correct partial percentage against the node's `planned_quantity`. Submit a second report for the same node ("welded 5 more joints") and verify that the cumulative addition works perfectly.

Once Phase 14 is verified, mark it complete in `SETU_PRD_and_Phased_Plan.md` and move to Phase 15. Good luck!
