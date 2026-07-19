"use client";

import { Bot } from "lucide-react";
import { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onViewTrace: (trace: any[]) => void;
}

export default function ChatMessages({ messages, isStreaming, onViewTrace }: ChatMessagesProps) {
  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted px-8">
        <Bot className="w-12 h-12 mb-4 opacity-30" />
        <p className="text-lg">Start a conversation</p>
        <p className="text-sm">Ingest documents or ask a question directly.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">
      {messages.map((msg, idx) => (
        <ChatBubble
          key={idx}
          message={msg}
          isStreaming={isStreaming && idx === messages.length - 1}
          onViewTrace={onViewTrace}
        />
      ))}
    </div>
  );
}
