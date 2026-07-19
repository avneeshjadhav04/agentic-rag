"use client";

import { X } from "lucide-react";

interface AgentTraceProps {
  trace: any[];
  onClose: () => void;
}

export default function AgentTrace({ trace, onClose }: AgentTraceProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-6">
      <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto bg-surface border border-line">
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-line bg-surface">
          <h3 className="font-mono text-[11px] uppercase tracking-widest text-text">
            Agent Trace
          </h3>
          <button
            onClick={onClose}
            className="p-1 text-muted hover:text-text"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          {trace.map((step, idx) => (
            <div key={idx} className="border border-line bg-panel p-4">
              <div className="mb-2">
                <span className="font-mono text-[11px] uppercase tracking-widest text-accent">
                  {step.step}
                </span>
              </div>
              <pre className="font-mono text-xs text-muted overflow-x-auto whitespace-pre-wrap">
                {JSON.stringify(step, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}