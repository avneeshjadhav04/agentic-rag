"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Settings,
  FileUp,
} from "lucide-react";
import ProviderConfig from "./ProviderConfig";
import IngestionPanel from "./IngestionPanel";

export default function Sidebar() {
  const [sections, setSections] = useState({ config: true, ingestion: true });

  const toggleSection = (key: keyof typeof sections) =>
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <aside className="flex-shrink-0 flex flex-col border-r border-border bg-surface w-96">
      <div className="p-6 border-b border-border">
        <h1 className="text-2xl font-bold text-primary truncate">Agentic RAG</h1>
        <p className="text-xs text-muted">Multi-agent retrieval system</p>
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
