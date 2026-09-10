import json
import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '../backend'))
from database import insert_event

# Configuration
OVERRUN_FACTOR_CIVIL = 0.40 # 40% overrun for Civil
GRAPH_PATH = os.path.join(os.path.dirname(__file__), '../data/schedule_graph.json')

def seed_data():
    from database import engine
    from sqlmodel import Session
    from sqlalchemy import text
    with Session(engine) as session:
        session.execute(text("DELETE FROM event_audit WHERE source = 'historical'"))
        session.commit()
        
    with open(GRAPH_PATH, 'r') as f:
        graph = json.load(f)
        
    l5_nodes = [n for n in graph['nodes'] if n.get('level') == 5]
    
    # Let's pick up to 10 Civil nodes and 10 non-Civil nodes
    civil_nodes = [n for n in l5_nodes if n.get('discipline') == 'Civil'][:10]
    other_nodes = [n for n in l5_nodes if n.get('discipline') and n.get('discipline') != 'Civil'][:10]
    
    selected_nodes = civil_nodes + other_nodes
    
    base_date = datetime.now() - timedelta(days=100)
    
    for idx, node in enumerate(selected_nodes):
        node_id = node['id']
        node_name = node['name']
        discipline = node['discipline']
        duration_days = node.get('duration') or 5
        
        # Start event
        start_date = base_date + timedelta(days=idx*2) # Stagger start dates
        
        insert_event(
            raw_phrase=f"Historical record: Started {node_name}",
            extracted_json={},
            matched_node_id=node_id,
            matched_node_name=node_name,
            matched_discipline=discipline,
            confidence=1.0,
            status="confirmed",
            percent_complete=0.0,
            source="historical",
            timestamp=start_date.isoformat()
        )
        
        # Calculate actual duration
        if discipline == 'Civil':
            actual_duration = int(duration_days * (1 + OVERRUN_FACTOR_CIVIL))
        else:
            actual_duration = int(duration_days)
            
        finish_date = start_date + timedelta(days=actual_duration)
        
        insert_event(
            raw_phrase=f"Historical record: Completed {node_name}",
            extracted_json={},
            matched_node_id=node_id,
            matched_node_name=node_name,
            matched_discipline=discipline,
            confidence=1.0,
            status="confirmed",
            percent_complete=100.0,
            source="historical",
            timestamp=finish_date.isoformat()
        )
        
    print(f"Seeded {len(selected_nodes)} historical events with paired start/complete timestamps.")

if __name__ == "__main__":
    seed_data()
