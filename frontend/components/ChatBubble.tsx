"use client";

import { Copy, Check, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
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
    <div className="group relative overflow-x-auto">
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

function SourcesPanel({ trace }: { trace: any[] }) {
  const [expanded, setExpanded] = useState(false);
  const retrieveStep = trace.find((t) => t.step === "retrieve");
  const gradeStep = trace.find((t) => t.step === "grade_documents");
  const gradeUrlsStep = trace.find((t) => t.step === "grade_urls");
  const fetchStep = trace.find((t) => t.step === "fetch_urls");

  const sources: { name: string; isWeb: boolean; chunks?: number }[] = [];

  if (retrieveStep && gradeStep) {
    const allSources: { name: string; chunks?: number }[] = (retrieveStep.sources || []).map((s: any) =>
      typeof s === "string" ? { name: s } : s
    );
    const grades: { index: number; relevant: boolean }[] = gradeStep.grades || [];
    const relevantIndices = new Set(
      grades.filter((g) => g.relevant).map((g) => g.index)
    );
    const sourceIndexMap = new Map<string, number[]>();
    allSources.forEach((src, i) => {
      if (relevantIndices.has(i) && src.name) {
        const arr = sourceIndexMap.get(src.name) || [];
        arr.push(i);
        sourceIndexMap.set(src.name, arr);
      }
    });
    sourceIndexMap.forEach((indices, name) => {
      sources.push({ name, isWeb: false, chunks: indices.length });
    });
  }

  if (fetchStep && gradeUrlsStep) {
    const urls: string[] = fetchStep.urls || [];
    const successful = fetchStep.successful_fetches || 0;
    const grades: { index: number; relevant: boolean }[] = gradeUrlsStep.grades || [];
    urls.slice(0, successful).forEach((url, i) => {
      const grade = grades[i];
      if (url && grade?.relevant) {
        sources.push({ name: url, isWeb: true });
      }
    });
  }

  if (sources.length === 0) return null;

  const seen = new Set<string>();
  const uniqueSources = sources.filter((s) => {
    const key = s.name;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return (
    <div className="mt-4 border-t border-line pt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted hover:text-text transition"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Sources ({uniqueSources.length})
      </button>
      {expanded && (
        <div className="mt-2 space-y-1">
          {uniqueSources.map((src, i) => (
            <div key={i} className="flex items-center gap-2 font-mono text-[11px] text-text">
              <span className="text-muted shrink-0">[{i + 1}]</span>
              {src.isWeb ? (
                <a
                  href={src.name}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate hover:text-accent transition flex items-center gap-1"
                >
                  {src.name}
                  <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                </a>
              ) : (
                <span className="truncate">{src.name}</span>
              )}
              {src.chunks !== undefined && (
                <span className="text-muted shrink-0 whitespace-nowrap">
                  ({src.chunks} chunk{src.chunks > 1 ? "s" : ""})
                </span>
              )}
            </div>
          ))}
        </div>
      )}
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
            "max-w-full md:max-w-[680px] text-sm leading-relaxed",
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

          {!isUser && message.trace && message.trace.length > 0 && !isStreaming && (
            <SourcesPanel trace={message.trace} />
          )}
        </div>
      )}
    </div>
  );
}