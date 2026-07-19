"use client";

import { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

export default function ChatMessages({ messages, isStreaming }: ChatMessagesProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-8">
        <p className="text-2xl font-mono tracking-tighter gradient-ready">READY</p>
        <p className="font-mono text-[11px] uppercase tracking-widest text-muted mt-3">
          Ingest documents or ask a question directly.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-8 py-8 space-y-8">
      {messages.map((msg, idx) => (
        <ChatBubble
          key={idx}
          message={msg}
          isStreaming={isStreaming && idx === messages.length - 1}
        />
      ))}
    </div>
  );
}