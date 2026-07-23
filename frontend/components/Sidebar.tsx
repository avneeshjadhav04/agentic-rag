"use client";

import { useState } from "react";
import { Plus, Minus, X } from "lucide-react";
import ProviderConfig from "./ProviderConfig";
import IngestionPanel from "./IngestionPanel";
import WebFallbackToggle from "./WebFallbackToggle";
import EvalPanel from "./EvalPanel";

interface SidebarProps {
  onClose?: () => void;
}

export default function Sidebar({ onClose }: SidebarProps) {
  const [sections, setSections] = useState({ ingestion: true, fallback: true, eval: true, config: true });

  const toggleSection = (key: keyof typeof sections) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));

  const sectionButton = (key: keyof typeof sections, num: string, label: string) => (
    <button
      onClick={() => toggleSection(key)}
      className="flex items-center justify-between w-full text-left font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition py-2"
    >
      <span>
        <span className="text-text">{num}</span>
        <span className="mx-2">/</span>
        <span>{label}</span>
      </span>
      {sections[key] ? <Minus className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
    </button>
  );

  return (
    <aside className="flex-shrink-0 flex flex-col h-full bg-surface w-80 md:w-96">
      <div className="px-6 md:px-8 py-6 border-b border-line flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tighter text-text">Agentic RAG</h1>
          <p className="font-mono text-[11px] uppercase tracking-widest text-muted mt-1">
            Multi-agent retrieval system
          </p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="md:hidden text-muted hover:text-text transition"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 md:px-8 py-8 space-y-8">
        {/* Ingestion */}
        <div>
          {sectionButton("ingestion", "01", "Ingestion")}
          {sections.ingestion && (
            <div className="mt-4">
              <IngestionPanel />
            </div>
          )}
        </div>

        {/* Web Fallback */}
        <div>
          {sectionButton("fallback", "02", "Web Fallback")}
          {sections.fallback && (
            <div className="mt-4">
              <WebFallbackToggle />
            </div>
          )}
        </div>

        {/* Evaluation */}
        <div>
          {sectionButton("eval", "03", "Evaluation")}
          {sections.eval && (
            <div className="mt-4">
              <EvalPanel />
            </div>
          )}
        </div>

        {/* Configuration */}
        <div>
          {sectionButton("config", "04", "Configuration (optional)")}
          {sections.config && (
            <div className="mt-4">
              <ProviderConfig />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}