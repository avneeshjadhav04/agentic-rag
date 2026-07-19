"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";

interface TraceStep {
  step: string;
  [key: string]: any;
}

interface TraceChainProps {
  trace: TraceStep[];
  live: boolean;
}

const STEP_LABELS: Record<string, string> = {
  retrieve: "Retrieve",
  grade_documents: "Grade Documents",
  propose_urls: "Propose URLs",
  fetch_urls: "Fetch URLs",
  generate: "Generate",
  quality_check: "Quality Check",
};

function TraceRow({ step, detail, status, isLast }: { step: string; detail?: TraceStep; status: "done" | "running" | "pending"; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const label = STEP_LABELS[step] || step;
  const hasDetail = detail && Object.keys(detail).length > 1;

  return (
    <div className={cn("border-b border-line", isLast && "border-b-0")}>
      <button
        onClick={() => hasDetail && setExpanded(!expanded)}
        className={cn(
          "w-full flex items-center gap-3 px-4 py-3 text-left",
          !hasDetail && "cursor-default"
        )}
      >
        {status === "done" && (
          <span className="font-mono text-[10px] text-muted">--</span>
        )}
        {status === "running" && (
          <span className="font-mono text-[10px] text-accent animate-pulse">--</span>
        )}
        {status === "pending" && (
          <span className="font-mono text-[10px] text-muted/40">--</span>
        )}
        <span className="font-mono text-[11px] uppercase tracking-widest text-text">
          {label}
        </span>
        {status === "running" && (
          <span className="font-mono text-[10px] uppercase tracking-widest text-accent ml-auto animate-pulse">
            Running
          </span>
        )}
        {hasDetail && (
          <span className="font-mono text-[10px] text-muted ml-auto">
            {expanded ? "[-]" : "[+]"}
          </span>
        )}
      </button>
      {expanded && detail && (
        <div className="px-4 pb-3">
          <pre className="font-mono text-[11px] text-muted whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(detail, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function TraceChain({ trace, live }: TraceChainProps) {
  if (!trace || trace.length === 0) return null;

  const doneSteps = new Set(trace.map((t) => t.step));

  return (
    <div className="w-full max-w-[680px] mb-5 border border-line">
      {trace.map((entry, idx) => (
        <TraceRow
          key={entry.step + idx}
          step={entry.step}
          detail={entry}
          status={live && idx === trace.length - 1 ? "running" : "done"}
          isLast={idx === trace.length - 1}
        />
      ))}
    </div>
  );
}
