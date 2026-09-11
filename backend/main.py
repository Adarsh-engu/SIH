from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from database import init_db, insert_event, get_events, update_event_status, get_completed_node_ids
from llm_extractor import extract_structured_event, OLLAMA_STATUS
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
    events = get_events(status_filter="needs-review")
    completed_ids = get_completed_node_ids()
    for e in events:
        nid = e.get("matched_node_id")
        if nid:
            dep_check = matcher_service.check_dependencies(nid, completed_ids)
            reasoning = e.get("match_reasoning", {})
            reasoning["dependency_violations"] = dep_check["violations"]
            e["match_reasoning"] = reasoning
    return events

@app.get("/schedule-graph")
def get_schedule_graph():
    # Fetch LIVE events only — historical seed data must not affect DAG node coloring
    all_events = get_events(source_filter="live")
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
    # Annotate nodes with live status only
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
        
    # Get completed nodes — LIVE source only, never historical seed data
    confirmed_events = get_events(status_filter="confirmed", source_filter="live")
    auto_updated = get_events(status_filter="auto-updated", source_filter="live")
    completed_node_ids = set([e["matched_node_id"] for e in confirmed_events + auto_updated if e["matched_node_id"]])
    
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
        
    needs_review = get_events(status_filter="needs-review", source_filter="live")
    
    all_events = get_events(source_filter="live")
    # Sort descending by id to get newest
    all_events.sort(key=lambda x: x["id"], reverse=True)
    recent_activity = all_events[:5]
    
    return {
        "total_tasks": sum(total for d, total in total_by_discipline.items() if d not in ["Project", "Multi"]),
        "completed_tasks": len(completed_node_ids),
        "needs_review_count": len(needs_review),
        "discipline_stats": discipline_stats,
        "recent_activity": recent_activity,
        "llm_status": OLLAMA_STATUS,
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

def _build_dpr_data(date: str) -> dict:
    """Shared logic for both /reports/daily and /reports/daily/download."""
    all_live = get_events(source_filter="live", date_filter=date)
    qualified = [e for e in all_live if e.get("status") in ("auto-updated", "confirmed")]

    if not qualified:
        return {"empty": True, "date": date}

    groups: dict = {}
    flags: list = []
    auto_count = 0
    confirmed_count = 0

    for e in qualified:
        discipline = e.get("matched_discipline") or "Unknown"
        if discipline not in groups:
            groups[discipline] = []

        reasoning = e.get("match_reasoning") or {}
        dep_violations = reasoning.get("dependency_violations") or []

        qty = e.get("actual_quantity")
        unit = (e.get("extracted_json") or {}).get("unit")

        groups[discipline].append({
            "activity_name": e.get("matched_node_name") or e.get("matched_node_id"),
            "node_id": e.get("matched_node_id"),
            "status": e.get("status"),
            "confidence": round((e.get("confidence") or 0) * 100),
            "quantity": qty,
            "unit": unit,
            "dependency_violations": dep_violations,
        })

        if dep_violations:
            flags.append({
                "activity": e.get("matched_node_name") or e.get("matched_node_id"),
                "violations": dep_violations,
            })

        if e.get("status") == "auto-updated":
            auto_count += 1
        else:
            confirmed_count += 1

    return {
        "empty": False,
        "date": date,
        "groups": groups,
        "flags": flags,
        "summary": {
            "auto_updated": auto_count,
            "planner_confirmed": confirmed_count,
            "total": auto_count + confirmed_count,
        },
    }


@app.get("/reports/daily")
def daily_report_json(date: str):
    data = _build_dpr_data(date)
    if data.get("empty"):
        return {"message": f"No confirmed activities recorded for {date}.", "date": date}
    return data


@app.get("/reports/daily/download")
def daily_report_download(date: str):
    data = _build_dpr_data(date)

    if data.get("empty"):
        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>DPR – {date}</title></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:40px auto;color:#333">
  <h1 style="color:#1a3c5e">Daily Progress Report</h1>
  <p><strong>Project:</strong> Upper Assam Oilfield Development &amp; Pipeline Augmentation Project</p>
  <p><strong>Date:</strong> {date}</p>
  <p><em>Generated by Setu</em></p>
  <hr/>
  <p>No confirmed activities recorded for this date.</p>
</body></html>"""
        resp = Response(content=html_content, media_type="text/html")
        resp.headers["Content-Disposition"] = f"attachment; filename=DPR_{date}.html"
        return resp

    groups = data["groups"]
    summary = data["summary"]
    flags = data["flags"]

    # Build discipline table rows
    discipline_sections = ""
    for discipline, activities in groups.items():
        rows = ""
        for act in activities:
            qty_str = f"{act['quantity']} {act['unit'] or ''}".strip() if act["quantity"] is not None else "—"
            flag_str = "⚠ Seq. Conflict" if act["dependency_violations"] else ""
            status_color = "#2e7d32" if act["status"] == "auto-updated" else "#1565c0"
            rows += f"""<tr>
              <td style="padding:8px 10px;border-bottom:1px solid #e0e0e0">{act['activity_name']}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e0e0e0;color:{status_color};font-weight:600">{act['status'].replace('-', ' ').title()}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e0e0e0;text-align:center">{act['confidence']}%</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e0e0e0;text-align:center">{qty_str}</td>
              <td style="padding:8px 10px;border-bottom:1px solid #e0e0e0;color:#c62828;text-align:center">{flag_str}</td>
            </tr>"""
        discipline_sections += f"""
        <h3 style="color:#1a3c5e;border-left:4px solid #1a3c5e;padding-left:10px;margin-top:28px">{discipline}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <thead>
            <tr style="background:#1a3c5e;color:#fff">
              <th style="padding:10px;text-align:left">Activity</th>
              <th style="padding:10px;text-align:left">Status</th>
              <th style="padding:10px;text-align:center">Confidence</th>
              <th style="padding:10px;text-align:center">Qty / Unit</th>
              <th style="padding:10px;text-align:center">Flags</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    # Flags section
    flags_html = ""
    if flags:
        flag_items = ""
        for f in flags:
            for v in f["violations"]:
                flag_items += f"<li><strong>{f['activity']}</strong>: {v.get('reason','Sequence conflict detected.')}</li>"
        flags_html = f"""
        <h3 style="color:#c62828;margin-top:32px">⚠ Dependency / Sequence Flags</h3>
        <ul style="font-size:14px;line-height:1.8">{flag_items}</ul>"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DPR – {date}</title>
  <style>
    @media print {{ body {{ margin: 20px; }} }}
    body {{ font-family: Arial, sans-serif; max-width: 960px; margin: 40px auto; color: #333; line-height: 1.5; }}
  </style>
</head>
<body>
  <div style="border-bottom:3px solid #1a3c5e;padding-bottom:16px;margin-bottom:24px">
    <h1 style="color:#1a3c5e;margin:0 0 6px 0;font-size:22px">Daily Progress Report</h1>
    <p style="margin:2px 0"><strong>Project:</strong> Upper Assam Oilfield Development &amp; Pipeline Augmentation Project</p>
    <p style="margin:2px 0"><strong>Date:</strong> {date}</p>
    <p style="margin:2px 0;color:#666;font-size:13px"><em>Generated by Setu — AI-Powered Site Progress Tracker</em></p>
  </div>

  <div style="display:flex;gap:24px;margin-bottom:24px">
    <div style="flex:1;background:#e8f5e9;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#2e7d32">{summary['auto_updated']}</div>
      <div style="font-size:13px;color:#555">Auto-Updated</div>
    </div>
    <div style="flex:1;background:#e3f2fd;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#1565c0">{summary['planner_confirmed']}</div>
      <div style="font-size:13px;color:#555">Planner Confirmed</div>
    </div>
    <div style="flex:1;background:#f5f5f5;border-radius:8px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#333">{summary['total']}</div>
      <div style="font-size:13px;color:#555">Total Activities</div>
    </div>
  </div>

  {discipline_sections}
  {flags_html}

  <p style="margin-top:40px;font-size:12px;color:#999;border-top:1px solid #eee;padding-top:12px">
    This report was automatically generated by Setu from verified field site reports. 
    Auto-updated entries were matched with high confidence by the AI. Planner-confirmed entries were reviewed and approved by the site planner.
  </p>
</body>
</html>"""

    resp = Response(content=html_content, media_type="text/html")
    resp.headers["Content-Disposition"] = f"attachment; filename=DPR_{date}.html"
    return resp


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
