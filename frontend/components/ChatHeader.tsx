"use client";

import { Bot } from "lucide-react";
import { cn } from "@/lib/cn";

interface ChatHeaderProps {
  messageCount: number;
  sidebarOpen: boolean;
}

export default function ChatHeader({ messageCount, sidebarOpen }: ChatHeaderProps) {
  return (
    <div className={cn("flex items-center gap-3 border-b border-border bg-surface", sidebarOpen ? "px-8" : "pl-20 pr-8")}>
      <div className="p-2 rounded-lg bg-primary/10">
        <Bot className="w-6 h-6 text-primary" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-text">Agentic Chat</h2>
        <p className="text-xs text-muted">
          {messageCount === 0
            ? "Start a conversation"
            : `${messageCount} message${messageCount === 1 ? "" : "s"}`}
        </p>
      </div>
    </div>
  );
}
