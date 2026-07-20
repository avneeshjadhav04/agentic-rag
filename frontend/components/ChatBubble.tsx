"use client";

import { Copy, Check } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { ChatMessage } from "@/types";
import { cn } from "@/lib/cn";
import TraceChain from "./TraceChain";

interface ChatBubbleProps {
  message: ChatMessage;
  isStreaming: boolean;
}

function CodeBlock({ language, children }: { language: string; children: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="group relative">
      <button
        onClick={copy}
        className="absolute top-2 right-2 z-10 flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition opacity-0 group-hover:opacity-100"
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
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
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
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || "");
                      const text = String(children).replace(/\n$/, "");
                      return match ? (
                        <CodeBlock language={match[1]}>{text}</CodeBlock>
                      ) : (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {isStreaming && message.content && (
                  <span className="streaming-cursor" />
                )}
              </div>
            )}
          </div>

          {!isUser && message.content && !isStreaming && (
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