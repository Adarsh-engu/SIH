"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, X, Clock, AlertCircle, Download, AlertTriangle, Lightbulb } from "lucide-react";
import ScheduleGraph from "../../components/ScheduleGraph";

type SetuEvent = {
  id: number;
  raw_phrase: string;
  extracted_json: {
      activity_phrase?: string;
      discipline?: string;
      action?: string;
  };
  matched_node_id: string;
  matched_node_name?: string;
  matched_discipline?: string;
  confidence: number;
  status: string;
  percent_complete?: number;
  created_at: string;
  match_reasoning?: {
      semantic_score?: number;
      id_match?: boolean;
      discipline_match?: boolean;
      unit_match?: boolean;
      qty_match?: boolean;
      dependency_violations?: Array<{
          predecessor_id: string;
          predecessor_name: string;
          reason: string;
      }>;
  };
};

export default function PlannerDashboard() {
  const [events, setEvents] = useState<SetuEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [insights, setInsights] = useState<string[]>([]);
  const [dprDate, setDprDate] = useState(() => new Date().toISOString().split('T')[0]);

  // Fetch initial data
  const fetchEvents = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/needs-review");
      if (res.ok) {
        const data = await res.json();
        setEvents(data);
      }
    } catch (err) {
      console.error("Failed to fetch initial events", err);
    }
  };

  const fetchInsights = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/analytics");
      if (res.ok) {
        const data = await res.json();
        setInsights(data.insights || []);
      }
    } catch (err) {
      console.error("Failed to fetch insights", err);
    }
  };

  useEffect(() => {
    fetchEvents();
    fetchInsights();

    const ws = new WebSocket("ws://127.0.0.1:8000/ws");
    
    ws.onopen = () => {
        setIsConnected(true);
    };

    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "new_report") {
            const newEventData = payload.data;
            if (newEventData.match.status === "needs-review") {
                fetchEvents();
            }
            // Ensure graph refreshes for auto-updated events
            setRefreshTrigger((prev) => prev + 1);
        } else if (payload.type === "status_update") {
            // Re-fetch the queue so that sequence conflicts for remaining items are dynamically updated
            fetchEvents();
            setRefreshTrigger((prev) => prev + 1);
        }
    };

    ws.onclose = () => {
        setIsConnected(false);
    };

    return () => ws.close();
  }, []);

  const handleAction = async (eventId: number, action: "confirm" | "reject") => {
      // Optimistically remove
      setEvents((prev) => prev.filter(e => e.id !== eventId));
      
      try {
          await fetch(`http://127.0.0.1:8000/events/${eventId}/${action}`, {
              method: "POST"
          });
          // Re-render graph to show new confirmed nodes
          setRefreshTrigger(prev => prev + 1);
      } catch (err) {
          console.error(`Failed to ${action} event`, err);
          // Re-fetch to fix state if optimistic update failed
          fetchEvents();
      }
  };

  return (
    <main className="flex-1 bg-slate-950 p-6 md:p-8 text-slate-100 flex flex-col h-[calc(100vh-56px)] overflow-hidden">
        
        <header className="flex items-center justify-between mb-6 shrink-0">
            <div>
                <h1 className="text-3xl font-bold tracking-tight mb-1">Planner Dashboard</h1>
                <p className="text-slate-400">Review field reports and monitor project schedule impact.</p>
            </div>
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <input
                        type="date"
                        id="dpr-date-picker"
                        value={dprDate}
                        onChange={(e) => setDprDate(e.target.value)}
                        className="h-9 px-3 rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <a
                        href={`http://127.0.0.1:8000/reports/daily/download?date=${dprDate}`}
                        download
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-medium transition-colors shadow-sm"
                    >
                        <Download className="w-4 h-4" /> Download DPR
                    </a>
                </div>
                <a 
                    href="http://127.0.0.1:8000/export-schedule" 
                    download
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors shadow-sm"
                >
                    <Download className="w-4 h-4" /> Export CSV
                </a>
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border ${isConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                    <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></div>
                    {isConnected ? 'Live Sync' : 'Offline'}
                </div>
            </div>
        </header>

        <div className="flex-1 flex flex-col lg:flex-row gap-8 overflow-hidden">
            {/* LEFT COLUMN: The Graph & Insights */}
            <div className="flex-[2] h-full flex flex-col min-h-0 gap-6">
                {insights.length > 0 && (
                    <div className="bg-indigo-900/20 border border-indigo-500/30 rounded-2xl p-5 shrink-0 flex items-start gap-4 shadow-sm">
                        <div className="bg-indigo-500/20 p-2.5 rounded-full mt-1 shrink-0">
                            <Lightbulb className="w-5 h-5 text-indigo-400" />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold text-indigo-300 uppercase tracking-wider mb-2">Execution Memory Insights</h3>
                            <ul className="space-y-2">
                                {insights.map((insight, idx) => (
                                    <li key={idx} className="text-slate-200 text-sm leading-relaxed">
                                        <strong className="text-indigo-400">•</strong> {insight}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                )}
                
                <div className="flex-1 min-h-0 relative">
                    <ScheduleGraph refreshTrigger={refreshTrigger} />
                </div>
            </div>

            {/* RIGHT COLUMN: The Queue */}
            <div className="flex-1 flex flex-col h-full bg-slate-900/30 rounded-3xl border border-slate-800 p-5 overflow-hidden">
                <h2 className="text-lg font-semibold mb-4 flex items-center justify-between">
                    <span>Needs Review</span>
                    <span className="bg-amber-500/10 text-amber-500 text-xs py-1 px-2.5 rounded-full border border-amber-500/20">{events.length} Pending</span>
                </h2>
                
                <div className="overflow-y-auto pr-2 custom-scrollbar flex-1 space-y-4">
                    <AnimatePresence mode="popLayout">
                        {events.length === 0 ? (
                            <motion.div 
                                initial={{ opacity: 0 }} 
                                animate={{ opacity: 1 }} 
                                exit={{ opacity: 0 }}
                                className="text-center py-16 border border-slate-800 border-dashed rounded-2xl bg-slate-900/50"
                            >
                                <div className="w-12 h-12 mx-auto bg-slate-800 rounded-full flex items-center justify-center mb-3">
                                    <Check className="w-6 h-6 text-slate-500" />
                                </div>
                                <h3 className="text-base font-medium text-slate-300">Queue empty</h3>
                                <p className="text-sm text-slate-500">All field reports processed.</p>
                            </motion.div>
                        ) : (
                            events.map((evt) => (
                                <motion.div
                                    layout
                                    initial={{ opacity: 0, x: 20, scale: 0.95 }}
                                    animate={{ opacity: 1, x: 0, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ type: "spring", damping: 20, stiffness: 200 }}
                                    key={evt.id}
                                    className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group"
                                >
                                    <div className="absolute top-0 left-0 w-1 h-full bg-amber-500"></div>
                                    
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px] font-bold uppercase tracking-widest border border-slate-700">
                                            {evt.matched_discipline || evt.extracted_json?.discipline || 'Unknown'}
                                        </span>
                                        <span className="text-[10px] font-medium text-slate-500 flex items-center gap-1">
                                            <Clock className="w-3 h-3" />
                                            {new Date(evt.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                        </span>
                                    </div>
                                    
                                    <h3 className="text-base font-medium text-slate-100 mb-1 leading-snug">
                                        {evt.matched_node_name || evt.extracted_json?.action || evt.extracted_json?.activity_phrase || "Unknown Action"}
                                    </h3>
                                    
                                    <div className="text-xs text-slate-400 flex flex-col gap-1 mb-3">
                                        <span>Node: <strong className="text-slate-300">{evt.matched_node_id || 'None'}</strong></span>
                                        <span>Confidence: <strong className={evt.confidence > 0.2 ? "text-amber-400" : "text-red-400"}>{(evt.confidence * 100).toFixed(0)}%</strong></span>
                                        {evt.percent_complete !== undefined && evt.percent_complete !== null && (
                                            <span className="flex items-center gap-2 mt-1">
                                                <span>Progress: <strong className="text-blue-400">{evt.percent_complete}%</strong></span>
                                                <div className="flex-1 max-w-[100px] h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, Math.max(0, evt.percent_complete))}%` }}></div>
                                                </div>
                                            </span>
                                        )}
                                    </div>
                                    
                                    {evt.match_reasoning && (
                                        <div className="mb-4 bg-slate-950/50 rounded-lg p-2.5 text-[10px] text-slate-400 border border-slate-800/60 flex gap-2 flex-wrap items-center">
                                            <span className="text-slate-500 w-full mb-0.5 font-medium flex items-center gap-1.5"><AlertCircle className="w-3 h-3"/> Match Reasoning</span>
                                            {evt.match_reasoning.id_match && <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded"><Check className="w-3 h-3" /> Exact ID</span>}
                                            {evt.match_reasoning.qty_match && <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded"><Check className="w-3 h-3" /> Quantity</span>}
                                            {evt.match_reasoning.unit_match && !evt.match_reasoning.qty_match && <span className="flex items-center gap-1 text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded"><Check className="w-3 h-3" /> Unit</span>}
                                            {evt.match_reasoning.discipline_match && <span className="flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded"><Check className="w-3 h-3" /> Discipline</span>}
                                            {evt.match_reasoning.semantic_score !== undefined && <span className="flex items-center gap-1 bg-slate-800/50 px-1.5 py-0.5 rounded">Semantic: {evt.match_reasoning.semantic_score}</span>}
                                        </div>
                                    )}

                                    {evt.match_reasoning?.dependency_violations && evt.match_reasoning.dependency_violations.length > 0 && (
                                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                                            <h4 className="text-xs font-bold text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                                                <AlertTriangle className="w-3 h-3" />
                                                Sequence Conflict
                                            </h4>
                                            <ul className="space-y-1">
                                                {evt.match_reasoning.dependency_violations.map((v, idx) => (
                                                    <li key={idx} className="text-[11px] text-red-300 flex items-start gap-2">
                                                        <span className="text-red-500 mt-0.5">•</span>
                                                        <span>{v.reason}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    <div className="flex items-center gap-2">
                                        <button 
                                            onClick={() => handleAction(evt.id, "reject")}
                                            className="flex-1 h-9 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 flex items-center justify-center transition-colors border border-red-500/20 text-sm font-medium"
                                        >
                                            Reject
                                        </button>
                                        <button 
                                            onClick={() => handleAction(evt.id, "confirm")}
                                            className="flex-[2] h-9 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center gap-2 transition-colors shadow-sm shadow-indigo-500/25 text-sm font-medium"
                                        >
                                            <Check className="w-4 h-4" /> Confirm
                                        </button>
                                    </div>
                                </motion.div>
                            ))
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    </main>
  );
}
