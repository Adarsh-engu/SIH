from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "setu.db")
sqlite_url = f"sqlite:///{DB_PATH}"

engine = create_engine(sqlite_url, echo=False)

class EventAudit(SQLModel, table=True):
    __tablename__ = "event_audit"
    id: Optional[int] = Field(default=None, primary_key=True)
    raw_phrase: str
    extracted_json: str
    matched_node_id: Optional[str] = None
    matched_node_name: Optional[str] = None
    matched_discipline: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    match_reasoning: Optional[str] = None
    actual_quantity: Optional[float] = None
    percent_complete: Optional[float] = None
    timestamp: str
    source: str = Field(default="live")

def init_db():
    SQLModel.metadata.create_all(engine)

def insert_event(raw_phrase: str, extracted_json: Dict[str, Any], matched_node_id: Optional[str], matched_node_name: Optional[str], matched_discipline: Optional[str], confidence: Optional[float], status: Optional[str], match_reasoning: Dict[str, Any] = None, actual_quantity: Optional[float] = None, percent_complete: Optional[float] = None, source: str = "live", timestamp: Optional[str] = None) -> int:
    event = EventAudit(
        raw_phrase=raw_phrase,
        extracted_json=json.dumps(extracted_json),
        matched_node_id=matched_node_id,
        matched_node_name=matched_node_name,
        matched_discipline=matched_discipline,
        confidence=confidence,
        status=status,
        match_reasoning=json.dumps(match_reasoning or {}),
        actual_quantity=actual_quantity,
        percent_complete=percent_complete,
        timestamp=timestamp or datetime.now().isoformat(),
        source=source
    )
    with Session(engine) as session:
        session.add(event)
        session.commit()
        session.refresh(event)
        return event.id

def get_events(status_filter: Optional[str] = None, source_filter: Optional[str] = None, date_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    with Session(engine) as session:
        statement = select(EventAudit)
        if status_filter:
            statement = statement.where(EventAudit.status == status_filter)
        if source_filter:
            statement = statement.where(EventAudit.source == source_filter)
        if date_filter:
            statement = statement.where(EventAudit.timestamp.startswith(date_filter))
        
        statement = statement.order_by(EventAudit.id.desc())
        results = session.exec(statement).all()
        
        events = []
        for row in results:
            d = row.model_dump()
            try:
                d['extracted_json'] = json.loads(d['extracted_json'])
            except Exception:
                d['extracted_json'] = {}
                
            try:
                d['match_reasoning'] = json.loads(d['match_reasoning']) if d.get('match_reasoning') else {}
            except Exception:
                d['match_reasoning'] = {}
            d['created_at'] = d['timestamp']
            events.append(d)
        return events

def get_completed_node_ids() -> set:
    """Return the set of matched_node_ids for all confirmed or auto-updated LIVE events.
    Strictly filters source='live' — historical seed data must never satisfy
    dependency checks for live project reports (Phase 13 integrity requirement).
    """
    with Session(engine) as session:
        statement = select(EventAudit).where(
            EventAudit.status.in_(["confirmed", "auto-updated"]),
            EventAudit.source == "live"
        )
        results = session.exec(statement).all()
        return {r.matched_node_id for r in results if r.matched_node_id}

def update_event_status(event_id: int, new_status: str):
    with Session(engine) as session:
        event = session.get(EventAudit, event_id)
        if event:
            event.status = new_status
            session.add(event)
            session.commit()
