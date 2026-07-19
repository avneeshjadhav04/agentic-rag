"use client";

import { X } from "lucide-react";

interface AgentTraceProps {
  trace: any[];
  onClose: () => void;
}

export default function AgentTrace({ trace, onClose }: AgentTraceProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6">
      <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-2xl bg-surface border border-border shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-border bg-surface">
          <h3 className="text-lg font-semibold text-primary">Agent Trace</h3>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-panel text-muted hover:text-text">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          {trace.map((step, idx) => (
            <div key={idx} className="rounded-xl border border-border bg-panel p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="px-2 py-1 rounded-md bg-primary/10 text-primary text-xs font-semibold">
                  {step.step}
                </span>
              </div>
              <pre className="text-xs text-muted overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(step, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
