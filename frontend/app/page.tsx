"use client";

import Chat from "@/components/Chat";
import IngestionPanel from "@/components/IngestionPanel";
import ProviderConfig from "@/components/ProviderConfig";
import { PanelRightOpen, PanelRightClose } from "lucide-react";
import { useState } from "react";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen w-full bg-background text-text overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`flex-shrink-0 flex flex-col border-r border-border bg-surface transition-all duration-300 ${
          sidebarOpen ? "w-96" : "w-0 overflow-hidden"
        }`}
      >
        <div className="p-6 border-b border-border">
          <h1 className="text-2xl font-bold text-primary">Agentic RAG</h1>
          <p className="text-sm text-muted">Multi-agent retrieval system</p>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <ProviderConfig />
          <IngestionPanel />
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0 bg-background relative">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute top-4 left-4 z-10 p-2 rounded-lg bg-panel border border-border hover:border-primary transition"
        >
          {sidebarOpen ? (
            <PanelRightClose className="w-5 h-5 text-primary" />
          ) : (
            <PanelRightOpen className="w-5 h-5 text-primary" />
          )}
        </button>
        <Chat />
      </main>
    </div>
  );
}
