"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage } from "@/types";
import { cn } from "@/lib/cn";
import TraceChain from "./TraceChain";

interface ChatBubbleProps {
  message: ChatMessage;
  isStreaming: boolean;
}

export default function ChatBubble({ message, isStreaming }: ChatBubbleProps) {
  const [copied, setCopied] = useState(false);

  const copyContent = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = message.role === "user";
  const roleLabel = isUser ? "You" : "Agent";

  return (
    <div className={cn("flex flex-col", isUser ? "items-end" : "items-start")}>
      <span className="font-mono text-[10px] uppercase tracking-widest text-muted mb-2">
        {roleLabel}
      </span>

      {!isUser && message.trace && message.trace.length > 0 && (
        <TraceChain trace={message.trace} live={isStreaming && !message.content} />
      )}

      {isStreaming && !message.content && !isUser && (!message.trace || message.trace.length === 0) ? (
        <span className="gradient-working font-mono text-[14px] uppercase tracking-widest">
          Working
        </span>
      ) : (
        <div
          className={cn(
            "max-w-[680px] text-sm leading-relaxed",
            isUser
              ? "bg-accent text-background px-4 py-3"
              : "bg-transparent border-l-2 border-line pl-4"
          )}
        >
          <div>
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {!isUser && message.content && (
            <div className="flex items-center gap-4 mt-3">
              <button
                onClick={copyContent}
                className="flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" /> Copy
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}