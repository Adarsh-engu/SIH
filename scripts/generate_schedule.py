"""
generate_schedule.py
Generates a synthetic but structurally realistic L1-L6 EPC/Infrastructure project
schedule graph, modeled on real-world WBS conventions (similar to what you'd see
exported from Primavera P6 / MS Project for a refinery, power, or industrial
infra project). Covers 5 disciplines: Civil, Piping, Electrical, Instrumentation, HSE.

Output: ../data/schedule_graph.json
  {
    "nodes": [ {id, name, discipline, level, parent_id, unit, description}, ... ],
    "edges": [ {source, target, type}, ... ]   # type: "wbs_parent" | "predecessor"
  }
"""
import json
import random
import itertools
import os

random.seed(42)

# ---------------------------------------------------------------------------
# L1-L2 structure: Project -> Area/Field (typical of upstream oil & gas E&P
# infrastructure projects -- modeled on Oil India Limited's actual operations:
# well pads, drilling, Group Gathering Stations, crude oil trunk pipelines,
# in the Assam/Upper Assam oilfield belt)
# ---------------------------------------------------------------------------
PROJECT_NAME = "Upper Assam Oilfield Development & Pipeline Augmentation Project"

UNITS = [
    ("WP-14", "Well Pad 14 - Moran Field"),
    ("GGS-07", "Group Gathering Station 7 - Naharkatiya"),
    ("PL-EXT", "Crude Oil Trunk Pipeline Extension - Duliajan Sector"),
    ("GPU-03", "Gas Processing Unit 3 - Moran"),
    ("CGD-02", "City Gas Distribution Network Phase 2"),
]

DISCIPLINES = ["Civil", "Piping", "Electrical", "Instrumentation", "HSE"]

# ---------------------------------------------------------------------------
# L5/L6 activity templates per discipline, parameterized so we can generate
# many realistic, varied activities per unit (mirrors real EPC WBS dictionaries)
# ---------------------------------------------------------------------------
CIVIL_TEMPLATES = [
    ("Site levelling & grading for {struct}", "Site Levelling"),
    ("Excavation for {struct} foundation", "Excavation"),
    ("PCC laying for {struct} foundation", "PCC"),
    ("Reinforcement fixing for {struct} foundation", "Rebar"),
    ("Shuttering & formwork for {struct} foundation", "Formwork"),
    ("Concreting for {struct} foundation", "Concrete Pour"),
    ("De-shuttering for {struct} foundation", "De-shuttering"),
    ("Backfilling around {struct} foundation", "Backfill"),
    ("Approach road construction near {struct}", "Road Construction"),
    ("Boundary fencing & security wall for {struct}", "Fencing"),
]
CIVIL_STRUCTS = ["Well Pad WP-{n}", "GGS Tank Foundation TF-{n}", "Separator Skid Foundation SF-{n}",
                 "Pump House PH-{n}", "Cable Trench CT-{n}", "Flare Stack Foundation FS-{n}"]

PIPING_TEMPLATES = [
    ("Fabrication of flowline spool for {line}", "Fabrication"),
    ("Erection of flowline for {line}", "Erection"),
    ("Fit-up of flowline joints for {line}", "Fit-up"),
    ("Welding of joints for {line}", "Welding"),
    ("Radiography (NDT) for {line}", "NDT"),
    ("Hydrostatic testing of {line}", "Hydro Test"),
    ("Wellhead / Christmas tree installation at {line}", "Wellhead Installation"),
    ("Tie-in of flowline to {line}", "Tie-in"),
    ("Cathodic protection testing for {line}", "Cathodic Protection"),
    ("Pigging station tie-in at {line}", "Pigging Station"),
    ("Anti-corrosion coating & wrapping of {line}", "Coating"),
]
PIPE_SIZES = ["4\"", "6\"", "10\"", "16\"", "24\""]

ELECTRICAL_TEMPLATES = [
    ("Cable tray installation for {feeder}", "Tray Installation"),
    ("Cable laying for {feeder}", "Cable Laying"),
    ("Cable glanding & termination for {feeder}", "Termination"),
    ("Megger testing for {feeder}", "Megger Test"),
    ("Installation of {equip}", "Equipment Installation"),
    ("Panel wiring for {equip}", "Panel Wiring"),
    ("Earthing connection for {equip}", "Earthing"),
    ("Area lighting installation near {equip}", "Area Lighting"),
]
ELEC_FEEDERS = ["Feeder F-{n}", "MCC Panel MCC-{n}", "VFD Motor Cable VFD-{n}"]
ELEC_EQUIP = ["Transformer TR-{n}", "Submersible Pump Panel SPP-{n}", "Wellhead Motor Control WMC-{n}", "GGS LT Panel LTP-{n}"]

INSTR_TEMPLATES = [
    ("Installation of instrument {tag}", "Instrument Installation"),
    ("Impulse tubing for {tag}", "Tubing"),
    ("Loop checking for {tag}", "Loop Check"),
    ("Calibration of {tag}", "Calibration"),
    ("Junction box termination for {tag}", "JB Termination"),
    ("SCADA/RTU integration for {tag}", "SCADA Integration"),
    ("Flow computer commissioning for {tag}", "Flow Computer"),
    ("Wellhead pressure transmitter installation - {tag}", "Pressure Transmitter"),
]
INSTR_TAGS = ["PT-{n}", "FT-{n}", "TT-{n}", "LT-{n}", "XV-{n}", "RTU-{n}"]

HSE_TEMPLATES = [
    ("Safety induction & orientation for {area}", "Induction"),
    ("Scaffolding erection safety inspection - {area}", "Scaffold Inspection"),
    ("PTW (permit-to-work) issuance for {area}", "PTW"),
    ("Fire watch arrangement for hot work - {area}", "Fire Watch"),
    ("HIRA review for {area}", "HIRA"),
    ("PPE compliance audit - {area}", "PPE Audit"),
    ("H2S gas detector calibration & drill - {area}", "H2S Drill"),
    ("Well control / blowout prevention drill - {area}", "BOP Drill"),
]
HSE_AREAS = ["Well Pad WP-{n}", "Confined Space CS-{n}", "Hot Work Zone HW-{n}", "GGS Tank Farm TF-{n}"]

nodes = []
edges = []
node_id_counter = itertools.count(1)


def new_node(name, discipline, level, parent_id, description, activity_id=None, planned_quantity=None, unit=None, duration=None):
    nid = f"A{next(node_id_counter):05d}"
    nodes.append({
        "id": nid,
        "activity_id": activity_id,
        "name": name,
        "discipline": discipline,
        "level": level,
        "parent_id": parent_id,
        "description": description,
        "planned_quantity": planned_quantity,
        "unit": unit,
        "duration": duration
    })
    if parent_id:
        edges.append({"source": parent_id, "target": nid, "type": "wbs_parent"})
    return nid


# L1: Project
project_id = new_node(PROJECT_NAME, "Project", 1, None, "Top-level project milestone")

for unit_code, unit_name in UNITS:
    # L2: Unit/Area
    unit_id = new_node(f"{unit_code} - {unit_name}", "Multi", 2, project_id, f"Area {unit_code}")

    for discipline in DISCIPLINES:
        # L3: Discipline within unit
        disc_id = new_node(f"{discipline} Works - {unit_code}", discipline, 3, unit_id,
                            f"{discipline} scope for {unit_name}")

        # L4: Sub-system groupings (varies by discipline)
        n_subsystems = random.randint(2, 3)
        for s in range(n_subsystems):
            sub_id = new_node(f"{discipline} Sub-system {s+1} - {unit_code}", discipline, 4, disc_id,
                               f"Sub-system grouping {s+1}")

            # L5/L6: actual executable activities
            n_activities = random.randint(4, 7)
            prev_activity_id = None
            for a in range(n_activities):
                planned_qty = random.randint(10, 500)
                unit = "EA"
                activity_id_prefix = "GEN"
                
                if discipline == "Civil":
                    tmpl, short = random.choice(CIVIL_TEMPLATES)
                    struct = random.choice(CIVIL_STRUCTS).format(n=random.randint(1, 40))
                    name = tmpl.format(struct=struct)
                    activity_id_prefix = "CIV"
                    unit = random.choice(["m3", "sqm"])
                    rate = 10 if unit == "m3" else 20
                    duration = max(1, min(15, planned_qty // rate))
                elif discipline == "Piping":
                    tmpl, short = random.choice(PIPING_TEMPLATES)
                    line = f"{random.randint(10,99)}\"-{random.choice(PIPE_SIZES)}-{random.choice(['CS','SS','AS'])}"
                    name = tmpl.format(line=line)
                    activity_id_prefix = "PIP"
                    unit = random.choice(["inch-dia", "joints", "meters"])
                    rate = 30 if unit == "inch-dia" else (5 if unit == "joints" else 10)
                    duration = max(1, min(15, planned_qty // rate))
                elif discipline == "Electrical":
                    tmpl, short = random.choice(ELECTRICAL_TEMPLATES)
                    if "{feeder}" in tmpl:
                        name = tmpl.format(feeder=random.choice(ELEC_FEEDERS).format(n=random.randint(1,30)))
                    else:
                        name = tmpl.format(equip=random.choice(ELEC_EQUIP).format(n=random.randint(1,30)))
                    activity_id_prefix = "ELE"
                    unit = random.choice(["meters", "terminations", "EA"])
                    if unit == "EA": planned_qty = random.randint(1, 3)
                    rate = 50 if unit == "meters" else (10 if unit == "terminations" else 1)
                    duration = max(1, min(15, planned_qty // rate))
                elif discipline == "Instrumentation":
                    tmpl, short = random.choice(INSTR_TEMPLATES)
                    tag = random.choice(INSTR_TAGS).format(n=random.randint(100,999))
                    name = tmpl.format(tag=tag)
                    activity_id_prefix = "INS"
                    unit = random.choice(["loops", "tags", "EA"])
                    if unit == "EA": planned_qty = random.randint(1, 5)
                    rate = 2 if unit == "loops" else (5 if unit == "tags" else 1)
                    duration = max(1, min(10, planned_qty // rate))
                else:  # HSE
                    tmpl, short = random.choice(HSE_TEMPLATES)
                    area = random.choice(HSE_AREAS).format(n=random.randint(1,15))
                    name = tmpl.format(area=area)
                    activity_id_prefix = "HSE"
                    unit = "sessions"
                    planned_qty = random.randint(1, 5)
                    duration = max(1, min(5, planned_qty))

                act_id_val = f"{activity_id_prefix}-{random.randint(1000, 9999)}"
                act_id = new_node(name, discipline, 5, sub_id, short, activity_id=act_id_val, planned_quantity=planned_qty, unit=unit, duration=duration)
                if prev_activity_id:
                    edges.append({"source": prev_activity_id, "target": act_id, "type": "predecessor"})
                prev_activity_id = act_id

# Cross-discipline dependencies (realistic: e.g. civil foundation -> piping erection,
# electrical cable tray -> instrumentation cable laying)
l5_nodes = [n for n in nodes if n["level"] == 5]
civil_nodes = [n for n in l5_nodes if n["discipline"] == "Civil"]
piping_nodes = [n for n in l5_nodes if n["discipline"] == "Piping"]
elec_nodes = [n for n in l5_nodes if n["discipline"] == "Electrical"]
instr_nodes = [n for n in l5_nodes if n["discipline"] == "Instrumentation"]

for _ in range(min(30, len(civil_nodes), len(piping_nodes))):
    c = random.choice(civil_nodes)
    p = random.choice(piping_nodes)
    edges.append({"source": c["id"], "target": p["id"], "type": "predecessor"})

for _ in range(min(20, len(elec_nodes), len(instr_nodes))):
    e = random.choice(elec_nodes)
    i = random.choice(instr_nodes)
    edges.append({"source": e["id"], "target": i["id"], "type": "predecessor"})

for _ in range(min(20, len(piping_nodes), len(instr_nodes))):
    p = random.choice(piping_nodes)
    i = random.choice(instr_nodes)
    edges.append({"source": p["id"], "target": i["id"], "type": "predecessor"})

for _ in range(min(10, len(piping_nodes), len(elec_nodes))):
    p = random.choice(piping_nodes)
    e = random.choice(elec_nodes)
    edges.append({"source": p["id"], "target": e["id"], "type": "predecessor"})

schedule = {"project": PROJECT_NAME, "nodes": nodes, "edges": edges}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "schedule_graph.json")
with open(out_path, "w") as f:
    json.dump(schedule, f, indent=2)

print(f"Generated {len(nodes)} nodes and {len(edges)} edges.")
print(f"L5 (executable activity) nodes: {len(l5_nodes)}")
