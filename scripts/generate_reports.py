"""
generate_reports.py
Generates synthetic, messy, supervisor-style "field report" phrases for each L5
schedule activity -- deliberately using different wording, abbreviations,
granularity, and jargon than the plan's own activity name (this is the
"spool erected" vs "Erect Line 24"-XX" gap named in the problem statement).

Output: ../data/labeled_reports.json
  [ {phrase, true_node_id, discipline, action}, ... ]

Also outputs ../data/train_test_split.json with node-disjoint train/val/test
splits (so evaluation reflects generalization to unseen phrasing, not memorization).
"""
import os
import json
import random

random.seed(7)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "..", "data", "schedule_graph.json")) as f:
    schedule = json.load(f)

nodes_by_id = {n["id"]: n for n in schedule["nodes"]}
l5_nodes = [n for n in schedule["nodes"] if n["level"] == 5]

# Jargon/action synonyms keyed by the template "description/short" tag assigned
# during generation -- this is what lets the same underlying activity be phrased
# many different ways, the way different supervisors/contractors actually talk.
ACTION_SYNONYMS = {
    "Site Levelling": ["site levelled", "levelling done", "grading completed at"],
    "Excavation": ["dug out", "excavated", "excavation done for", "dug the pit for"],
    "PCC": ["PCC laid", "plain cement concrete poured for", "PCC done at"],
    "Rebar": ["rebar fixed", "reinforcement tied", "steel fixing completed for", "rebar work done"],
    "Formwork": ["shuttering done", "formwork fixed", "centering done for"],
    "Concrete Pour": ["concreting done", "poured concrete for", "concrete casting completed"],
    "De-shuttering": ["shuttering removed", "de-shuttered", "formwork stripped"],
    "Backfill": ["backfilled", "filling done around"],
    "Road Construction": ["approach road done", "road laid near", "road construction completed at"],
    "Fencing": ["fencing done", "boundary wall completed", "fencing put up at"],
    "Fabrication": ["spool fabricated", "fab done for", "fabrication completed"],
    "Erection": ["flowline erected", "erected the line", "pipe erected", "erection completed for"],
    "Fit-up": ["fit-up done", "joints fitted up", "fit up completed"],
    "Welding": ["welding done", "welded the joint", "weld completed"],
    "NDT": ["RT done", "radiography completed", "NDT cleared", "x-ray done"],
    "Hydro Test": ["hydro test done", "hydro passed", "pressure tested", "hydro testing completed"],
    "Wellhead Installation": ["wellhead installed", "X-mas tree fixed", "christmas tree installed", "wellhead set up at"],
    "Tie-in": ["tie-in done", "tied in the line", "flowline tied in at"],
    "Cathodic Protection": ["CP test done", "cathodic protection tested", "CP survey completed"],
    "Pigging Station": ["pigging station tied in", "pig launcher fixed", "pig trap installed"],
    "Coating": ["coating done", "line wrapped", "anti-corrosion coating completed"],
    "Tray Installation": ["cable tray fixed", "tray installed", "tray laid"],
    "Cable Laying": ["cable pulled", "cable laid", "cabling done"],
    "Termination": ["glanding done", "termination completed", "cable terminated"],
    "Megger Test": ["megger done", "insulation resistance test done", "megger test cleared"],
    "Equipment Installation": ["equipment installed", "placed and aligned", "installation completed"],
    "Panel Wiring": ["panel wired", "wiring completed"],
    "Earthing": ["earthing done", "earth pit connected", "earthing completed"],
    "Area Lighting": ["lighting fixed", "area lights put up", "lighting installation done"],
    "Instrument Installation": ["instrument mounted", "instrument fixed", "installed the instrument"],
    "Tubing": ["tubing done", "impulse line connected"],
    "Loop Check": ["loop checked", "loop test cleared", "loop checking done"],
    "Calibration": ["calibrated", "calibration completed"],
    "JB Termination": ["JB terminated", "junction box wired"],
    "SCADA Integration": ["SCADA hooked up", "RTU integrated", "SCADA/RTU commissioned"],
    "Flow Computer": ["flow computer commissioned", "flow computer set up", "FC commissioning done"],
    "Pressure Transmitter": ["PT fixed at wellhead", "pressure transmitter installed", "PT mounted"],
    "Induction": ["induction conducted", "safety orientation done"],
    "Scaffold Inspection": ["scaffold inspected", "scaffold tag issued"],
    "PTW": ["permit issued", "PTW closed", "work permit given"],
    "Fire Watch": ["fire watch posted", "fire watcher deployed"],
    "HIRA": ["HIRA done", "risk assessment completed"],
    "PPE Audit": ["PPE checked", "PPE audit done"],
    "H2S Drill": ["H2S drill conducted", "gas detector calibrated", "H2S mock drill done"],
    "BOP Drill": ["BOP drill conducted", "well control drill done", "blowout drill completed"],
}

FILLERS_START = ["", "Today ", "As of shift end, ", "Update: ", "Sir, ", "FYI - ", "Site note: "]
FILLERS_END = ["", ".", ", all good", ", no issues", ", ready for next stage", ", team moved to next area"]

DISCIPLINE_HINT_DROP_PROB = 0.7  # supervisors rarely say the discipline name explicitly


def strip_technical_detail(name, short):
    """Simulate a supervisor dropping precise plan-level detail (tag numbers etc)."""
    # crude heuristic: keep only rough noun phrase, drop the specific code
    import re
    stripped = re.sub(r'[A-Z]{1,4}-?\d+', '', name)
    stripped = re.sub(r'\d+"', '', stripped)
    stripped = re.sub(r'\s+', ' ', stripped).strip(' -,')
    return stripped


records = []
for n in l5_nodes:
    short = n["description"]
    activity_id = n.get("activity_id", "")
    qty = n.get("planned_quantity", "")
    unit = n.get("unit", "")
    
    synonyms = ACTION_SYNONYMS.get(short, [short.lower()])
    n_variants = random.randint(3, 5)
    for i in range(n_variants):
        syn = random.choice(synonyms)
        base = strip_technical_detail(n["name"], short)
        
        # Inject activity_id and qty occasionally
        prefix = random.choice(FILLERS_START)
        suffix = random.choice(FILLERS_END)
        
        if activity_id and i == 0:  # 1 variant has exact ID
            base = f"{base} (Ref: {activity_id})"
        if qty and unit and i == 1: # 1 variant has quantity
            base = f"{base}, {qty} {unit}"
            
        phrase = f"{prefix}{syn} {base}{suffix}".strip()
        phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
        records.append({
            "phrase": phrase,
            "true_node_id": n["id"],
            "discipline": n["discipline"],
            "short_action": short,
        })

random.shuffle(records)

with open(os.path.join(BASE_DIR, "..", "data", "labeled_reports.json"), "w") as f:
    json.dump(records, f, indent=2)

# Node-disjoint split: some ACTIVITY NODES are held out entirely for val/test,
# so we measure generalization to unseen (but structurally similar) activities --
# this is the honest way to validate a matching model, not a random row split.
node_ids = list({n["id"] for n in l5_nodes})
random.shuffle(node_ids)
n_test = max(1, int(0.15 * len(node_ids)))
n_val = max(1, int(0.15 * len(node_ids)))
test_ids = set(node_ids[:n_test])
val_ids = set(node_ids[n_test:n_test + n_val])
train_ids = set(node_ids[n_test + n_val:])

split = {"train_node_ids": list(train_ids), "val_node_ids": list(val_ids), "test_node_ids": list(test_ids)}
with open(os.path.join(BASE_DIR, "..", "data", "train_test_split.json"), "w") as f:
    json.dump(split, f, indent=2)

print(f"Generated {len(records)} labeled report phrases for {len(l5_nodes)} L5 activities.")
print(f"Split: {len(train_ids)} train nodes / {len(val_ids)} val nodes / {len(test_ids)} test nodes.")
print("\nSample records:")
for r in records[:8]:
    print(" -", r["phrase"], "=>", r["true_node_id"], f"({r['discipline']})")
