"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage } from "@/types";
import { cn } from "@/lib/cn";

interface ChatBubbleProps {
  message: ChatMessage;
  isStreaming: boolean;
  onViewTrace: (trace: any[]) => void;
}

export default function ChatBubble({ message, isStreaming, onViewTrace }: ChatBubbleProps) {
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
                {message.content || (isStreaming ? "..." : "")}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && message.content && (
          <div className="flex items-center gap-4 mt-3">
            {message.trace && message.trace.length > 0 && (
              <button
                onClick={() => onViewTrace(message.trace || [])}
                className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-text transition"
              >
                View agent trace
              </button>
            )}
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
    </div>
  );
}