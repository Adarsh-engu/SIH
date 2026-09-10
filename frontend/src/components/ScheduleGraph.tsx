"use client";

import { useEffect, useState, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  MarkerType,
  BackgroundVariant
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';

type RawNode = {
  id: string;
  name: string;
  discipline: string;
  level: number;
  status: 'pending' | 'needs-review' | 'auto-updated' | 'confirmed' | 'rejected';
  percent_complete?: number;
  duration?: number;
};

const getStatusStyles = (status: string) => {
    switch (status) {
        case 'confirmed': return { bg: '#064e3b', border: '#10b981', shadow: '0 0 15px rgba(16, 185, 129, 0.2)', text: 'text-emerald-50', badgeBg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' };
        case 'auto-updated': return { bg: '#134e4a', border: '#14b8a6', shadow: '0 0 15px rgba(20, 184, 166, 0.2)', text: 'text-teal-50', badgeBg: 'bg-teal-500/20 text-teal-300 border-teal-500/30' };
        case 'needs-review': return { bg: '#451a03', border: '#f59e0b', shadow: '0 0 15px rgba(245, 158, 11, 0.2)', text: 'text-amber-50', badgeBg: 'bg-amber-500/20 text-amber-300 border-amber-500/30' };
        case 'rejected': return { bg: '#4c0519', border: '#f43f5e', shadow: '0 0 15px rgba(244, 63, 94, 0.2)', text: 'text-rose-50', badgeBg: 'bg-rose-500/20 text-rose-300 border-rose-500/30' };
        default: return { bg: '#0f172a', border: '#334155', shadow: 'none', text: 'text-slate-200', badgeBg: 'bg-slate-700 text-slate-300 border-slate-600' };
    }
};

type RawEdge = {
  source: string;
  target: string;
  type: string;
};

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 200 });

  nodes.forEach((node) => {
    // estimate node width and height based on text content
    dagreGraph.setNode(node.id, { width: 250, height: 96 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = direction === 'LR' ? 'left' as any : 'top' as any;
    node.sourcePosition = direction === 'LR' ? 'right' as any : 'bottom' as any;
    
    // We are shifting the dagre node position (anchor=center center) to the top left
    // so it matches the React Flow node anchor point (top left).
    node.position = {
      x: nodeWithPosition.x - 250 / 2,
      y: nodeWithPosition.y - 96 / 2,
    };
  });

  return { nodes, edges };
};

export default function ScheduleGraph({ refreshTrigger }: { refreshTrigger: number }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [baseNodes, setBaseNodes] = useState<Node[]>([]);
  const [baseEdges, setBaseEdges] = useState<Edge[]>([]);
  const [allNodes, setAllNodes] = useState<Node[]>([]);
  const [allEdges, setAllEdges] = useState<Edge[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Focus Filter
  const [focusDiscipline, setFocusDiscipline] = useState<string>('Piping');

  // Simulation State
  const [isSimulationMode, setIsSimulationMode] = useState(false);
  const [simulationDiscipline, setSimulationDiscipline] = useState('Piping');
  const [simulationDelayDays, setSimulationDelayDays] = useState(15);
  const [delayChain, setDelayChain] = useState<{node: Node, reason: string}[]>([]);

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/schedule-graph");
        if (!res.ok) throw new Error("Failed to fetch graph");
        const data = await res.json();

        // Convert backend nodes to ReactFlow nodes
        const rfNodes: Node[] = data.nodes
          // Filter to level 5 (leaf activities) to keep the graph manageable
          .filter((n: RawNode) => n.level === 5)
          .map((n: RawNode) => {
            const styles = getStatusStyles(n.status);
            return {
              id: n.id,
              data: { 
                  discipline: n.discipline,
                  name: n.name,
                  duration: n.duration || 5,
                  label: (
                      <div className="flex flex-col h-full justify-between">
                          <div className="flex justify-between items-start mb-2">
                              <span className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border ${styles.badgeBg}`}>
                                  {n.discipline}
                              </span>
                              <span className="text-[10px] text-slate-500 font-mono">{n.id}</span>
                          </div>
                          <p className={`text-xs text-left leading-tight font-medium flex-1 ${styles.text}`}>
                              {n.name}
                          </p>
                          {n.percent_complete !== undefined && (
                              <div className="mt-2 w-full shrink-0">
                                  <div className="flex justify-between items-center mb-1">
                                      <span className="text-[9px] text-slate-400 font-medium">Progress</span>
                                      <span className="text-[9px] font-bold text-blue-400">{n.percent_complete}%</span>
                                  </div>
                                  <div className="w-full h-1 bg-slate-800/50 rounded-full overflow-hidden border border-slate-700/30">
                                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, Math.max(0, n.percent_complete))}%` }}></div>
                                  </div>
                              </div>
                          )}
                      </div>
                  ) 
              },
              position: { x: 0, y: 0 },
              style: {
                  width: 250,
                  height: 96,
                  background: styles.bg,
                  border: `1px solid ${styles.border}`,
                  borderRadius: '12px',
                  padding: '12px',
                  boxShadow: styles.shadow,
              }
            };
          });

        const validNodeIds = new Set(rfNodes.map(n => n.id));

        const edgeIds = new Set();
        const rfEdges: Edge[] = data.edges
          .filter((e: RawEdge) => e.type === 'predecessor')
          .filter((e: RawEdge) => validNodeIds.has(e.source) && validNodeIds.has(e.target))
          .filter((e: RawEdge) => {
              const id = `${e.source}-${e.target}`;
              if (edgeIds.has(id)) return false;
              edgeIds.add(id);
              return true;
          })
          .map((e: RawEdge) => ({
            id: `${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            animated: true,
            style: { stroke: '#475569', strokeWidth: 2 },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#475569',
            },
          }));

        setAllNodes(rfNodes);
        setAllEdges(rfEdges);
      } catch (err: any) {
        console.error("Error loading graph:", err);
        setErrorMsg(err.message || "Failed to render graph");
      } finally {
        setIsLoading(false);
      }
    };

    fetchGraph();
  }, [refreshTrigger, setNodes, setEdges]); // re-fetch when trigger changes (e.g. WebSocket update)

  useEffect(() => {
      if (allNodes.length === 0) return;
      
      let filteredNodes = allNodes;
      if (focusDiscipline !== 'All') {
          filteredNodes = allNodes.filter(n => n.data.discipline === focusDiscipline);
      }
      
      const validIds = new Set(filteredNodes.map(n => n.id));
      const filteredEdges = allEdges.filter(e => validIds.has(e.source) && validIds.has(e.target));
      
      const layouted = getLayoutedElements(filteredNodes, filteredEdges, 'LR');
      setBaseNodes(layouted.nodes);
      setBaseEdges(layouted.edges);
  }, [allNodes, allEdges, focusDiscipline]);

  useEffect(() => {
    if (baseNodes.length === 0) return;

    if (!isSimulationMode || simulationDelayDays === 0) {
        setNodes(baseNodes);
        setEdges(baseEdges);
        setDelayChain([]);
        return;
    }

    // Identify primary delayed nodes
    const primaryDelayedNodeIds = new Set<string>();
    baseNodes.forEach(n => {
        if (n.data.discipline === simulationDiscipline) {
            primaryDelayedNodeIds.add(n.id);
        }
    });

    // BFS to find cascading delays (descendants)
    const cascadingDelayedNodeIds = new Set<string>();
    const adjList = new Map<string, string[]>();
    baseEdges.forEach(e => {
        if (!adjList.has(e.source)) adjList.set(e.source, []);
        adjList.get(e.source)!.push(e.target);
    });

    const queue = Array.from(primaryDelayedNodeIds);
    while (queue.length > 0) {
        const curr = queue.shift()!;
        const neighbors = adjList.get(curr) || [];
        for (const next of neighbors) {
            if (!primaryDelayedNodeIds.has(next) && !cascadingDelayedNodeIds.has(next)) {
                cascadingDelayedNodeIds.add(next);
                queue.push(next);
            }
        }
    }

    // Phase 17: Compute Propagation Chain (Longest Path by Duration)
    const memo = new Map<string, { path: string[], weight: number }>();
    const getLongestPath = (nodeId: string): { path: string[], weight: number } => {
        if (memo.has(nodeId)) return memo.get(nodeId)!;
        const neighbors = adjList.get(nodeId) || [];
        let maxPath: string[] = [];
        let maxWeight = 0;
        
        for (const next of neighbors) {
            const nextResult = getLongestPath(next);
            if (nextResult.weight > maxWeight) {
                maxWeight = nextResult.weight;
                maxPath = nextResult.path;
            }
        }
        
        const node = baseNodes.find(n => n.id === nodeId);
        const nodeDuration = (node?.data?.duration as number) || 5;
        const res = { 
            path: [nodeId, ...maxPath], 
            weight: maxWeight + nodeDuration 
        };
        memo.set(nodeId, res);
        return res;
    };

    let globalMaxPath: string[] = [];
    let globalMaxWeight = 0;
    for (const pid of primaryDelayedNodeIds) {
        const result = getLongestPath(pid);
        if (result.weight > globalMaxWeight) {
            globalMaxWeight = result.weight;
            globalMaxPath = result.path;
        }
    }

    const chain = globalMaxPath.map((id, idx) => {
        const node = baseNodes.find(n => n.id === id)!;
        let reason = '';
        if (idx === 0) {
            reason = `Primary delay on ${node.data.discipline} activity (+${simulationDelayDays} days).`;
        } else if (idx === 1) {
            const prevNode = baseNodes.find(n => n.id === globalMaxPath[idx - 1])!;
            reason = `Blocks ${node.data.discipline} activity '${node.data.name}' due to dependency on '${prevNode.data.name}'.`;
        } else if (idx === globalMaxPath.length - 1) {
            reason = `Threatens downstream milestone: '${node.data.name}'.`;
        } else {
            reason = `Puts ${node.data.discipline} activity '${node.data.name}' at risk.`;
        }
        return { node, reason };
    });
    setDelayChain(chain);

    // Apply styles
    const newNodes = baseNodes.map(n => {
        if (primaryDelayedNodeIds.has(n.id)) {
            return {
                ...n,
                style: {
                    ...n.style,
                    background: '#431407', // orange-950
                    border: '1px solid #f97316', // orange-500
                    boxShadow: '0 0 15px rgba(249, 115, 22, 0.4)',
                }
            };
        }
        if (cascadingDelayedNodeIds.has(n.id)) {
            return {
                ...n,
                style: {
                    ...n.style,
                    background: '#4c0519', // rose-950
                    border: '1px solid #f43f5e', // rose-500
                    boxShadow: '0 0 15px rgba(244, 63, 94, 0.4)',
                }
            };
        }
        return n;
    });

    const newEdges = baseEdges.map(e => {
        if (primaryDelayedNodeIds.has(e.source) || cascadingDelayedNodeIds.has(e.source)) {
            return {
                ...e,
                style: { stroke: '#f43f5e', strokeWidth: 3 }, // red edge
                animated: true,
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: '#f43f5e',
                }
            };
        }
        return e;
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [baseNodes, baseEdges, isSimulationMode, simulationDiscipline, simulationDelayDays, setNodes, setEdges]);

  if (isLoading) {
      return (
          <div className="w-full h-full flex items-center justify-center bg-slate-950/50 border border-slate-800 rounded-3xl">
              <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full"></div>
          </div>
      );
  }

  if (errorMsg || nodes.length === 0) {
      return (
          <div className="w-full h-full flex flex-col items-center justify-center bg-slate-950/50 border border-red-500/20 rounded-3xl text-slate-300 p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
                  <span className="text-red-400 text-xl font-bold">!</span>
              </div>
              <h3 className="text-lg font-medium text-slate-200 mb-2">Graph Failed to Render</h3>
              <p className="text-sm text-slate-400 max-w-md">{errorMsg || "No Level 5 nodes found in schedule graph."}</p>
          </div>
      );
  }

  return (
    <div className="flex-1 w-full h-full min-h-[500px] bg-slate-950 rounded-3xl overflow-hidden border border-slate-800 relative shadow-inner">
      <div className="absolute inset-0">
        <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={1.5}
        colorMode="dark"
        style={{ width: '100%', height: '100%' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2} color="#334155" />
        <Controls className="bg-slate-900 border-slate-800 fill-slate-300" />
      </ReactFlow>
      </div>

      {/* Simulation Panel */}
      <div className="absolute top-6 left-6 z-10 w-80">
          <div className="bg-slate-900/80 backdrop-blur-md border border-slate-700 rounded-2xl p-5 shadow-2xl">
              
              <div className="mb-6">
                  <label className="block text-xs font-medium text-slate-400 mb-1">Focus Filter</label>
                  <select 
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 px-3 py-2 focus:ring-1 focus:ring-indigo-500 outline-none"
                      value={focusDiscipline}
                      onChange={(e) => setFocusDiscipline(e.target.value)}
                  >
                      <option value="All">All Disciplines (Full View)</option>
                      <option value="Civil">Civil</option>
                      <option value="Piping">Piping</option>
                      <option value="Electrical">Electrical</option>
                      <option value="Instrumentation">Instrumentation</option>
                      <option value="HSE">HSE</option>
                  </select>
              </div>

              <hr className="border-slate-800 mb-6" />

              <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-slate-100 flex items-center gap-2">
                      <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                      </svg>
                      What-If Simulation
                  </h3>
                  <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" checked={isSimulationMode} onChange={(e) => setIsSimulationMode(e.target.checked)} />
                      <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-500"></div>
                  </label>
              </div>

              {isSimulationMode && (
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-4 duration-300">
                      <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1">Delayed Discipline</label>
                          <select 
                              className="w-full bg-slate-950 border border-slate-700 rounded-lg text-sm text-slate-200 px-3 py-2 focus:ring-1 focus:ring-indigo-500 outline-none"
                              value={simulationDiscipline}
                              onChange={(e) => setSimulationDiscipline(e.target.value)}
                          >
                              <option value="Civil">Civil</option>
                              <option value="Piping">Piping</option>
                              <option value="Electrical">Electrical</option>
                              <option value="Instrumentation">Instrumentation</option>
                              <option value="HSE">HSE</option>
                          </select>
                      </div>
                      <div>
                          <div className="flex justify-between items-end mb-1">
                              <label className="block text-xs font-medium text-slate-400">Delay Impact (Days)</label>
                              <span className="text-sm font-bold text-orange-400">+{simulationDelayDays}</span>
                          </div>
                          <input 
                              type="range" 
                              min="0" 
                              max="60" 
                              step="5"
                              value={simulationDelayDays}
                              onChange={(e) => setSimulationDelayDays(Number(e.target.value))}
                              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-orange-500" 
                          />
                      </div>
                      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mt-4">
                          <p className="text-xs text-red-300 font-medium">
                              Estimated Project Delay: <span className="font-bold">+{simulationDelayDays > 0 ? simulationDelayDays + 2 : 0} days</span>
                          </p>
                          <p className="text-[10px] text-red-400/70 mt-1">
                              Cascading delay pushes critical path out.
                          </p>
                      </div>
                  </div>
              )}
          </div>
      </div>
      
      {/* Delay Propagation Chain Panel */}
      {isSimulationMode && delayChain.length > 0 && (
          <div className="absolute top-6 right-6 z-10 w-96 max-h-[80vh] flex flex-col pointer-events-none">
              <div className="bg-slate-900/90 backdrop-blur-md border border-slate-700 rounded-2xl p-5 shadow-2xl flex-1 overflow-y-auto custom-scrollbar pointer-events-auto">
                  <h3 className="font-bold text-slate-100 flex items-center gap-2 mb-5">
                      <svg className="w-4 h-4 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Delay Propagation Chain
                  </h3>
                  <div className="space-y-4 relative">
                      <div className="absolute left-2.5 top-3 bottom-3 w-0.5 bg-slate-700/50"></div>
                      {delayChain.map((step, idx) => (
                          <div key={idx} className="relative pl-8 animate-in fade-in slide-in-from-right-4" style={{ animationDelay: `${idx * 150}ms`, animationFillMode: 'both' }}>
                              <div className={`absolute left-0 top-1 w-5 h-5 rounded-full flex items-center justify-center border-2 bg-slate-900 shadow-sm ${idx === 0 ? 'border-orange-500 shadow-orange-500/20' : 'border-rose-500 shadow-rose-500/20'}`}>
                                  <div className={`w-2 h-2 rounded-full ${idx === 0 ? 'bg-orange-500' : 'bg-rose-500'}`}></div>
                              </div>
                              <h4 className="text-sm font-bold text-slate-200 leading-tight">{step.node.data.name}</h4>
                              <p className="text-[11px] text-slate-400 mt-1 leading-snug">{step.reason}</p>
                          </div>
                      ))}
                  </div>
              </div>
          </div>
      )}
      
      {/* Overlay Legend */}
      <div className="absolute bottom-6 right-6 bg-slate-900/90 backdrop-blur border border-slate-800 p-4 rounded-xl shadow-xl z-10 pointer-events-none">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Legend</h4>
          <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-slate-900 border border-slate-700"></div>
                  <span className="text-sm text-slate-300">Pending Activity</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-amber-950 border border-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.3)]"></div>
                  <span className="text-sm text-slate-300">Needs Review</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-teal-950 border border-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.3)]"></div>
                  <span className="text-sm text-slate-300">Auto-Updated</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-emerald-950 border border-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)]"></div>
                  <span className="text-sm text-slate-300">Confirmed</span>
              </div>
              <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-rose-950 border border-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.3)]"></div>
                  <span className="text-sm text-slate-300">Rejected</span>
              </div>
              {isSimulationMode && (
                  <>
                      <div className="flex items-center gap-2 mt-2">
                          <div className="w-4 h-4 rounded bg-orange-950 border border-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.3)]"></div>
                          <span className="text-sm text-orange-300">Primary Delay</span>
                      </div>
                      <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded bg-rose-950 border border-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.3)]"></div>
                          <span className="text-sm text-rose-300">Cascading Delay</span>
                      </div>
                  </>
              )}
          </div>
      </div>
    </div>
  );
}
