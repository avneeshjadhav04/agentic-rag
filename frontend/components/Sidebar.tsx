"use client";

import { useState } from "react";
import {
  PanelRightClose,
  ChevronDown,
  ChevronRight,
  Settings,
  FileUp,
} from "lucide-react";
import { cn } from "@/lib/cn";
import ProviderConfig from "./ProviderConfig";
import IngestionPanel from "./IngestionPanel";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

export default function Sidebar({ open, onToggle }: SidebarProps) {
  const [sections, setSections] = useState({ config: true, ingestion: true });

  const toggleSection = (key: keyof typeof sections) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <aside
      className={cn(
        "flex-shrink-0 flex flex-col border-r border-border bg-surface transition-all duration-300",
        open ? "w-96" : "w-0 overflow-hidden"
      )}
    >
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-primary truncate">Agentic RAG</h1>
          <p className="text-xs text-muted">Multi-agent retrieval system</p>
        </div>
        <button
          onClick={onToggle}
          className="p-2 rounded-lg bg-panel border border-border hover:border-primary transition shrink-0"
        >
          <PanelRightClose className="w-5 h-5 text-primary" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Configuration */}
        <div>
          <button
            onClick={() => toggleSection("config")}
            className="flex items-center gap-2 w-full text-left text-sm font-semibold text-muted hover:text-text transition py-2"
          >
            {sections.config ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <Settings className="w-4 h-4" />
            Configuration
          </button>
          {sections.config && (
            <div className="mt-2">
              <ProviderConfig />
            </div>
          )}
        </div>

        {/* Ingestion */}
        <div>
          <button
            onClick={() => toggleSection("ingestion")}
            className="flex items-center gap-2 w-full text-left text-sm font-semibold text-muted hover:text-text transition py-2"
          >
            {sections.ingestion ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
            <FileUp className="w-4 h-4" />
            Ingestion
          </button>
          {sections.ingestion && (
            <div className="mt-2">
              <IngestionPanel />
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
