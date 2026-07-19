"use client";

import { Bot, User, Activity, Copy, Check } from "lucide-react";
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

  return (
    <div className={cn("flex gap-4", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-5 py-4 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-white rounded-br-none"
            : "bg-surface border border-border text-text rounded-bl-none"
        )}
      >
        <div className="flex items-center gap-2 mb-2">
          {isUser ? (
            <User className="w-4 h-4" />
          ) : (
            <Bot className="w-4 h-4 text-primary" />
          )}
          <span className="text-xs font-medium opacity-80">
            {isUser ? "You" : "Agent"}
          </span>
        </div>

        <div>
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || (isStreaming ? "Thinking..." : "")}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser && message.content && (
          <div className="flex items-center gap-3 mt-3">
            {message.trace && message.trace.length > 0 && (
              <button
                onClick={() => onViewTrace(message.trace || [])}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary-light transition"
              >
                <Activity className="w-3 h-3" /> View agent trace
              </button>
            )}
            <button
              onClick={copyContent}
              className="flex items-center gap-1 text-xs text-muted hover:text-text transition"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-green-400" /> Copied
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
