"use client";

import { useState } from "react";
import { PanelRightOpen } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import Chat from "@/components/Chat";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen w-full bg-background text-text overflow-hidden">
      <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      <main className="flex-1 flex flex-col min-w-0 bg-background relative">
        {!sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="absolute top-4 left-24 z-10 p-2 rounded-lg bg-panel border border-border hover:border-primary transition"
          >
            <PanelRightOpen className="w-5 h-5 text-primary" />
          </button>
        )}
        <Chat />
      </main>
    </div>
  );
}
