"use client";

import { Copy, Check } from "lucide-react";
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
  supervisor: "Supervisor",
  researcher: "Researcher",
  tool_result: "Tool Result",
  handoff: "Handoff",
  writer: "Writer",
  quality_check: "Quality Check",
};

function TraceRow({ step, detail, status, isLast }: { step: string; detail?: TraceStep; status: "done" | "running" | "pending"; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const label = STEP_LABELS[step] || step;
  const hasDetail = detail && Object.keys(detail).length > 1;

  const copyStep = () => {
    navigator.clipboard.writeText(JSON.stringify(detail, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn("border-b border-line", isLast && "border-b-0")}>
      <button
        onClick={() => hasDetail && setExpanded(!expanded)}
        className={cn(
          "w-full flex items-center gap-2 px-4 py-3 text-left",
          !hasDetail && "cursor-default"
        )}
      >
        {status === "done" && (
          <span className="font-mono text-[11px] leading-none text-success">✓</span>
        )}
        {status === "running" && (
          <span className="inline-block w-3 h-3 border border-accent border-t-transparent rounded-full animate-spin flex-shrink-0" />
        )}

        <span className={cn(
          "font-mono text-[11px] uppercase tracking-widest",
          status === "running" ? "text-accent" : "text-text"
        )}>
          {label}
        </span>

        <div className="flex-1" />

        {hasDetail && (
          <span className="font-mono text-[10px] text-muted">
            {expanded ? "[-]" : "[+]"}
          </span>
        )}
      </button>
      {expanded && detail && (
        <div className="px-4 pb-3">
          <div className="flex justify-start mb-2">
            <button
              onClick={copyStep}
              className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3" /> Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" /> Copy
                </>
              )}
            </button>
          </div>
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

  return (
    <div className="w-full max-w-full md:max-w-[680px] mb-5 border border-line">
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
