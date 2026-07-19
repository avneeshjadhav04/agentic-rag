"use client";

import { useRef, useLayoutEffect } from "react";
import { ChatMessage } from "@/types";
import ChatBubble from "./ChatBubble";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

export default function ChatMessages({ messages, isStreaming }: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const latestUserRef = useRef<HTMLDivElement>(null);
  const spacerRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(messages.length);

  const lastContent = messages[messages.length - 1]?.content ?? "";

  useLayoutEffect(() => {
    const container = containerRef.current;
    const userEl = latestUserRef.current;
    const spacer = spacerRef.current;
    if (!container || !userEl || !spacer) return;

    const paddingTop = parseFloat(getComputedStyle(container).paddingTop);
    const targetScrollTop = userEl.offsetTop - container.offsetTop - paddingTop;

    spacer.style.height = '0px';
    const maxScrollTop = container.scrollHeight - container.clientHeight;

    if (targetScrollTop > maxScrollTop) {
      spacer.style.height = `${targetScrollTop - maxScrollTop}px`;
    }

    const isNewMessage = messages.length !== prevLengthRef.current;
    prevLengthRef.current = messages.length;
    if (isNewMessage) {
      container.scrollTop = targetScrollTop;
    }
  }, [messages.length, lastContent]);

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
        {messages.map((msg, idx) => {
          const isLatestUser = msg.role === "user" && idx === messages.length - 1 - (messages[messages.length - 1]?.role === "assistant" ? 1 : 0);
          return (
            <div key={idx} ref={isLatestUser ? latestUserRef : undefined}>
              <ChatBubble
                message={msg}
                isStreaming={isStreaming && idx === messages.length - 1}
              />
            </div>
          );
        })}
        <div ref={spacerRef} aria-hidden="true" />
      </div>
    </div>
  );
}