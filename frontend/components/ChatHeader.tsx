"use client";

import { Bot } from "lucide-react";

interface ChatHeaderProps {
  messageCount: number;
}

export default function ChatHeader({ messageCount }: ChatHeaderProps) {
  return (
    <div className="flex items-center gap-3 px-8 py-5 border-b border-border bg-surface">
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
