"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, Square, Send, CheckCircle2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";

export default function SupervisorApp() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [micError, setMicError] = useState("");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [result, setResult] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);

  const [isOnline, setIsOnline] = useState(true);
  const [offlineQueue, setOfflineQueue] = useState<string[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    if (typeof navigator !== "undefined") {
      setIsOnline(navigator.onLine);
    }
    
    const savedQueue = localStorage.getItem("setu_offline_queue");
    if (savedQueue) {
       try { setOfflineQueue(JSON.parse(savedQueue)); } catch(e) {}
    }

    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    if (typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognitionRef.current.onresult = (event: any) => {
        let finalTranscript = "";
        let interimTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        setTranscript(prev => {
            const cleanPrev = prev.replace(/\s*\(.*?\)\s*/g, '');
            return cleanPrev + finalTranscript + (interimTranscript ? ` (${interimTranscript})` : "");
        });
      };

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognitionRef.current.onerror = (event: any) => {
        if (event.error === 'network') {
            setMicError("Microphone network error (common in Brave/Firefox). Please type your report instead.");
        } else if (event.error === 'not-allowed') {
            setMicError("Microphone access denied. Please type your report instead.");
        } else {
            console.error("Speech recognition error", event.error);
        }
        setIsRecording(false);
      };
      
      recognitionRef.current.onend = () => {
         setIsRecording(false);
      }
    }
    
    return () => {
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    if (isOnline && offlineQueue.length > 0 && !isSyncing) {
        syncOfflineQueue();
    }
  }, [isOnline]);

  const syncOfflineQueue = async () => {
      setIsSyncing(true);
      const queue = [...offlineQueue]; 
      let remaining = [...queue];
      
      for (const phrase of queue) {
          try {
              const res = await fetch("http://127.0.0.1:8000/report", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ raw_phrase: phrase })
              });
              if (res.ok) {
                  remaining = remaining.filter(p => p !== phrase);
                  setOfflineQueue([...remaining]);
                  localStorage.setItem("setu_offline_queue", JSON.stringify(remaining));
              }
          } catch (e) {
              console.error("Sync failed for", phrase, e);
              break;
          }
      }
      setIsSyncing(false);
  };

  const toggleRecording = () => {
    if (!recognitionRef.current) {
        alert("Speech recognition is not supported in this browser.");
        return;
    }
    
    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
      setTranscript(prev => prev.replace(/\s*\(.*?\)\s*/g, ''));
    } else {
      setTranscript("");
      setStatus("idle");
      setResult(null);
      setMicError("");
      recognitionRef.current.start();
      setIsRecording(true);
    }
  };

  const handleSubmit = async () => {
    const finalPhrase = transcript.replace(/\s*\(.*?\)\s*/g, '').trim();
    if (!finalPhrase) return;
    
    if (isRecording) {
        recognitionRef.current.stop();
        setIsRecording(false);
    }
    
    if (!isOnline) {
        const newQueue = [...offlineQueue, finalPhrase];
        setOfflineQueue(newQueue);
        localStorage.setItem("setu_offline_queue", JSON.stringify(newQueue));
        
        setResult({
            extracted: { action: "Report Queued (Offline)", discipline: "Pending Sync" },
            match: { status: "needs-review" }
        });
        setStatus("success");
        return;
    }

    setStatus("submitting");
    
    try {
      const res = await fetch("http://127.0.0.1:8000/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_phrase: finalPhrase })
      });
      
      if (!res.ok) throw new Error("Failed to submit");
      
      const data = await res.json();
      setResult(data);
      setStatus("success");
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  };

  return (
    <main className="min-h-[100dvh] bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30 flex items-center justify-center p-4 sm:p-8">
      <Card className="w-full max-w-md bg-slate-900 border-slate-800 sm:rounded-3xl rounded-2xl shadow-2xl overflow-hidden relative flex flex-col min-h-[500px]">
        
        <div className="absolute top-4 right-4 z-20 flex flex-col items-end gap-2">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border shadow-lg ${isOnline ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-400' : 'bg-red-400'}`}></div>
                {isOnline ? 'Live Sync' : 'Offline Mode'}
            </div>
            
            <AnimatePresence>
                {offlineQueue.length > 0 && (
                    <motion.div 
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-lg"
                    >
                        {isSyncing ? <Loader2 className="w-3 h-3 animate-spin" /> : <span>📡</span>}
                        {isSyncing ? "Syncing..." : `${offlineQueue.length} queued`}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>

        <CardHeader className="p-6 pb-6 text-center space-y-2 relative z-10 border-b border-slate-800/50 bg-slate-900/80 backdrop-blur-md">
            <CardTitle className="text-2xl font-bold tracking-tight bg-gradient-to-br from-blue-400 to-indigo-500 bg-clip-text text-transparent">Setu Capture</CardTitle>
            <CardDescription className="text-slate-400 text-sm">Tap the mic to log a field event</CardDescription>
        </CardHeader>

        <CardContent className="p-6 space-y-8 flex-1 flex flex-col relative z-0">
            <AnimatePresence mode="wait">
                {status === "success" && result ? (
                    <motion.div 
                        key="success"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="flex-1 flex flex-col justify-center items-center text-center space-y-5"
                    >
                        <motion.div 
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", damping: 15 }}
                            className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-500 shadow-inner"
                        >
                            <CheckCircle2 className="w-10 h-10" />
                        </motion.div>
                        <h2 className="text-xl font-semibold">Report Logged</h2>
                        
                        <div className="bg-slate-950 p-5 rounded-2xl text-left w-full border border-slate-800 shadow-sm relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
                            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-semibold">Extracted Action</p>
                            <p className="font-medium text-slate-200">{result.match?.matched_node_name || result.extracted?.action || result.extracted?.activity_phrase}</p>
                            
                            <div className="mt-4 flex items-center justify-between">
                                <div>
                                    <p className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-semibold">Discipline</p>
                                    <Badge variant="outline" className="bg-blue-500/10 text-blue-400 border-blue-500/20 rounded font-medium">{result.match?.discipline || result.extracted?.discipline}</Badge>
                                </div>
                                {result.match?.percent_complete !== undefined && result.match?.percent_complete !== null && (
                                    <div className="text-center">
                                         <p className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-semibold">Progress</p>
                                         <Badge variant="outline" className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20 rounded font-medium">{result.match.percent_complete}%</Badge>
                                    </div>
                                )}
                                <div className="text-right">
                                     <p className="text-xs text-slate-500 uppercase tracking-wider mb-1 font-semibold">Status</p>
                                     <Badge variant="outline" className={`rounded font-medium ${result.match?.status === 'auto-updated' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                                        {result.match?.status === 'auto-updated' ? 'Matched' : 'Needs Review'}
                                     </Badge>
                                </div>
                            </div>
                        </div>
                        
                        <Button 
                            variant="link"
                            onClick={() => { setStatus("idle"); setTranscript(""); setResult(null); }}
                            className="text-slate-400 hover:text-white transition-colors text-sm mt-4 underline decoration-slate-700 hover:decoration-slate-500 underline-offset-4"
                        >
                            Log another event
                        </Button>
                    </motion.div>
                ) : (
                    <motion.div 
                        key="capture"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="flex-1 flex flex-col"
                    >
                        <div className="flex-1 relative mb-6 flex flex-col">
                            {micError && (
                                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm font-medium">
                                    {micError}
                                </div>
                            )}
                            <Textarea 
                                value={transcript}
                                onChange={(e) => setTranscript(e.target.value)}
                                placeholder="e.g. Sir, tied in the line at WP-14..."
                                className="w-full h-full min-h-[160px] bg-transparent border-none resize-none focus-visible:ring-0 text-xl sm:text-2xl text-slate-200 placeholder:text-slate-600 leading-relaxed shadow-none p-0"
                            />
                            {isRecording && (
                                <span className="absolute bottom-2 right-2 flex h-3 w-3">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                                </span>
                            )}
                        </div>

                        <div className="mt-auto flex items-center justify-between gap-4">
                            <motion.div
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                                className="inline-flex"
                            >
                                <Button
                                    size="icon"
                                    onClick={toggleRecording}
                                    className={`h-14 w-14 rounded-full transition-all duration-300 shadow-xl ${
                                        isRecording 
                                            ? 'bg-red-500 hover:bg-red-400 text-white shadow-red-500/25 ring-4 ring-red-500/20' 
                                            : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/25'
                                    }`}
                                >
                                    {isRecording ? <Square className="w-5 h-5" fill="currentColor" /> : <Mic className="w-6 h-6" />}
                                </Button>
                            </motion.div>

                            <motion.div
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                className="flex-1 flex"
                            >
                                <Button
                                    disabled={!transcript.trim() || status === "submitting"}
                                    onClick={handleSubmit}
                                    className="flex-1 h-14 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-medium border border-slate-700/50 shadow-sm"
                                >
                                    {status === "submitting" ? (
                                        <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                                    ) : (
                                        <>
                                            Submit <Send className="w-4 h-4 ml-2 text-slate-400" />
                                        </>
                                    )}
                                </Button>
                            </motion.div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </CardContent>
      </Card>
    </main>
  );
}
