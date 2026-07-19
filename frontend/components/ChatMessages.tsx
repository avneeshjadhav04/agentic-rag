"use client";

import { useRef, useEffect } from "react";
import { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

export default function ChatMessages({ messages, isStreaming }: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || messages.length === 0) return;
    const userEls = containerRef.current.querySelectorAll('[data-role="user"]');
    if (userEls.length > 0) {
      const lastUser = userEls[userEls.length - 1] as HTMLElement;
      lastUser.scrollIntoView({ block: "start" });
    }
  }, [messages.length]);

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
    <div ref={containerRef} className="flex-1 overflow-y-auto px-8 py-8">
      <div className="mx-auto max-w-[680px] space-y-8">
        {messages.map((msg, idx) => (
          <div key={idx} data-role={msg.role}>
            <ChatBubble
              message={msg}
              isStreaming={isStreaming && idx === messages.length - 1}
            />
          </div>
        ))}
      </div>
    </div>
  );
}