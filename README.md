# Setu — Data & Matching Model (Day 1-2 deliverables)

This folder is what you build on top of at home. Everything here is generated
and verified end-to-end — you're not starting from a blank folder.

## What's in here

```
data/
  schedule_graph.json      # 433 nodes / 762 edges, L1-L6 EPC schedule graph
                            # (Project -> Unit -> Discipline -> Sub-system -> 341 L5 activities)
                            # across Civil, Piping, Electrical, Instrumentation, HSE
  labeled_reports.json      # 1,342 synthetic "supervisor phrase" -> true L5 node_id pairs
                            # deliberately uses different wording/jargon than the plan
                            # (this is the "spool erected" vs "Erect Line 24"-XX" gap)
  train_test_split.json     # NODE-DISJOINT train/val/test split (239/51/51 activities)
                            # -- tests generalization to UNSEEN activities, not memorization
  setu_matcher.pt           # trained model checkpoint (GraphSAGE + text projection head)

scripts/
  generate_schedule.py      # regenerate/expand the schedule graph (edit templates to add
                            # more units/disciplines/activity types)
  generate_reports.py       # regenerate/expand labeled phrases (edit ACTION_SYNONYMS to
                            # add more jargon variety per discipline)
  train_gnn.py               # trains the two-tower GraphSAGE + text contrastive matcher
  match_phrase.py             # inference: query the trained model with a new phrase
```

## The architecture (what's actually novel here)

1. **Graph tower**: the schedule is NOT a flat list — it's a graph (WBS parent/child
   edges + predecessor/successor edges, including cross-discipline dependencies like
   Civil foundation -> Piping erection). A 2-layer GraphSAGE propagates structural
   context into every node's embedding, so the model can disambiguate using "what's
   around this activity in the plan," not just the words in its name.
2. **Text tower**: incoming field-report phrases are embedded with the same kind of
   encoder and projected into the same vector space as the graph tower.
3. **Contrastive training**: InfoNCE loss with HARD NEGATIVES = other activities in
   the SAME discipline (the genuinely confusing case — e.g. two different piping
   lines) plus in-batch negatives.
4. **Inference**: cosine similarity + softmax -> confidence score. Below threshold
   (0.35, tune this) -> routes to "Needs Review" instead of silently auto-updating
   OR silently dropping — this directly satisfies the PS's audit-trail requirement.

## IMPORTANT: run this at home first, before the hackathon

This sandbox's network blocks `huggingface.co` (only package registries are
whitelisted), so `train_gnn.py` automatically fell back to a TF-IDF+SVD text
encoder to prove the pipeline runs end-to-end. **Your home machine has normal
internet access — the script will automatically use the real pretrained
`sentence-transformers/all-MiniLM-L6-v2` model instead**, which actually
understands synonymy/paraphrase (TF-IDF can't — it only matches shared words).
Expect a real accuracy jump once that swap happens automatically.

Steps:
```bash
pip install -r requirements.txt
python3 scripts/generate_schedule.py     # optional: re-run if you edit templates
python3 scripts/generate_reports.py      # optional: re-run if you edit templates
python3 scripts/train_gnn.py             # trains in a few minutes on CPU
python3 scripts/match_phrase.py "spool erected on the 24 inch line"
```

## What to do next (Day 2-3 of your plan)

1. **Sanity-check accuracy** with the real sentence-transformer encoder — check
   val/test top-1 and top-3 accuracy printed during training. If test (unseen
   activities) top-3 is above ~50-60%, you have a genuinely working matcher —
   good enough to wire into the demo.
2. **Tune `CONFIDENCE_THRESHOLD`** in `match_phrase.py` against your val set so
   the auto-update / needs-review split feels right for the demo script you plan
   to run on stage.
3. **Expand the synthetic data if needed** — if accuracy is too low, the fastest
   lever is adding MORE and MORE VARIED synonyms per action in
   `ACTION_SYNONYMS` (generate_reports.py) rather than changing the model —
   more realistic paraphrase diversity is what actually teaches the model to
   generalize.
4. **Wire this into FastAPI** — `match_phrase.py`'s `match()` function is your
   `/api/log-report` endpoint's core call. Wrap it, add the LLM extraction step
   in front of it (raw voice/text -> structured phrase), and the confidence-
   branch logic (auto-update vs. Needs Review write) behind it.
5. Move on to the frontend screens once this endpoint returns clean JSON.

## Extending the schedule graph for a stronger demo

If you want a bigger/more impressive-looking graph for the live demo (Cytoscape/D3
visualization), just bump the ranges in `generate_schedule.py`
(`n_subsystems`, `n_activities` per subsystem) and re-run both generator scripts
— the pipeline downstream doesn't need any code changes.
