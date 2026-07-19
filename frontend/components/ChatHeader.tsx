"use client";

import { useChatStore } from "@/store/chatStore";

export default function ChatHeader() {
  const clearMessages = useChatStore((s) => s.clearMessages);

  return (
    <div className="flex items-center justify-between px-8 py-3 border-b border-line">
      <div>
        <h2 className="text-base font-semibold tracking-tighter text-text">Chat</h2>
      </div>
      <button
        onClick={clearMessages}
        className="text-xs rounded-sm border border-line px-2 py-1 text-muted hover:text-text hover:border-text transition-colors"
      >
        Clear
      </button>
    </div>
  );
}