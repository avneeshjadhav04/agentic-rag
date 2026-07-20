"use client";

import { Menu } from "lucide-react";
import { useChatStore } from "@/store/chatStore";

interface ChatHeaderProps {
  onToggleSidebar?: () => void;
}

export default function ChatHeader({ onToggleSidebar }: ChatHeaderProps) {
  const clearMessages = useChatStore((s) => s.clearMessages);
  const hasMessages = useChatStore((s) => s.messages.length > 0);

  return (
    <div className="flex items-center justify-between px-4 md:px-8 py-3 border-b border-line">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="md:hidden text-muted hover:text-text transition"
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <h2 className="text-base font-semibold tracking-tighter text-text">Chat</h2>
      </div>
      {hasMessages && (
        <button
          onClick={clearMessages}
          className="text-xs rounded-sm border border-line px-2 py-1 text-muted hover:text-text hover:border-text transition-colors"
        >
          Clear
        </button>
      )}
    </div>
  );
}