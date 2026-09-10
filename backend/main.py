from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from database import init_db, insert_event, get_events, update_event_status, get_completed_node_ids
from llm_extractor import extract_structured_event
from matcher_service import matcher_service
import json
import csv
from io import StringIO

app = FastAPI(title="Setu API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.on_event("startup")
def startup_event():
    init_db()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect client messages currently, just hold the connection open
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

class ReportRequest(BaseModel):
    raw_phrase: str

@app.post("/report")
async def submit_report(req: ReportRequest):
    # 1. Extract JSON from raw phrase
    extracted = extract_structured_event(req.raw_phrase)
    
    # 2. Fuzzy match against the schedule graph
    match_result = matcher_service.find_match(extracted["activity_phrase"], extracted)
    
    # 2.5 Dependency validation
    completed_ids = get_completed_node_ids()
    dep_check = matcher_service.check_dependencies(match_result["matched_node_id"], completed_ids)
    
    if not dep_check["is_consistent"]:
        match_result["status"] = "needs-review"
        match_reasoning = match_result.get("reasoning", {})
        match_reasoning["dependency_violations"] = dep_check["violations"]
        match_result["reasoning"] = match_reasoning

    actual_quantity = None
    percent_complete = None
    
    if extracted.get("quantity") is not None:
        matched_node = matcher_service.nodes_by_id.get(match_result["matched_node_id"])
        if matched_node and matched_node.get("planned_quantity"):
            try:
                reported_qty = float(extracted["quantity"])
                actual_quantity = reported_qty
                planned_qty = float(matched_node["planned_quantity"])
                
                all_events = get_events()
                cumulative = 0.0
                for e in all_events:
                    if e.get("matched_node_id") == match_result["matched_node_id"] and e.get("status") in ["confirmed", "auto-updated"]:
                        cumulative += e.get("actual_quantity", 0.0) or 0.0
                
                total_qty = cumulative + reported_qty
                percent_complete = min(round((total_qty / planned_qty) * 100, 1), 100.0)
            except (ValueError, TypeError):
                pass

    # 3. Persist the event with confidence branching logic
    event_id = insert_event(
        raw_phrase=req.raw_phrase,
        extracted_json=extracted,
        matched_node_id=match_result["matched_node_id"],
        matched_node_name=match_result.get("matched_node_name"),
        matched_discipline=match_result.get("discipline"),
        confidence=match_result["confidence"],
        status=match_result["status"],
        match_reasoning=match_result.get("reasoning", {}),
        actual_quantity=actual_quantity,
        percent_complete=percent_complete
    )
    
    match_result["percent_complete"] = percent_complete
    
    response_data = {
        "event_id": event_id,
        "extracted": extracted,
        "match": match_result
    }
    
    # 4. Broadcast the new event
    await manager.broadcast({
        "type": "new_report",
        "data": response_data
    })
    
    return response_data

@app.get("/events")
def list_events():
    return get_events()

@app.get("/needs-review")
def list_needs_review():
    return get_events(status_filter="needs-review")

@app.get("/schedule-graph")
def get_schedule_graph():
    # Fetch all events to map exact statuses and percent complete
    all_events = get_events()
    node_status_map = {}
    node_percent_map = {}
    
    for e in all_events:
        nid = e.get("matched_node_id")
        if nid:
            if nid not in node_status_map:
                node_status_map[nid] = e.get("status")
            if e.get("status") in ["confirmed", "auto-updated"] and e.get("percent_complete") is not None:
                node_percent_map[nid] = max(node_percent_map.get(nid, 0.0), e.get("percent_complete"))
            
    graph_data = matcher_service.schedule
    # Annotate nodes with exact status
    annotated_nodes = []
    for node in graph_data["nodes"]:
        n = node.copy()
        n["status"] = node_status_map.get(n["id"], "pending")
        if n["id"] in node_percent_map:
            n["percent_complete"] = node_percent_map[n["id"]]
        annotated_nodes.append(n)
        
    return {
        "nodes": annotated_nodes,
        "edges": graph_data["edges"]
    }

@app.get("/stats")
def get_stats():
    # Get all nodes to establish the denominator
    graph_data = matcher_service.schedule
    total_by_discipline = {}
    for n in graph_data["nodes"]:
        d = n.get("discipline", "Unknown")
        total_by_discipline[d] = total_by_discipline.get(d, 0) + 1
        
    # Get completed nodes
    confirmed_events = get_events(status_filter="confirmed")
    auto_updated = get_events(status_filter="auto-updated")
    completed_node_ids = set([e["matched_node_id"] for e in confirmed_events + auto_updated])
    
    completed_by_discipline = {}
    for nid in completed_node_ids:
        node = matcher_service.nodes_by_id.get(nid)
        if node:
            d = node.get("discipline", "Unknown")
            completed_by_discipline[d] = completed_by_discipline.get(d, 0) + 1
            
    discipline_stats = []
    for d, total in total_by_discipline.items():
        if d in ["Project", "Multi"]:  # Skip WBS overview nodes
            continue
        comp = completed_by_discipline.get(d, 0)
        discipline_stats.append({
            "discipline": d,
            "completed": comp,
            "pending": total - comp,
            "total": total
        })
        
    needs_review = get_events(status_filter="needs-review")
    
    all_events = get_events()
    # Sort descending by id to get newest
    all_events.sort(key=lambda x: x["id"], reverse=True)
    recent_activity = all_events[:5]
    
    return {
        "total_tasks": sum(total for d, total in total_by_discipline.items() if d not in ["Project", "Multi"]),
        "completed_tasks": len(completed_node_ids),
        "needs_review_count": len(needs_review),
        "discipline_stats": discipline_stats,
        "recent_activity": recent_activity
    }

from datetime import datetime

@app.get("/analytics")
def get_analytics():
    # Only query historical seeded data for insights
    historical_events = get_events(source_filter="historical")
    
    # Group events by matched_node_id
    node_events = {}
    for e in historical_events:
        nid = e.get("matched_node_id")
        if not nid: continue
        if nid not in node_events:
            node_events[nid] = []
        node_events[nid].append(e)
        
    discipline_overruns = {}
    discipline_counts = {}
    
    for nid, events in node_events.items():
        # Find 0% and 100% events
        start_event = next((e for e in events if e.get("percent_complete") == 0.0), None)
        finish_event = next((e for e in events if e.get("percent_complete") == 100.0), None)
        
        # Discard incomplete pairs
        if not start_event or not finish_event:
            continue
            
        try:
            start_time = datetime.fromisoformat(start_event["timestamp"])
            finish_time = datetime.fromisoformat(finish_event["timestamp"])
            actual_duration_days = (finish_time - start_time).total_seconds() / 86400.0
            
            node = matcher_service.nodes_by_id.get(nid)
            if not node or not node.get("duration"):
                continue
                
            planned_duration = float(node["duration"])
            if planned_duration == 0:
                continue
                
            overrun_ratio = (actual_duration_days / planned_duration) - 1.0
            discipline = node.get("discipline", "Unknown")
            
            discipline_overruns[discipline] = discipline_overruns.get(discipline, 0.0) + overrun_ratio
            discipline_counts[discipline] = discipline_counts.get(discipline, 0) + 1
        except Exception:
            pass
            
    insights = []
    for d, total_ratio in discipline_overruns.items():
        count = discipline_counts[d]
        if count > 0:
            avg_overrun_pct = round((total_ratio / count) * 100)
            if avg_overrun_pct > 0:
                insights.append(f"{d} works exceeded planned duration by {avg_overrun_pct}% on average across {count} historical tasks.")
            elif avg_overrun_pct < 0:
                insights.append(f"{d} works completed {abs(avg_overrun_pct)}% faster than planned duration on average across {count} historical tasks.")
            else:
                insights.append(f"{d} works exactly met their planned duration on average across {count} historical tasks.")
                
    if not insights:
        insights.append("Not enough historical data pairs to generate execution insights.")
        
    return {
        "insights": insights
    }

@app.get("/export-schedule")
def export_schedule():
    graph_data = matcher_service.schedule
    confirmed_events = get_events(status_filter="confirmed")
    auto_updated = get_events(status_filter="auto-updated")
    
    completed_node_ids = set([e["matched_node_id"] for e in confirmed_events + auto_updated])
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Task ID", "Task Name", "Discipline", "Status", "Level"])
    
    for n in graph_data["nodes"]:
        if n.get("level") == 5:
            status = "Completed" if n["id"] in completed_node_ids else "Pending"
            cw.writerow([n["id"], n["name"], n.get("discipline", "Unknown"), status, n.get("level")])
        
    response = Response(content=si.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=setu_schedule_update.csv"
    return response

@app.post("/events/{event_id}/confirm")
async def confirm_event(event_id: int):
    update_event_status(event_id, "confirmed")
    await manager.broadcast({
        "type": "status_update",
        "data": {"event_id": event_id, "status": "confirmed"}
    })
    return {"message": "Event confirmed"}

@app.post("/events/{event_id}/reject")
async def reject_event(event_id: int):
    update_event_status(event_id, "rejected")
    await manager.broadcast({
        "type": "status_update",
        "data": {"event_id": event_id, "status": "rejected"}
    })
    return {"message": "Event rejected"}
