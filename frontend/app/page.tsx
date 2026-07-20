"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import Sidebar from "@/components/Sidebar";
import Chat from "@/components/Chat";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen w-full bg-background text-text overflow-hidden">
      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — fixed overlay on mobile, relative inline on desktop */}
      <div
        className={cn(
          "flex flex-col h-full border-r border-line bg-surface",
          "fixed inset-y-0 left-0 z-40 w-80",
          "transition-transform duration-300 ease-in-out",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
          "md:relative md:translate-x-0 md:z-auto md:w-96 md:flex-shrink-0"
        )}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0 bg-background">
        <Chat onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      </main>
    </div>
  );
}