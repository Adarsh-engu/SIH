"use client";

import { useState, useEffect } from "react";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts";
import { Activity, CheckCircle2, AlertCircle, Clock, BarChart3 } from "lucide-react";
import { motion } from "framer-motion";

type DisciplineStat = {
  discipline: string;
  completed: number;
  pending: number;
  total: number;
};

type RecentEvent = {
  id: number;
  extracted_json: any;
  confidence: number;
  status: string;
  created_at: string;
};

type StatsResponse = {
  total_tasks: number;
  completed_tasks: number;
  needs_review_count: number;
  discipline_stats: DisciplineStat[];
  recent_activity: RecentEvent[];
};

export default function AnalyticsDashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/stats");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (err) {
        console.error("Failed to fetch stats", err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
    
    // Auto-refresh every 5 seconds for demo purposes
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !stats) {
    return (
      <div className="flex-1 flex items-center justify-center h-[calc(100vh-56px)]">
        <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  const overallProgress = Math.round((stats.completed_tasks / stats.total_tasks) * 100) || 0;

  // Colors for disciplines
  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

  return (
    <main className="flex-1 bg-slate-950 p-6 md:p-8 text-slate-100 overflow-y-auto h-[calc(100vh-56px)] custom-scrollbar">
      <div className="max-w-6xl mx-auto space-y-8">
        
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Project Analytics</h1>
          <p className="text-slate-400">High-level insights based on real-time field reporting.</p>
        </header>

        {/* Top KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Overall Progress</h3>
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold text-white">{overallProgress}%</span>
              <span className="text-sm text-slate-500 mb-1">{stats.completed_tasks} / {stats.total_tasks} tasks</span>
            </div>
            <div className="mt-4 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div className="bg-emerald-500 h-full rounded-full transition-all duration-1000 ease-out" style={{ width: `${overallProgress}%` }}></div>
            </div>
          </motion.div>

          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }} className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Needs Review</h3>
              <div className="w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-amber-400" />
              </div>
            </div>
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold text-white">{stats.needs_review_count}</span>
              <span className="text-sm text-slate-500 mb-1">pending reports</span>
            </div>
          </motion.div>
          
          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.2 }} className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm relative overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Recent Reports</h3>
              <div className="w-10 h-10 rounded-full bg-indigo-500/10 flex items-center justify-center">
                <Activity className="w-5 h-5 text-indigo-400" />
              </div>
            </div>
            <div className="flex items-end gap-3">
              <span className="text-5xl font-bold text-white">{stats.recent_activity.length}</span>
              <span className="text-sm text-slate-500 mb-1">latest events processed</span>
            </div>
          </motion.div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.3 }} className="lg:col-span-2 bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm">
            <h3 className="text-base font-semibold text-slate-200 mb-6">Task Completion by Discipline</h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.discipline_stats} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="discipline" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', color: '#f1f5f9' }}
                    itemStyle={{ color: '#f1f5f9' }}
                    cursor={{ fill: '#1e293b' }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  <Bar dataKey="completed" name="Completed" stackId="a" fill="#10b981" radius={[0, 0, 4, 4]} />
                  <Bar dataKey="pending" name="Pending" stackId="a" fill="#334155" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.4 }} className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm">
            <h3 className="text-base font-semibold text-slate-200 mb-6">Discipline Breakdown</h3>
            <div className="h-[250px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats.discipline_stats}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="total"
                    nameKey="discipline"
                  >
                    {stats.discipline_stats.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', color: '#f1f5f9' }}
                    itemStyle={{ color: '#f1f5f9' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            
            {/* Custom Legend */}
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              {stats.discipline_stats.map((entry, index) => (
                <div key={entry.discipline} className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                  <span className="text-xs text-slate-400">{entry.discipline}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Recent Activity Feed */}
        <motion.div initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.5 }} className="bg-slate-900 border border-slate-800 p-6 rounded-3xl shadow-sm">
          <h3 className="text-base font-semibold text-slate-200 mb-6">Recent Field Reports</h3>
          
          <div className="space-y-4">
            {stats.recent_activity.map((evt) => (
              <div key={evt.id} className="flex items-center justify-between p-4 bg-slate-950/50 rounded-2xl border border-slate-800">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                    evt.status === 'confirmed' || evt.status === 'auto-updated' 
                      ? 'bg-emerald-500/10 text-emerald-400' 
                      : evt.status === 'rejected' 
                      ? 'bg-red-500/10 text-red-400'
                      : 'bg-amber-500/10 text-amber-400'
                  }`}>
                    {evt.status === 'confirmed' || evt.status === 'auto-updated' ? <CheckCircle2 className="w-5 h-5" /> : 
                     evt.status === 'rejected' ? <AlertCircle className="w-5 h-5" /> : 
                     <Clock className="w-5 h-5" />}
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-slate-200">{evt.extracted_json?.action || evt.extracted_json?.activity_phrase || "Unknown Activity"}</h4>
                    <p className="text-xs text-slate-500">
                      Discipline: {evt.extracted_json?.discipline || "Unknown"} • Match Confidence: {(evt.confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded ${
                    evt.status === 'confirmed' || evt.status === 'auto-updated' 
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                      : evt.status === 'rejected' 
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  }`}>
                    {evt.status}
                  </span>
                  <div className="text-xs text-slate-600 mt-1">
                    {new Date(evt.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </div>
                </div>
              </div>
            ))}
            
            {stats.recent_activity.length === 0 && (
              <div className="text-center py-8 text-slate-500 text-sm">
                No recent activity recorded.
              </div>
            )}
          </div>
        </motion.div>

      </div>
    </main>
  );
}
